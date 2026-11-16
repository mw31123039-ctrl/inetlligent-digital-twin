"""Deterministic multilingual extraction of structured findings from one patient message.

Every finding keeps the exact characters it came from (span + quote). Negated mentions become `absent`,
hedged ones `uncertain`, and past-tense context `past`, so a historical problem is never treated as current.
"""
import re
from dataclasses import dataclass, field

from .text import Normalised, clause_bounds, languages_for

GENERIC = {'pain', 'swelling', 'redness', 'lump', 'weakness', 'discharge', 'eye_dryness_grit', 'injury', 'stiffness', 'screen_use'}
SPECIFIC_PAIN = {'headache': 'body.head', 'chest_pain': 'body.chest', 'toothache': 'mouth.teeth', 'ear_pain': 'body.ears', 'sore_throat': 'neck.throat'}
WORD_BOUNDARY = '\\b'


@dataclass
class Finding:
    kind: str            # symptom | attribute | trigger | anatomy | side | answer
    key: str
    value: str = 'present'
    status: str = 'present'
    temporal: str = 'current'
    numeric: float | None = None
    start: int = 0       # original-text offsets
    end: int = 0
    quote: str = ''
    anatomy_id: str | None = None
    side: str | None = None
    extra: dict = field(default_factory=dict)


def _context_flags(kb, norm, start, end, langs):
    clause_start, clause_end = clause_bounds(norm.text, start)
    before, after, clause = norm.text[clause_start:start], norm.text[end:clause_end], norm.text[clause_start:clause_end]
    negated = uncertain = historical = False
    for lang in langs:
        neg = kb.terms['negation'][lang]
        if neg['before'].search(before) or neg['after'].search(after):
            negated = True
        if kb.terms['uncertain'][lang].search(clause):
            uncertain = True
        if kb.terms['historical'][lang].search(clause):
            historical = True
    return negated, uncertain, historical


def _overlaps(a, b):
    return a.start < b.end and b.start < a.end


