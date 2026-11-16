"""Handling for untrusted text: retrieved pages, uploaded reports, OCR output and patient free text.

The engine never executes or follows instructions found in data. This module only *flags* instruction-like
content so that (a) it is excluded from anything that could be shown as an extracted fact or citation and
(b) reviewers can see that an injection attempt was present. Detection is heuristic; the real protection
is architectural: extracted text only ever fills typed data fields and is never concatenated into rules.
"""
import re
import unicodedata

_PATTERNS = [
    ('override', r'\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|system|safety)\b.{0,30}\b(instructions?|rules?|prompts?|guidelines?)'),
    ('role', r'\b(you are now|act as|pretend to be|from now on you)\b'),
    ('system', r'(^|\s)(system|assistant|developer)\s*(prompt|message|:)'),
    ('exfiltrate', r'\b(reveal|print|show|send|email|upload)\b.{0,40}\b(prompt|api key|password|token|secret|other patients?|all (records|users))\b'),
    ('urgency_tamper', r'\b(mark|set|classify|downgrade|change)\b.{0,30}\b(urgency|triage|emergency|risk)\b.{0,20}\b(to|as)\b'),
    ('diagnosis_tamper', r'\b(diagnos(e|is)|confirm)\b.{0,30}\b(this patient|the patient|me)\b.{0,30}\b(with|as|has)\b'),
    ('markup', r'<\s*(script|iframe|img|svg|object)\b|javascript:'),
    ('ar_override', r'(تجاهل|انس|تخط).{0,30}(التعليمات|القواعد|الأوامر)'),
    ('ckb_override', r'(گوێ مەدە|پشتگوێ بخە|لەبیر بکە).{0,30}(ڕێنمایی|یاسا|فەرمان)'),
]
_COMPILED = [(name, re.compile(pattern, re.I | re.S)) for name, pattern in _PATTERNS]
_CONTROL = re.compile(r'[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁦-⁩]')


def clean(text: str) -> str:
    """Normalise Unicode and strip control / bidi-override characters (keeps ZWNJ used in Sorani)."""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('‌', '‌')  # ZWNJ is meaningful in Kurdish/Persian script; keep it.
    return _CONTROL.sub('', text)


def screen_untrusted(text: str) -> dict:
    """Return instruction-like spans. Never raises; never modifies the caller's data."""
    flags, spans = [], []
    for name, pattern in _COMPILED:
        for match in pattern.finditer(text):
            flags.append(name)
            spans.append({'type': name, 'start': match.start(), 'end': match.end()})
    return {'flags': sorted(set(flags)), 'spans': spans}


def overlaps_flag(start: int, end: int, spans: list[dict], margin: int = 0) -> bool:
    return any(start < span['end'] + margin and end > span['start'] - margin for span in spans)
