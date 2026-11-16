"""Length-tracking text normalisation for English, Arabic and Sorani Kurdish.

Matching runs on a normalised copy, but every match is mapped back to the patient's original characters so
quotes and highlights always show exactly what the patient wrote.
"""
import re
import unicodedata

# One canonical form for letters that users type interchangeably on Arabic/Persian/Kurdish keyboards.
_MAP = str.maketrans({
    'ي': 'ی', 'ى': 'ی', 'ئ': 'ئ', 'ك': 'ک', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ۀ': 'ە', 'ؤ': 'ؤ',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '’': "'", '‘': "'", '`': "'", '“': '"', '”': '"', '–': '-', '—': '-',
})
_DROP = set('ـ‌‍‎‏') | {chr(c) for c in range(0x064B, 0x0653)} | {'ٰ'}
ARABIC_SCRIPT = re.compile(r'[؀-ۿ]')
LATIN = re.compile(r'[A-Za-z]')
SORANI_ONLY = re.compile(r'[ەێۆڵڕڤ]')


def normalise_char(ch: str) -> str:
    ch = ch.translate(_MAP)
    lowered = ch.lower()
    return lowered if len(lowered) == 1 else ch


def normalise_pattern(pattern: str) -> str:
    """Apply the same letter mapping to a regex pattern. Case is left alone (patterns compile with IGNORECASE)
    so escapes such as \\S or \\W keep their meaning."""
    return ''.join('' if ch in _DROP else ch.translate(_MAP) for ch in unicodedata.normalize('NFC', pattern))


class Normalised:
    """Normalised text plus a map from each normalised index to the original index."""

    def __init__(self, original: str):
        self.original = original
        chars, index = [], []
        for position, ch in enumerate(original):
            if ch in _DROP:
                continue
            for out in unicodedata.normalize('NFC', ch):
                chars.append(normalise_char(out))
                index.append(position)
        self.text = ''.join(chars)
        self.index = index

    def span(self, start: int, end: int) -> tuple[int, int]:
        if not self.index:
            return 0, 0
        start = min(max(start, 0), len(self.index) - 1)
        last = min(max(end - 1, 0), len(self.index) - 1)
        return self.index[start], self.index[last] + 1

    def quote(self, start: int, end: int) -> str:
        a, b = self.span(start, end)
        return self.original[a:b]


def languages_for(text: str) -> list[str]:
    """Pattern sets to try. Mixed-language messages try every applicable set."""
    langs = []
    if LATIN.search(text):
        langs.append('en')
    if ARABIC_SCRIPT.search(text):
        langs.extend(['ckb', 'ar'] if SORANI_ONLY.search(text) else ['ar', 'ckb'])
    return langs or ['en']


CLAUSE_SPLIT = re.compile(r'[.!?;\n،؛؟]|\bbut\b|\bhowever\b|\bلكن\b|\bبس\b|بەڵام')


def clause_bounds(text: str, position: int) -> tuple[int, int]:
    start, end = 0, len(text)
    for match in CLAUSE_SPLIT.finditer(text):
        if match.end() <= position:
            start = match.end()
        elif match.start() >= position:
            end = match.start()
            break
    return start, end
