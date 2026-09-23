"""
Text utilities for Quran data.

Handles diacritic stripping for search, validation, and rendering helpers.
"""

import re
import unicodedata

# Unicode ranges for Quranic diacritics / marks to strip for search.
# Includes tashkeel, shadda, madda, hamza variants, sukun, etc., plus
# Quranic annotation marks (sajda, pause marks are kept in uthmani but stripped for search).
_TASHKEEL_RE = re.compile(
    "["
    "\u0610-\u061A"  # Quranic annotation signs
    "\u064B-\u065F"  # tashkeel: fathatan .. waqf
    "\u0670"  # dagger alif
    "\u06D6-\u06ED"  # Quranic marks (small high ligatures, pause marks)
    "]"
)

# Verse-end marker and Arabic-Indic digits are kept in display but not needed for search normalization.
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


# Normalize alef variants so plain typing ("الحمد") matches Uthmani "ٱلْحَمْدُ"
_ALIF_MAP = str.maketrans({
    "ٱ": "ا",  # alef wasla
    "إ": "ا",
    "أ": "ا",
    "آ": "ا",
    "ٲ": "ا",
})
# Also normalize teh marbuta / yeh variants for forgiving search
_EXTRA_NORMALIZE_MAP = str.maketrans({
    "ة": "ه",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
})


def strip_tashkeel(text: str) -> str:
    """
    Remove diacritics and Quranic annotation marks for search indexing.

    Keeps base Arabic letters, tatweel (ـ) is removed, and text is NFC-normalized.
    Also normalizes alef variants (ٱ إ أ آ → ا) so plain typing matches Uthmani.
    Used to populate ayahs.text_search per spec §11.
    """
    if not text:
        return ""
    # Normalize first so composed characters are consistent
    normalized = unicodedata.normalize("NFC", text)
    stripped = _TASHKEEL_RE.sub("", normalized)
    # Remove tatweel
    stripped = stripped.replace("\u0640", "")
    # Normalize alef / yeh variants
    stripped = stripped.translate(_ALIF_MAP).translate(_EXTRA_NORMALIZE_MAP)
    # Collapse whitespace
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped


def normalize_search_query(query: str) -> str:
    """Normalize user search input the same way as text_search."""
    return strip_tashkeel(query)


def to_arabic_indic(n: int) -> str:
    """Convert integer to Arabic-Indic numerals (١٢٣)."""
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def verse_end_marker(ayah_number: int) -> str:
    """Return verse-end marker ۝ + Arabic-Indic number (e.g. ۝١)."""
    return f"۝{to_arabic_indic(ayah_number)}"


# Canonical ayah counts for all 114 surahs, used for ingestion validation (spec §11).
CANONICAL_AYAH_COUNTS: dict[int, int] = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129, 10: 109,
    11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111, 18: 110, 19: 98,
    20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77, 26: 227, 27: 93, 28: 88,
    29: 69, 30: 60, 31: 34, 32: 30, 33: 73, 34: 54, 35: 45, 36: 83, 37: 182,
    38: 88, 39: 75, 40: 85, 41: 54, 42: 53, 43: 89, 44: 59, 45: 37, 46: 35,
    47: 38, 48: 29, 49: 18, 50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78,
    56: 96, 57: 29, 58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18,
    65: 12, 66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20,
    74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29, 82: 19,
    83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30, 90: 20, 91: 15,
    92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5, 98: 8, 99: 8, 100: 11,
    101: 11, 102: 8, 103: 3, 104: 9, 105: 5, 106: 4, 107: 7, 108: 3, 109: 6,
    110: 3, 111: 5, 112: 4, 113: 5, 114: 6,
}


def validate_ayah_counts(counts: dict[int, int]) -> list[str]:
    """Validate ayah counts against canonical values. Returns list of error messages."""
    errors: list[str] = []
    for surah_num, expected in CANONICAL_AYAH_COUNTS.items():
        actual = counts.get(surah_num)
        if actual is None:
            errors.append(f"Surah {surah_num}: missing (expected {expected} ayahs)")
        elif actual != expected:
            errors.append(f"Surah {surah_num}: expected {expected} ayahs, got {actual}")
    for surah_num in counts:
        if surah_num not in CANONICAL_AYAH_COUNTS:
            errors.append(f"Surah {surah_num}: unknown surah")
    return errors
