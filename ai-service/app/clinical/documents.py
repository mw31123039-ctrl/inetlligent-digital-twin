"""Report extraction with source location: page number, character offsets and the exact text.

Supported input: UTF-8 plain text (pages separated by form feed) and PDF *only* when the optional `pypdf`
package is installed (text layer only; scanned PDFs need OCR, which is not bundled). Every extracted item is
`pending_confirmation`: nothing enters the patient record until the patient or a clinician confirms it.
Document text is untrusted: instruction-like lines are flagged and never become extracted items.
"""
import hashlib
import io
import re

from pydantic import BaseModel, ConfigDict, Field

from .untrusted import clean, overlaps_flag, screen_untrusted

MAX_PAGES = 40
MAX_CHARS = 200_000


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=1, max_length=200)
    media_type: str = Field(pattern=r'^(text/plain|application/pdf)$')
    content_base64: str = Field(min_length=4, max_length=7_000_000)


class Location(BaseModel):
    model_config = ConfigDict(extra='forbid')
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    line: int = Field(ge=1)


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    kind: str
    label: str
    value: str | None
    text: str
    location: Location
    certainty: str
    status: str = 'pending_confirmation'


class ExtractResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: str = 'humantwin-report-extraction-v1'
    document_sha256: str
    pages: int
    characters: int
    items: list[ExtractedItem]
    injection_flags: list[dict]
    unsupported_reason: str | None
    method: str
    clinical_validation: bool = False


MEDICATION = re.compile(r'\b([A-Z][a-z]{3,}(?:in|ol|am|ide|ine|ate|one|pril|sartan|statin|mab|cillin|mycin|azole|prazole|olol|pine|done|xetine))\b\s*(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?))?', re.UNICODE)
PATTERNS = [
    ('allergy', re.compile(r'(?im)^\s*(?:known\s+)?allerg(?:y|ies)\s*[:\-]\s*(?P<value>[^\n]{2,120})$'), 'labelled'),
    ('allergy', re.compile(r'(?i)\ballergic to (?P<value>[a-z][a-z \-]{2,60})'), 'phrase'),
    ('diagnosis', re.compile(r'(?im)^\s*(?:diagnosis|impression|assessment|conclusion)\s*[:\-]\s*(?P<value>[^\n]{3,200})$'), 'labelled'),
    ('medication_list', re.compile(r'(?im)^\s*(?:medications?|current medicines|drugs|rx)\s*[:\-]\s*(?P<value>[^\n]{2,200})$'), 'labelled'),
    ('blood_pressure', re.compile(r'(?i)\b(?:bp|blood pressure)\s*[:=]?\s*(?P<value>\d{2,3}\s*/\s*\d{2,3})\s*(?:mm\s*hg)?'), 'measurement'),
    ('heart_rate', re.compile(r'(?i)\b(?:hr|heart rate|pulse)\s*[:=]?\s*(?P<value>\d{2,3})\s*(?:bpm|/min)?\b'), 'measurement'),
    ('temperature', re.compile(r'(?i)\b(?:temp(?:erature)?)\s*[:=]?\s*(?P<value>\d{2}(?:\.\d)?)\s*°?\s*c\b'), 'measurement'),
    ('intraocular_pressure', re.compile(r'(?i)\b(?:iop|intra-?ocular pressure)\s*[:=]?\s*(?P<value>(?:(?:r|l|od|os)\s*\d{1,2}\s*[,/;]?\s*){1,2})\s*(?:mm\s*hg)?'), 'measurement'),
    ('visual_acuity', re.compile(r'(?i)\b(?:va|visual acuity)\s*[:=]?\s*(?P<value>(?:\d{1,2}/\d{1,3}\s*[,;]?\s*){1,2})'), 'measurement'),
    ('hba1c', re.compile(r'(?i)\bhba1c\s*[:=]?\s*(?P<value>\d{1,3}(?:\.\d)?\s*(?:%|mmol/mol))'), 'measurement'),
    ('tooth', re.compile(r'(?i)\b(?:tooth|fdi)\s*#?\s*(?P<value>[1-4][1-8])\b'), 'labelled'),
]


