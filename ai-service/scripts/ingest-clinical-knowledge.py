"""Approved-source ingestion for clinical retrieval (knowledge updates without touching model weights).

Pipeline: registry -> fetch (allowlisted HTTPS hosts, size/type limits, manual redirects) -> extract main
content -> section/unit chunking -> normalise + SHA-256 -> de-duplicate -> version against the previous
snapshot -> retire changed/removed chunks -> write knowledge/clinical-snapshot.json.

Fetched pages are untrusted data. Nothing in them is executed or treated as an instruction.

Usage (from ai-service/):
  python scripts/ingest-clinical-knowledge.py            # fetch everything in the registry
  python scripts/ingest-clinical-knowledge.py --only nhs-stye,nhs-red-eye
  python scripts/ingest-clinical-knowledge.py --check    # validate the existing snapshot only
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / 'ai-service'
sys.path.insert(0, str(SERVICE))
from app.clinical.untrusted import screen_untrusted  # noqa: E402

REGISTRY = ROOT / 'contracts/clinical/sources.v1.json'
SNAPSHOT = SERVICE / 'knowledge/clinical-snapshot.json'
MAX_BYTES = 2_000_000
SKIP_HEADINGS = re.compile(r'^(page last reviewed|help us improve|more in|related|video|other languages|support links|is this page useful|share|sign up|cookies)', re.I)
CREDIT = re.compile(r'PHOTO LIBRARY|Alamy|Stock Photo|Getty Images|Shutterstock|^https?://\S+$|\bhttps?://www\.(sciencephoto|alamy)', re.I)
CARE_LEVEL = [(re.compile(r'^immediate action required|call 999|go to a ?&? ?e', re.I), 'emergency'), (re.compile(r'^urgent advice', re.I), 'urgent'), (re.compile(r'^non-urgent advice', re.I), 'routine')]
MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December'
DATE_PATTERNS = {
    'last_reviewed': [rf'(?:Page last reviewed|Last reviewed|Content last reviewed)\s*:?\s*(\d{{1,2}} (?:{MONTHS}) \d{{4}})', rf'(?:Page last reviewed|Last reviewed|Content last reviewed)\s*:?\s*((?:{MONTHS}) \d{{1,2}},? \d{{4}})', r'(?:Last reviewed|Last updated)\s*:?\s*(\d{4}-\d{2}-\d{2})'],
    'last_updated': [rf'(?:Last updated|Page updated)\s*:?\s*((?:{MONTHS}) \d{{1,2}},? \d{{4}})', rf'(?:Last updated|Page updated)\s*:?\s*(\d{{1,2}} (?:{MONTHS}) \d{{4}})'],
    'next_review_due': [rf'Next review due\s*:?\s*(\d{{1,2}} (?:{MONTHS}) \d{{4}})'],
}


def normalise(text):
    return re.sub(r'\s+', ' ', text.replace(' ', ' ')).strip()


def iso(raw):
    raw = re.sub(r'\s+', ' ', raw.replace(',', '')).strip()
    match = re.match(r'(\d{1,2} [A-Za-z]+ \d{4}|[A-Za-z]+ \d{1,2} \d{4}|\d{4}-\d{2}-\d{2})', raw)
    raw = match.group(1) if match else raw
    for fmt in ('%d %B %Y', '%B %d %Y', '%d %b %Y', '%b %d %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:48] or 'overview'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def fetch(client, url, hosts):
    import httpx
    current = url
    for _ in range(4):
        with client.stream('GET', current) as response:
            if response.is_redirect:
                nxt = httpx.URL(str(response.url.join(response.headers['location'])))
                if nxt.scheme != 'https' or nxt.host not in hosts:
                    raise ValueError(f'redirect left the allowlist: {nxt}')
                current = str(nxt)
                continue
            response.raise_for_status()
            if 'text/html' not in response.headers.get('content-type', ''):
                raise ValueError('not HTML')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('page too large')
                chunks.append(chunk)
            return current, b''.join(chunks)
    raise ValueError('too many redirects')


def li_text(item):
    from bs4 import Tag
    parts = []
    for child in item.contents:
        if isinstance(child, Tag) and child.name in ('ul', 'ol'):
            continue
        parts.append(child.get_text(' ', strip=True) if isinstance(child, Tag) else str(child))
    return normalise(' '.join(parts))


def extract(source, final_url, html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    page_text = normalise(soup.get_text(' ', strip=True))
    dates = {}
    for key, patterns in DATE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, page_text)
            if match:
                dates[key] = iso(match.group(1))
                break
    published = None
    for attrs in ({'property': 'article:published_time'}, {'name': 'DC.date.issued'}, {'name': 'dcterms.created'}, {'name': 'citation_publication_date'}):
        tag = soup.find('meta', attrs=attrs)
        if tag and tag.get('content'):
            published = iso(tag['content'])
            break
    main = soup.find('main') or soup.find('article') or soup.body
    if main is None:
        raise ValueError('no main content')
    for node in main.select('script,style,nav,form,footer,aside,noscript,svg,button,figure,figcaption,picture,.nhsuk-review-date,.nhsuk-back-link,.nhsuk-breadcrumb'):
        node.decompose()
    title_tag = main.find('h1') or soup.find('title')
    title = normalise(title_tag.get_text(' ', strip=True)) if title_tag else source['id']
    sections, heading, lead, units = [], 'Overview', None, []
    skipping = False

    def close():
        if units and not skipping:
            sections.append({'heading': heading, 'units': list(units)})

    for element in main.find_all(['h2', 'h3', 'p', 'li']):
        if element.name in ('h2', 'h3'):
            close()
            heading = normalise(element.get_text(' ', strip=True)) or 'Section'
            skipping = bool(SKIP_HEADINGS.match(heading))
            units, lead = [], None
            continue
        if element.name == 'p' and element.find_parent('li'):
            continue
        text = li_text(element) if element.name == 'li' else normalise(element.get_text(' ', strip=True))
        if len(text) < 3 or re.match(r'^(page last reviewed|next review due)', text, re.I) or CREDIT.search(text):
            continue
        if element.name == 'li':
            units.append({'text': text, 'kind': 'list_item', 'lead': lead})
        else:
            units.append({'text': text, 'kind': 'paragraph', 'lead': None})
            lead = text if text.endswith(':') else None
    close()
    chunks = []
    for section in sections:
        bucket, size, part = [], 0, 0
        for unit in section['units']:
            if bucket and size + len(unit['text']) > 1400:
                chunks.append((section['heading'], bucket, part)); bucket, size, part = [], 0, part + 1
            bucket.append(unit); size += len(unit['text'])
        if bucket:
            chunks.append((section['heading'], bucket, part))
    out, used = [], {}
    for heading, bucket, part in chunks:
        text = ' '.join(unit['text'] for unit in bucket)
        screening = screen_untrusted(text)
        base = f"{source['id']}#{slug(heading)}{'-' + str(part) if part else ''}"
        used[base] = used.get(base, 0) + 1
        care = next((level for pattern, level in CARE_LEVEL if pattern.search(heading)), None)
        out.append({
            'id': base if used[base] == 1 else f'{base}~{used[base]}',
            'source_id': source['id'], 'heading': heading, 'care_level': care, 'units': bucket, 'text': text, 'sha256': sha(text),
            'injection_flags': screening['flags'],
        })
    return {'title': title, 'final_url': final_url, 'dates': dates, 'published': published, 'chunks': out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--delay', type=float, default=0.6)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    previous = json.loads(SNAPSHOT.read_text(encoding='utf-8')) if SNAPSHOT.exists() else {'sources': {}, 'chunks': [], 'retired': []}
    if args.check:
        problems = validate(previous, registry)
        print(json.dumps({'snapshot': previous.get('version'), 'problems': problems}, indent=1))
        sys.exit(1 if problems else 0)
    import httpx
    only = {item for item in args.only.split(',') if item}
    hosts = set(registry['policy']['allowed_hosts'])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    old_chunks = {chunk['id']: chunk for chunk in previous['chunks']}
    sources_meta = dict(previous.get('sources', {}))
    new_chunks = [chunk for chunk in previous['chunks'] if only and chunk['source_id'] not in only]
    retired = list(previous.get('retired', []))
    report = {'fetched': [], 'failed': [], 'added': 0, 'changed': 0, 'retired': 0, 'unchanged': 0, 'duplicates': 0}
    registry_ids = {source['id'] for source in registry['sources']}
    with httpx.Client(timeout=20, follow_redirects=False, headers={'User-Agent': 'HumanTwin-KnowledgeIngest/1.0 (research prototype; approved-source registry)'}) as client:
        for source in registry['sources']:
            if only and source['id'] not in only:
                continue
            if source.get('status', 'active') != 'active':
                continue
            publisher = registry['publishers'][source['publisher']]
            try:
                final_url, html = fetch(client, source['url'], hosts)
                page = extract(source, final_url, html)
                if not page['chunks']:
                    raise ValueError('no usable content')
            except Exception as error:  # keep the previous version, mark it stale
                report['failed'].append({'id': source['id'], 'error': str(error)[:160]})
                meta = sources_meta.get(source['id'])
                if meta:
                    meta['fetch_status'] = 'failed'; meta['stale_since'] = meta.get('stale_since') or now
                new_chunks.extend(chunk for chunk in previous['chunks'] if chunk['source_id'] == source['id'])
                time.sleep(args.delay)
                continue
            report['fetched'].append(source['id'])
            for chunk in page['chunks']:
                prior = old_chunks.get(chunk['id'])
                if prior and prior['sha256'] == chunk['sha256']:
                    chunk['first_seen'] = prior['first_seen']; report['unchanged'] += 1
                else:
                    chunk['first_seen'] = now
                    if prior:
                        retired.append({'id': prior['id'], 'sha256': prior['sha256'], 'retired_at': now, 'reason': 'content changed at source'}); report['changed'] += 1
                    else:
                        report['added'] += 1
                new_chunks.append(chunk)
            current_ids = {chunk['id'] for chunk in page['chunks']}
            for prior in previous['chunks']:
                if prior['source_id'] == source['id'] and prior['id'] not in current_ids:
                    retired.append({'id': prior['id'], 'sha256': prior['sha256'], 'retired_at': now, 'reason': 'section removed at source'}); report['retired'] += 1
            content_hash = sha(''.join(chunk['sha256'] for chunk in page['chunks']))
            prior_meta = sources_meta.get(source['id'], {})
            sources_meta[source['id']] = {
                'id': source['id'], 'title': page['title'], 'publisher': publisher['name'], 'publisher_id': source['publisher'],
                'tier': publisher['tier'], 'url': page['final_url'], 'registry_url': source['url'],
                'publication_date': page['published'], 'last_reviewed': page['dates'].get('last_reviewed') or page['dates'].get('last_updated'),
                'next_review_due': page['dates'].get('next_review_due'), 'retrieved_at': now, 'usage_rights': publisher['usage_rights'],
                'anatomy': source['anatomy'], 'content_sha256': content_hash,
                'version': prior_meta.get('version', 0) + (1 if prior_meta.get('content_sha256') != content_hash else 0),
                'fetch_status': 'ok', 'stale_since': None, 'status': 'active',
            }
            time.sleep(args.delay)
    for source_id in list(sources_meta):
        if source_id not in registry_ids:
            for chunk in [c for c in new_chunks if c['source_id'] == source_id]:
                retired.append({'id': chunk['id'], 'sha256': chunk['sha256'], 'retired_at': now, 'reason': 'source removed from registry'}); report['retired'] += 1
            new_chunks = [c for c in new_chunks if c['source_id'] != source_id]
            sources_meta[source_id]['status'] = 'retired'
    seen = {}
    for chunk in new_chunks:
        if chunk['sha256'] in seen and seen[chunk['sha256']] != chunk['id']:
            chunk['duplicate_of'] = seen[chunk['sha256']]; report['duplicates'] += 1
        else:
            chunk.pop('duplicate_of', None); seen[chunk['sha256']] = chunk['id']
    new_chunks.sort(key=lambda chunk: chunk['id'])
    corpus_hash = sha(''.join(chunk['sha256'] for chunk in new_chunks))
    snapshot = {
        'schema_version': 'humantwin-clinical-snapshot-v1',
        'version': f'clinical-knowledge-{date.today().isoformat()}.{corpus_hash[:8]}',
        'registry_version': registry['version'], 'built_at': now, 'corpus_sha256': corpus_hash,
        'untrusted_content_notice': registry['policy']['untrusted_content'],
        'sources': dict(sorted(sources_meta.items())), 'chunks': new_chunks, 'retired': retired[-2000:],
    }
    problems = validate(snapshot, registry)
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    report.update({'version': snapshot['version'], 'active_chunks': len(new_chunks), 'problems': problems})
    print(json.dumps(report, indent=1))


def validate(snapshot, registry):
    problems = []
    ids = [chunk['id'] for chunk in snapshot['chunks']]
    if len(ids) != len(set(ids)):
        problems.append('duplicate chunk ids')
    for chunk in snapshot['chunks']:
        if sha(chunk['text']) != chunk['sha256']:
            problems.append(f"hash mismatch {chunk['id']}")
        if chunk['source_id'] not in snapshot['sources']:
            problems.append(f"orphan chunk {chunk['id']}")
    for source in registry['sources']:
        if source['id'] not in snapshot['sources']:
            problems.append(f"missing source {source['id']}")
    return problems


if __name__ == '__main__':
    main()
