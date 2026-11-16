"""Loads and cross-checks the versioned clinical contracts and the approved-source snapshot."""
import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .text import normalise_pattern

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / 'contracts/clinical'
SNAPSHOT = ROOT / 'ai-service/knowledge/clinical-snapshot.json'
WEIGHTS = {'typical': 3.0, 'common': 2.0, 'possible': 1.0}
AGAINST = {'strong': 4.0, 'moderate': 2.0}
_lock = threading.Lock()
_cache: dict = {}


PLAIN_WORD = re.compile(r'^[؀-ۿ ]+$')


def compile_terms(patterns, lang='en'):
    """Arabic-script terms are substring matches (prefixes/suffixes attach), but very short plain words must start
    a word so that, for example, Sorani 'لم' (sand) cannot match inside Arabic 'ألم' (pain)."""
    compiled = []
    for pattern in patterns:
        normalised = normalise_pattern(pattern)
        if lang != 'en' and PLAIN_WORD.match(normalised) and len(normalised.replace(' ', '')) <= 3:
            normalised = r'(?<![؀-ۿ])' + normalised
        compiled.append(re.compile(normalised, re.IGNORECASE))
    return compiled


@dataclass
class Binding:
    source_id: str
    chunk_id: str
    unit_index: int
    text: str
    lead: str | None


@dataclass
class KnowledgeBase:
    anatomy: dict
    anatomy_version: str
    symptoms: dict
    symptoms_doc: dict
    knowledge: dict
    registry: dict
    snapshot: dict
    chunks: dict
    conditions: list
    red_flags: dict
    unbound: list = field(default_factory=list)
    children: dict = field(default_factory=dict)
    terms: dict = field(default_factory=dict)
    anatomy_terms: list = field(default_factory=list)
    bm25: 'BM25 | None' = None
    fingerprint: str = ''
    conditions_by_id: dict = field(default_factory=dict)

    # ---------------------------------------------------------------- anatomy helpers
    def node(self, identifier):
        return self.anatomy.get(identifier)

    def ancestors(self, identifier):
        out, current = [], self.anatomy.get(identifier)
        while current and current['parent']:
            out.append(current['parent'])
            current = self.anatomy.get(current['parent'])
        return out

    def region(self, identifier):
        chain = [identifier, *self.ancestors(identifier)]
        return chain[-1] if chain and chain[-1] in self.anatomy else None

    def within(self, identifier, ancestor):
        return identifier == ancestor or ancestor in self.ancestors(identifier)

    def label(self, identifier, locale):
        node = self.anatomy.get(identifier)
        return node['label'].get(locale) or node['label']['en'] if node else identifier

    def is_lateral(self, identifier):
        node = self.anatomy.get(identifier)
        return bool(node and node['lateral'])

    # ---------------------------------------------------------------- source helpers
    def source(self, source_id):
        return self.snapshot['sources'].get(source_id)

    def review_overdue(self, source_id, today=None):
        meta = self.source(source_id) or {}
        due = meta.get('next_review_due')
        return bool(due and due < (today or date.today()).isoformat())


class BM25:
    """Small, dependency-free BM25 over snapshot chunks (text + heading + source title)."""

    def __init__(self, documents: dict[str, str], k1=1.4, b=0.72):
        self.k1, self.b = k1, b
        self.tokens = {key: self.tokenise(value) for key, value in documents.items()}
        self.lengths = {key: len(value) for key, value in self.tokens.items()}
        self.average = sum(self.lengths.values()) / max(1, len(self.lengths))
        frequency: dict[str, int] = {}
        for tokens in self.tokens.values():
            for token in set(tokens):
                frequency[token] = frequency.get(token, 0) + 1
        total = len(self.tokens)
        self.idf = {token: math.log(1 + (total - count + .5) / (count + .5)) for token, count in frequency.items()}

    STOP = set('a an and are as at be by can for from has have if in into is it its may of on or that the their they this to was were what when where which will with you your'.split())

    @classmethod
    def tokenise(cls, text):
        words = re.findall(r'[a-z]+', text.lower())
        return [w[:-1] if len(w) > 4 and w.endswith('s') else w for w in words if w not in cls.STOP and len(w) > 2]

    def score(self, query_tokens, key):
        tokens = self.tokens[key]
        if not tokens:
            return 0.0
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        value = 0.0
        for token in set(query_tokens):
            if token not in counts:
                continue
            tf = counts[token]
            value += self.idf.get(token, 0) * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.lengths[key] / self.average))
        return value


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