def extract(kb, text: str, question: str | None = None) -> list[Finding]:
    norm = Normalised(text)
    langs = languages_for(text)
    findings: list[Finding] = []

    def add(kind, key, match, **values):
        a, b = norm.span(match.start(), match.end())
        negated, uncertain, historical = _context_flags(kb, norm, match.start(), match.end(), langs)
        status = 'absent' if negated else 'uncertain' if uncertain else 'present'
        findings.append(Finding(kind=kind, key=key, status=status, temporal='past' if historical else 'current', start=a, end=b, quote=text[a:b], **values))

    # ---------------------------------------------------------------- symptoms
    for symptom_id, by_lang in kb.terms['symptoms'].items():
        for lang in langs:
            for pattern in by_lang.get(lang, []):
                for match in pattern.finditer(norm.text):
                    add('symptom', symptom_id, match)
    # A generic word inside a more specific symptom phrase ("chest pain") is not a second symptom.
    # ("Pain spreading to my jaw" is still pain, so radiation does not swallow the generic word.)
    specific = [f for f in findings if f.kind == 'symptom' and f.key not in GENERIC and f.key != 'radiating_pain']
    findings = [f for f in findings if not (f.kind == 'symptom' and f.key in GENERIC and any(_overlaps(f, s) and s.key != f.key and (s.end - s.start) >= (f.end - f.start) for s in specific))]
    # Specific pain words also carry a located `pain` finding so pain-based rules apply to that anatomy.
    for item in list(findings):
        if item.kind == 'symptom' and item.key in SPECIFIC_PAIN:
            findings.append(Finding(kind='symptom', key='pain', status=item.status, temporal=item.temporal, start=item.start, end=item.end, quote=item.quote,
                                    anatomy_id=SPECIFIC_PAIN[item.key], extra={'derived_from': item.key}))

    # ---------------------------------------------------------------- anatomy mentions and their sides
    side_terms = kb.terms['attributes']['side']
    for anatomy_id, lang, pattern in kb.anatomy_terms:
        if lang not in langs:
            continue
        for match in pattern.finditer(norm.text):
            window_start, window_end = max(0, match.start() - 18), min(len(norm.text), match.end() + 18)
            window = norm.text[window_start:window_end]
            side = None
            for value, by_lang in side_terms.items():
                if any(p.search(window) for l2 in langs for p in by_lang.get(l2, [])):
                    side = 'both' if value == 'both' or (side and side != value) else value
            a, b = norm.span(match.start(), match.end())
            findings.append(Finding(kind='anatomy', key=anatomy_id, start=a, end=b, quote=text[a:b], anatomy_id=anatomy_id, side=side))

    # ---------------------------------------------------------------- attributes
    for name, values in kb.terms['attributes'].items():
        if name == 'side':
            continue
        for value, by_lang in values.items():
            for lang in langs:
                for pattern in by_lang.get(lang, []):
                    for match in pattern.finditer(norm.text):
                        a, b = norm.span(match.start(), match.end())
                        negated, _, historical = _context_flags(kb, norm, match.start(), match.end(), langs)
                        if negated or historical:
                            continue
                        findings.append(Finding(kind='attribute', key=name, value=value, start=a, end=b, quote=text[a:b]))
    if question in ('side', 'attr:side') or (question or '').startswith('laterality'):
        for value, by_lang in side_terms.items():
            for lang in langs:
                for pattern in by_lang.get(lang, []):
                    match = pattern.search(norm.text)
                    if match:
                        a, b = norm.span(match.start(), match.end())
                        findings.append(Finding(kind='side', key='side', value=value, start=a, end=b, quote=text[a:b]))

    # ---------------------------------------------------------------- severity
    numeric = re.search(r'(\d{1,2}(?:\.\d)?)\s*(?:/|out of|من|لە|لە کۆی)\s*10\b', norm.text)
    if numeric and float(numeric.group(1)) <= 10:
        a, b = norm.span(numeric.start(), numeric.end())
        findings.append(Finding(kind='attribute', key='severity', value=numeric.group(1), numeric=float(numeric.group(1)), start=a, end=b, quote=text[a:b]))
    elif question == 'attr:severity':
        bare = re.fullmatch(r'\s*(\d{1,2}(?:\.\d)?)\s*', norm.text)
        if bare and float(bare.group(1)) <= 10:
            findings.append(Finding(kind='attribute', key='severity', value=bare.group(1), numeric=float(bare.group(1)), start=0, end=len(text), quote=text))
    if not any(f.key == 'severity' for f in findings):
        for lang in langs:
            for pattern, value in kb.terms['severity'][lang]:
                match = pattern.search(norm.text)
                if match:
                    a, b = norm.span(match.start(), match.end())
                    findings.append(Finding(kind='attribute', key='severity', value=str(value), numeric=float(value), start=a, end=b, quote=text[a:b]))
                    break
            if any(f.key == 'severity' for f in findings):
                break

    # ---------------------------------------------------------------- duration (hours)
    duration = parse_duration(kb, norm, langs)
    if duration:
        hours, a, b = duration
        findings.append(Finding(kind='attribute', key='duration', value=str(round(hours, 2)), numeric=hours, start=a, end=b, quote=text[a:b]))

    # ---------------------------------------------------------------- triggers
    for trigger_id, by_lang in kb.terms['triggers'].items():
        for lang in langs:
            for pattern in by_lang.get(lang, []):
                for match in pattern.finditer(norm.text):
                    prefix = norm.text[max(0, match.start() - 28):match.start()]
                    if question != 'triggers' and not kb.terms['trigger_cues'][lang].search(prefix):
                        continue
                    a, b = norm.span(match.start(), match.end())
                    findings.append(Finding(kind='trigger', key=trigger_id, start=a, end=b, quote=text[a:b]))

    # ---------------------------------------------------------------- bare yes / no
    for lang in langs:
        match = kb.terms['yes'][lang].search(norm.text)
        if match:
            a, b = norm.span(match.start(), match.end())
            findings.append(Finding(kind='answer', key='yes', start=a, end=b, quote=text[a:b]))
            break
        match = kb.terms['no'][lang].search(norm.text)
        if match:
            a, b = norm.span(match.start(), match.end())
            findings.append(Finding(kind='answer', key='no', start=a, end=b, quote=text[a:b]))
            break
    if any(kb.terms['uncertain'][lang].search(norm.text) for lang in langs):
        findings.append(Finding(kind='answer', key='unsure', start=0, end=len(text), quote=text))
    return _dedupe(findings)


def parse_duration(kb, norm, langs):
    """Return (hours, start, end) for the first duration expression, using normalised patterns."""
    for lang in langs:
        spec = kb.terms['duration'][lang]
        for pattern, hours in spec['special']:
            match = pattern.search(norm.text)
            if match:
                a, b = norm.span(match.start(), match.end())
                return hours, a, b
        words = '|'.join(sorted((re.escape(w) for w in spec['numbers']), key=len, reverse=True))
        for unit_pattern, unit_hours in spec['units']:
            if lang == 'en':
                pattern = WORD_BOUNDARY + rf'(\d+(?:\.\d+)?|{words})\s*(?:-|to)?\s*(?:\d+\s*)?({unit_pattern})' + WORD_BOUNDARY
            else:
                pattern = rf'(\d+(?:\.\d+)?|{words})\s*({unit_pattern})'
            match = re.search(pattern, norm.text, re.IGNORECASE)
            if match:
                raw = match.group(1).lower()
                value = float(raw) if re.match(r'\d', raw) else float(spec['numbers'].get(raw, 1))
                a, b = norm.span(match.start(), match.end())
                return value * unit_hours, a, b
    return None


def _dedupe(findings):
    seen, out = set(), []
    for item in findings:
        key = (item.kind, item.key, item.value, item.start, item.end, item.anatomy_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