def _pages_from_pdf(raw: bytes):
    try:
        from pypdf import PdfReader  # optional dependency
    except ImportError:
        return None, 'PDF text extraction needs the optional `pypdf` package on the private AI service. Upload a text export instead.'
    reader = PdfReader(io.BytesIO(raw))
    if len(reader.pages) > MAX_PAGES:
        return None, f'Only reports up to {MAX_PAGES} pages are supported.'
    pages = [(page.extract_text() or '') for page in reader.pages]
    if not any(p.strip() for p in pages):
        return None, 'No text layer was found. Scanned reports need OCR, which is not installed.'
    return pages, None


def extract_report(raw: bytes, media_type: str) -> ExtractResult:
    digest = hashlib.sha256(raw).hexdigest()
    if media_type == 'application/pdf':
        if not raw.startswith(b'%PDF-'):
            return ExtractResult(document_sha256=digest, pages=0, characters=0, items=[], injection_flags=[], unsupported_reason='The file is not a PDF.', method='none')
        pages, reason = _pages_from_pdf(raw)
        if pages is None:
            return ExtractResult(document_sha256=digest, pages=0, characters=0, items=[], injection_flags=[], unsupported_reason=reason, method='none')
        method = 'pdf-text-layer'
    else:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            return ExtractResult(document_sha256=digest, pages=0, characters=0, items=[], injection_flags=[], unsupported_reason='Text reports must be UTF-8.', method='none')
        pages = text.split('\f')[:MAX_PAGES]
        method = 'plain-text'
    items, flags, total = [], [], 0
    for page_number, page in enumerate(pages, start=1):
        page = clean(page)[:MAX_CHARS]
        total += len(page)
        screening = screen_untrusted(page)
        for span in screening['spans']:
            line = page.count('\n', 0, span['start']) + 1
            flags.append({'page': page_number, 'line': line, 'type': span['type'], 'text': page[span['start']:span['end']][:160]})
        flagged_lines = {page.count('\n', 0, span['start']) for span in screening['spans']}

        def on_flagged_line(start):
            return page.count('\n', 0, start) in flagged_lines

        for kind, pattern, certainty in PATTERNS:
            for match in pattern.finditer(page):
                start, end = match.span()
                if overlaps_flag(start, end, screening['spans']) or on_flagged_line(start):
                    continue
                value = re.sub(r'\s+', ' ', match.group('value')).strip(' .;,')
                items.append(ExtractedItem(id=f'{kind}:{page_number}:{start}', kind=kind, label=kind.replace('_', ' '), value=value, text=page[start:end].strip(),
                                           location=Location(page=page_number, start=start, end=end, line=page.count('\n', 0, start) + 1),
                                           certainty='pattern-matched (verify against the report)' if certainty != 'labelled' else 'labelled field (verify against the report)'))
        for match in MEDICATION.finditer(page):
            start, end = match.span()
            if overlaps_flag(start, end, screening['spans']) or on_flagged_line(start) or not match.group(2):
                continue  # a drug-like word without a dose is too uncertain to propose
            items.append(ExtractedItem(id=f'medication:{page_number}:{start}', kind='medication', label='medication', value=match.group(0).strip(), text=match.group(0).strip(),
                                       location=Location(page=page_number, start=start, end=end, line=page.count('\n', 0, start) + 1), certainty='name and dose pattern (verify against the report)'))
    seen, unique = set(), []
    for item in items:
        key = (item.kind, item.location.page, item.location.start)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return ExtractResult(document_sha256=digest, pages=len(pages), characters=total, items=unique[:200], injection_flags=flags[:50], unsupported_reason=None, method=method)