# English anatomy words that are something else in common phrases ("back tooth", "back of my head").
EN_ANATOMY_GUARDS = {'back': r'(?!\s+(tooth|teeth|molars?|of\b))', 'lower back': r'(?!\s+(tooth|teeth|molars?))', 'chest': r'(?!\s+of\s+drawers)'}
PREFERRED_HEADING = re.compile(r'symptom|check if|signs|feel like|main|what is|overview', re.IGNORECASE)


def bind(chunks_by_source, source_id, pattern):
    """First matching unit, preferring symptom sections, then care cards, then anything else."""
    regex = re.compile(pattern, re.IGNORECASE)
    ordered = sorted(chunks_by_source.get(source_id, []), key=lambda chunk: (0 if PREFERRED_HEADING.search(chunk['heading']) else 1 if chunk.get('care_level') else 2))
    for chunk in ordered:
        for index, unit in enumerate(chunk['units']):
            if regex.search(unit['text']):
                return Binding(source_id, chunk['id'], index, unit['text'], unit.get('lead'))
    return None


def load_kb(contracts: Path = CONTRACTS, snapshot_path: Path = SNAPSHOT) -> KnowledgeBase:
    paths = [contracts / 'anatomy.v1.json', contracts / 'symptoms.v1.json', contracts / 'knowledge.v1.json', contracts / 'sources.v1.json', snapshot_path]
    key = tuple((str(p), p.stat().st_mtime_ns) for p in paths)
    with _lock:
        if key in _cache:
            return _cache[key]
        anatomy_doc, symptoms_doc, knowledge, registry, snapshot = (_load_json(p) for p in paths)
        if anatomy_doc.get('schema_version') != 'humantwin-anatomy-v1' or symptoms_doc.get('schema_version') != 'humantwin-symptoms-v1' \
                or knowledge.get('schema_version') != 'humantwin-clinical-knowledge-v1' or snapshot.get('schema_version') != 'humantwin-clinical-snapshot-v1':
            raise ValueError('Unsupported clinical contract version.')
        anatomy = {node['id']: node for node in anatomy_doc['nodes'] if node.get('status', 'active') == 'active'}
        children: dict[str, list[str]] = {}
        for node in anatomy.values():
            if node['parent']:
                children.setdefault(node['parent'], []).append(node['id'])
        chunks = {chunk['id']: chunk for chunk in snapshot['chunks']}
        by_source: dict[str, list] = {}
        for chunk in snapshot['chunks']:
            by_source.setdefault(chunk['source_id'], []).append(chunk)
        unbound = []
        conditions = []
        for condition in knowledge['conditions']:
            item = dict(condition)
            for group in ('features', 'against'):
                resolved = []
                for feature in condition[group]:
                    binding = bind(by_source, feature['source'], feature['ev'])
                    if binding is None:
                        unbound.append(f"{condition['id']}:{group}:{feature['match']}")
                    resolved.append({**feature, 'binding': binding})
                item[group] = resolved
            conditions.append(item)
        red_flags = {}
        for rule in knowledge['red_flags']:
            binding = bind(by_source, rule['source'], rule['ev'])
            if binding is None:
                unbound.append(f"red_flag:{rule['id']}")
            red_flags[rule['id']] = {**rule, 'binding': binding}
        symptoms = {item['id']: item for item in symptoms_doc['symptoms']}
        terms = {
            'symptoms': {sid: {lang: compile_terms(patterns, lang) for lang, patterns in item['terms'].items()} for sid, item in symptoms.items()},
            'attributes': {name: {value: {lang: compile_terms(p, lang) for lang, p in spec['terms'].items()} for value, spec in attr['values'].items()} for name, attr in symptoms_doc['attributes'].items()},
            'triggers': {tid: {lang: compile_terms(p, lang) for lang, p in spec['terms'].items()} for tid, spec in symptoms_doc['triggers'].items()},
            'trigger_cues': {lang: re.compile(normalise_pattern(p), re.IGNORECASE) for lang, p in symptoms_doc['trigger_cues'].items()},
            'severity': {lang: [(re.compile(normalise_pattern(p), re.IGNORECASE), v) for p, v in items] for lang, items in symptoms_doc['severity_words'].items()},
            'negation': {lang: {k: re.compile(normalise_pattern(p), re.IGNORECASE) for k, p in spec.items()} for lang, spec in symptoms_doc['negation'].items()},
            'uncertain': {lang: re.compile(normalise_pattern(p), re.IGNORECASE) for lang, p in symptoms_doc['uncertain'].items()},
            'historical': {lang: re.compile(normalise_pattern(p), re.IGNORECASE) for lang, p in symptoms_doc['historical'].items()},
            'yes': {lang: re.compile(normalise_pattern(p), re.IGNORECASE) for lang, p in symptoms_doc['yes'].items()},
            'no': {lang: re.compile(normalise_pattern(p), re.IGNORECASE) for lang, p in symptoms_doc['no'].items()},
            'duration': {lang: {
                'special': [(re.compile(normalise_pattern(p), re.IGNORECASE), h) for p, h in symptoms_doc['duration_special'][lang]],
                'units': [(normalise_pattern(p), h) for p, h in symptoms_doc['duration_units'][lang]],
                'numbers': {normalise_pattern(w).lower(): v for w, v in symptoms_doc['number_words'][lang].items()},
            } for lang in ('en', 'ar', 'ckb')},
        }
        anatomy_terms = []
        for node in anatomy.values():
            for lang, words in node['terms'].items():
                for word in words:
                    if lang == 'en':
                        pattern = rf'\b{re.escape(word)}\b' + EN_ANATOMY_GUARDS.get(word, '')
                    else:
                        literal = re.escape(normalise_pattern(word))
                        # Anatomy words must start a word (Arabic may attach و/ب/ف/ل), so "دەست" (hand) is not found
                        # inside "ئاودەست" (toilet). Very short words must also end the word, allowing a possessive suffix.
                        start = r'(?:(?<![؀-ۿ])|(?<=(?<![؀-ۿ])[وبفل]))' if lang == 'ar' else r'(?<![؀-ۿ])'
                        end = r'(?=$|[^؀-ۿ]|[مت]|ی(?![؀-ۿ]))' if len(word.replace(' ', '')) <= 2 else ''
                        pattern = start + literal + end
                    anatomy_terms.append((node['id'], lang, re.compile(pattern, re.IGNORECASE)))
        documents = {chunk_id: f"{snapshot['sources'][chunk['source_id']]['title']} {chunk['heading']} {chunk['text']}" for chunk_id, chunk in chunks.items() if not chunk.get('duplicate_of')}
        fingerprint = hashlib.sha256(''.join(f'{p}{m}' for p, m in key).encode()).hexdigest()[:16]
        kb = KnowledgeBase(anatomy=anatomy, anatomy_version=anatomy_doc['version'], symptoms=symptoms, symptoms_doc=symptoms_doc, knowledge=knowledge,
                           registry=registry, snapshot=snapshot, chunks=chunks, conditions=conditions, red_flags=red_flags, unbound=unbound,
                           children=children, terms=terms, anatomy_terms=anatomy_terms, bm25=BM25(documents), fingerprint=fingerprint,
                           conditions_by_id={c['id']: c for c in conditions})
        _cache.clear()
        _cache[key] = kb
        return kb
