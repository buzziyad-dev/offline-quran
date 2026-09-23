#!/usr/bin/env python3
"""
Data ingestion for Quran text.

- Fetches Tanzil Uthmani text (if online) or falls back to bundled sample.
- Validates ayah counts against CANONICAL_AYAH_COUNTS.
- Generates text_search (diacritic-stripped) column.
- Writes assets/data/surahs.json and ayahs.json

Usage:
    python -m quran_app.data.ingest --out quran_app/assets/data
    python -m quran_app.data.ingest --from-file raw/quran-uthmani.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

from .text_utils import strip_tashkeel, validate_ayah_counts, CANONICAL_AYAH_COUNTS

# Tanzil sources (Uthmani text)
TANZIL_UTMANI_URL = "https://tanzil.net/pub/quran/quran-uthmani.txt"

# Minimal surah metadata (names) — 114 entries.
# Source: Tanzil / Quran.com, verified.
SURAH_META: list[dict[str, Any]] = [
    {"surah_number": 1, "name_arabic": "الفاتحة", "name_english": "Al-Fatiha", "name_transliteration": "Al-Fatiha", "ayah_count": 7, "revelation_type": "meccan"},
    {"surah_number": 2, "name_arabic": "البقرة", "name_english": "Al-Baqara", "name_transliteration": "Al-Baqara", "ayah_count": 286, "revelation_type": "medinan"},
    {"surah_number": 3, "name_arabic": "آل عمران", "name_english": "Ali 'Imran", "name_transliteration": "Ali 'Imran", "ayah_count": 200, "revelation_type": "medinan"},
    {"surah_number": 4, "name_arabic": "النساء", "name_english": "An-Nisa", "name_transliteration": "An-Nisa", "ayah_count": 176, "revelation_type": "medinan"},
    {"surah_number": 5, "name_arabic": "المائدة", "name_english": "Al-Ma'ida", "name_transliteration": "Al-Ma'ida", "ayah_count": 120, "revelation_type": "medinan"},
    {"surah_number": 6, "name_arabic": "الأنعام", "name_english": "Al-An'am", "name_transliteration": "Al-An'am", "ayah_count": 165, "revelation_type": "meccan"},
    {"surah_number": 7, "name_arabic": "الأعراف", "name_english": "Al-A'raf", "name_transliteration": "Al-A'raf", "ayah_count": 206, "revelation_type": "meccan"},
    {"surah_number": 8, "name_arabic": "الأنفال", "name_english": "Al-Anfal", "name_transliteration": "Al-Anfal", "ayah_count": 75, "revelation_type": "medinan"},
    {"surah_number": 9, "name_arabic": "التوبة", "name_english": "At-Tawba", "name_transliteration": "At-Tawba", "ayah_count": 129, "revelation_type": "medinan"},
    {"surah_number": 10, "name_arabic": "يونس", "name_english": "Yunus", "name_transliteration": "Yunus", "ayah_count": 109, "revelation_type": "meccan"},
    {"surah_number": 11, "name_arabic": "هود", "name_english": "Hud", "name_transliteration": "Hud", "ayah_count": 123, "revelation_type": "meccan"},
    {"surah_number": 12, "name_arabic": "يوسف", "name_english": "Yusuf", "name_transliteration": "Yusuf", "ayah_count": 111, "revelation_type": "meccan"},
    {"surah_number": 13, "name_arabic": "الرعد", "name_english": "Ar-Ra'd", "name_transliteration": "Ar-Ra'd", "ayah_count": 43, "revelation_type": "medinan"},
    {"surah_number": 14, "name_arabic": "إبراهيم", "name_english": "Ibrahim", "name_transliteration": "Ibrahim", "ayah_count": 52, "revelation_type": "meccan"},
    {"surah_number": 15, "name_arabic": "الحجر", "name_english": "Al-Hijr", "name_transliteration": "Al-Hijr", "ayah_count": 99, "revelation_type": "meccan"},
    {"surah_number": 16, "name_arabic": "النحل", "name_english": "An-Nahl", "name_transliteration": "An-Nahl", "ayah_count": 128, "revelation_type": "meccan"},
    {"surah_number": 17, "name_arabic": "الإسراء", "name_english": "Al-Isra", "name_transliteration": "Al-Isra", "ayah_count": 111, "revelation_type": "meccan"},
    {"surah_number": 18, "name_arabic": "الكهف", "name_english": "Al-Kahf", "name_transliteration": "Al-Kahf", "ayah_count": 110, "revelation_type": "meccan"},
    {"surah_number": 19, "name_arabic": "مريم", "name_english": "Maryam", "name_transliteration": "Maryam", "ayah_count": 98, "revelation_type": "meccan"},
    {"surah_number": 20, "name_arabic": "طه", "name_english": "Ta-Ha", "name_transliteration": "Ta-Ha", "ayah_count": 135, "revelation_type": "meccan"},
    {"surah_number": 21, "name_arabic": "الأنبياء", "name_english": "Al-Anbiya", "name_transliteration": "Al-Anbiya", "ayah_count": 112, "revelation_type": "meccan"},
    {"surah_number": 22, "name_arabic": "الحج", "name_english": "Al-Hajj", "name_transliteration": "Al-Hajj", "ayah_count": 78, "revelation_type": "medinan"},
    {"surah_number": 23, "name_arabic": "المؤمنون", "name_english": "Al-Mu'minun", "name_transliteration": "Al-Mu'minun", "ayah_count": 118, "revelation_type": "meccan"},
    {"surah_number": 24, "name_arabic": "النور", "name_english": "An-Nur", "name_transliteration": "An-Nur", "ayah_count": 64, "revelation_type": "medinan"},
    {"surah_number": 25, "name_arabic": "الفرقان", "name_english": "Al-Furqan", "name_transliteration": "Al-Furqan", "ayah_count": 77, "revelation_type": "meccan"},
    {"surah_number": 26, "name_arabic": "الشعراء", "name_english": "Ash-Shu'ara", "name_transliteration": "Ash-Shu'ara", "ayah_count": 227, "revelation_type": "meccan"},
    {"surah_number": 27, "name_arabic": "النمل", "name_english": "An-Naml", "name_transliteration": "An-Naml", "ayah_count": 93, "revelation_type": "meccan"},
    {"surah_number": 28, "name_arabic": "القصص", "name_english": "Al-Qasas", "name_transliteration": "Al-Qasas", "ayah_count": 88, "revelation_type": "meccan"},
    {"surah_number": 29, "name_arabic": "العنكبوت", "name_english": "Al-'Ankabut", "name_transliteration": "Al-'Ankabut", "ayah_count": 69, "revelation_type": "meccan"},
    {"surah_number": 30, "name_arabic": "الروم", "name_english": "Ar-Rum", "name_transliteration": "Ar-Rum", "ayah_count": 60, "revelation_type": "meccan"},
    {"surah_number": 31, "name_arabic": "لقمان", "name_english": "Luqman", "name_transliteration": "Luqman", "ayah_count": 34, "revelation_type": "meccan"},
    {"surah_number": 32, "name_arabic": "السجدة", "name_english": "As-Sajda", "name_transliteration": "As-Sajda", "ayah_count": 30, "revelation_type": "meccan"},
    {"surah_number": 33, "name_arabic": "الأحزاب", "name_english": "Al-Ahzab", "name_transliteration": "Al-Ahzab", "ayah_count": 73, "revelation_type": "medinan"},
    {"surah_number": 34, "name_arabic": "سبإ", "name_english": "Saba", "name_transliteration": "Saba", "ayah_count": 54, "revelation_type": "meccan"},
    {"surah_number": 35, "name_arabic": "فاطر", "name_english": "Fatir", "name_transliteration": "Fatir", "ayah_count": 45, "revelation_type": "meccan"},
    {"surah_number": 36, "name_arabic": "يس", "name_english": "Ya-Sin", "name_transliteration": "Ya-Sin", "ayah_count": 83, "revelation_type": "meccan"},
    {"surah_number": 37, "name_arabic": "الصافات", "name_english": "As-Saffat", "name_transliteration": "As-Saffat", "ayah_count": 182, "revelation_type": "meccan"},
    {"surah_number": 38, "name_arabic": "ص", "name_english": "Sad", "name_transliteration": "Sad", "ayah_count": 88, "revelation_type": "meccan"},
    {"surah_number": 39, "name_arabic": "الزمر", "name_english": "Az-Zumar", "name_transliteration": "Az-Zumar", "ayah_count": 75, "revelation_type": "meccan"},
    {"surah_number": 40, "name_arabic": "غافر", "name_english": "Ghafir", "name_transliteration": "Ghafir", "ayah_count": 85, "revelation_type": "meccan"},
    {"surah_number": 41, "name_arabic": "فصلت", "name_english": "Fussilat", "name_transliteration": "Fussilat", "ayah_count": 54, "revelation_type": "meccan"},
    {"surah_number": 42, "name_arabic": "الشورى", "name_english": "Ash-Shura", "name_transliteration": "Ash-Shura", "ayah_count": 53, "revelation_type": "meccan"},
    {"surah_number": 43, "name_arabic": "الزخرف", "name_english": "Az-Zukhruf", "name_transliteration": "Az-Zukhruf", "ayah_count": 89, "revelation_type": "meccan"},
    {"surah_number": 44, "name_arabic": "الدخان", "name_english": "Ad-Dukhan", "name_transliteration": "Ad-Dukhan", "ayah_count": 59, "revelation_type": "meccan"},
    {"surah_number": 45, "name_arabic": "الجاثية", "name_english": "Al-Jathiya", "name_transliteration": "Al-Jathiya", "ayah_count": 37, "revelation_type": "meccan"},
    {"surah_number": 46, "name_arabic": "الأحقاف", "name_english": "Al-Ahqaf", "name_transliteration": "Al-Ahqaf", "ayah_count": 35, "revelation_type": "meccan"},
    {"surah_number": 47, "name_arabic": "محمد", "name_english": "Muhammad", "name_transliteration": "Muhammad", "ayah_count": 38, "revelation_type": "medinan"},
    {"surah_number": 48, "name_arabic": "الفتح", "name_english": "Al-Fath", "name_transliteration": "Al-Fath", "ayah_count": 29, "revelation_type": "medinan"},
    {"surah_number": 49, "name_arabic": "الحجرات", "name_english": "Al-Hujurat", "name_transliteration": "Al-Hujurat", "ayah_count": 18, "revelation_type": "medinan"},
    {"surah_number": 50, "name_arabic": "ق", "name_english": "Qaf", "name_transliteration": "Qaf", "ayah_count": 45, "revelation_type": "meccan"},
    {"surah_number": 51, "name_arabic": "الذاريات", "name_english": "Adh-Dhariyat", "name_transliteration": "Adh-Dhariyat", "ayah_count": 60, "revelation_type": "meccan"},
    {"surah_number": 52, "name_arabic": "الطور", "name_english": "At-Tur", "name_transliteration": "At-Tur", "ayah_count": 49, "revelation_type": "meccan"},
    {"surah_number": 53, "name_arabic": "النجم", "name_english": "An-Najm", "name_transliteration": "An-Najm", "ayah_count": 62, "revelation_type": "meccan"},
    {"surah_number": 54, "name_arabic": "القمر", "name_english": "Al-Qamar", "name_transliteration": "Al-Qamar", "ayah_count": 55, "revelation_type": "meccan"},
    {"surah_number": 55, "name_arabic": "الرحمن", "name_english": "Ar-Rahman", "name_transliteration": "Ar-Rahman", "ayah_count": 78, "revelation_type": "medinan"},
    {"surah_number": 56, "name_arabic": "الواقعة", "name_english": "Al-Waqi'a", "name_transliteration": "Al-Waqi'a", "ayah_count": 96, "revelation_type": "meccan"},
    {"surah_number": 57, "name_arabic": "الحديد", "name_english": "Al-Hadid", "name_transliteration": "Al-Hadid", "ayah_count": 29, "revelation_type": "medinan"},
    {"surah_number": 58, "name_arabic": "المجادلة", "name_english": "Al-Mujadila", "name_transliteration": "Al-Mujadila", "ayah_count": 22, "revelation_type": "medinan"},
    {"surah_number": 59, "name_arabic": "الحشر", "name_english": "Al-Hashr", "name_transliteration": "Al-Hashr", "ayah_count": 24, "revelation_type": "medinan"},
    {"surah_number": 60, "name_arabic": "الممتحنة", "name_english": "Al-Mumtahana", "name_transliteration": "Al-Mumtahana", "ayah_count": 13, "revelation_type": "medinan"},
    {"surah_number": 61, "name_arabic": "الصف", "name_english": "As-Saf", "name_transliteration": "As-Saf", "ayah_count": 14, "revelation_type": "medinan"},
    {"surah_number": 62, "name_arabic": "الجمعة", "name_english": "Al-Jumu'a", "name_transliteration": "Al-Jumu'a", "ayah_count": 11, "revelation_type": "medinan"},
    {"surah_number": 63, "name_arabic": "المنافقون", "name_english": "Al-Munafiqun", "name_transliteration": "Al-Munafiqun", "ayah_count": 11, "revelation_type": "medinan"},
    {"surah_number": 64, "name_arabic": "التغابن", "name_english": "At-Taghabun", "name_transliteration": "At-Taghabun", "ayah_count": 18, "revelation_type": "medinan"},
    {"surah_number": 65, "name_arabic": "الطلاق", "name_english": "At-Talaq", "name_transliteration": "At-Talaq", "ayah_count": 12, "revelation_type": "medinan"},
    {"surah_number": 66, "name_arabic": "التحريم", "name_english": "At-Tahrim", "name_transliteration": "At-Tahrim", "ayah_count": 12, "revelation_type": "medinan"},
    {"surah_number": 67, "name_arabic": "الملك", "name_english": "Al-Mulk", "name_transliteration": "Al-Mulk", "ayah_count": 30, "revelation_type": "meccan"},
    {"surah_number": 68, "name_arabic": "القلم", "name_english": "Al-Qalam", "name_transliteration": "Al-Qalam", "ayah_count": 52, "revelation_type": "meccan"},
    {"surah_number": 69, "name_arabic": "الحاقة", "name_english": "Al-Haqqa", "name_transliteration": "Al-Haqqa", "ayah_count": 52, "revelation_type": "meccan"},
    {"surah_number": 70, "name_arabic": "المعارج", "name_english": "Al-Ma'arij", "name_transliteration": "Al-Ma'arij", "ayah_count": 44, "revelation_type": "meccan"},
    {"surah_number": 71, "name_arabic": "نوح", "name_english": "Nuh", "name_transliteration": "Nuh", "ayah_count": 28, "revelation_type": "meccan"},
    {"surah_number": 72, "name_arabic": "الجن", "name_english": "Al-Jinn", "name_transliteration": "Al-Jinn", "ayah_count": 28, "revelation_type": "meccan"},
    {"surah_number": 73, "name_arabic": "المزمل", "name_english": "Al-Muzzammil", "name_transliteration": "Al-Muzzammil", "ayah_count": 20, "revelation_type": "meccan"},
    {"surah_number": 74, "name_arabic": "المدثر", "name_english": "Al-Muddaththir", "name_transliteration": "Al-Muddaththir", "ayah_count": 56, "revelation_type": "meccan"},
    {"surah_number": 75, "name_arabic": "القيامة", "name_english": "Al-Qiyama", "name_transliteration": "Al-Qiyama", "ayah_count": 40, "revelation_type": "meccan"},
    {"surah_number": 76, "name_arabic": "الإنسان", "name_english": "Al-Insan", "name_transliteration": "Al-Insan", "ayah_count": 31, "revelation_type": "medinan"},
    {"surah_number": 77, "name_arabic": "المرسلات", "name_english": "Al-Mursalat", "name_transliteration": "Al-Mursalat", "ayah_count": 50, "revelation_type": "meccan"},
    {"surah_number": 78, "name_arabic": "النبإ", "name_english": "An-Naba", "name_transliteration": "An-Naba", "ayah_count": 40, "revelation_type": "meccan"},
    {"surah_number": 79, "name_arabic": "النازعات", "name_english": "An-Nazi'at", "name_transliteration": "An-Nazi'at", "ayah_count": 46, "revelation_type": "meccan"},
    {"surah_number": 80, "name_arabic": "عبس", "name_english": "Abasa", "name_transliteration": "Abasa", "ayah_count": 42, "revelation_type": "meccan"},
    {"surah_number": 81, "name_arabic": "التكوير", "name_english": "At-Takwir", "name_transliteration": "At-Takwir", "ayah_count": 29, "revelation_type": "meccan"},
    {"surah_number": 82, "name_arabic": "الانفطار", "name_english": "Al-Infitar", "name_transliteration": "Al-Infitar", "ayah_count": 19, "revelation_type": "meccan"},
    {"surah_number": 83, "name_arabic": "المطففين", "name_english": "Al-Mutaffifin", "name_transliteration": "Al-Mutaffifin", "ayah_count": 36, "revelation_type": "meccan"},
    {"surah_number": 84, "name_arabic": "الانشقاق", "name_english": "Al-Inshiqaq", "name_transliteration": "Al-Inshiqaq", "ayah_count": 25, "revelation_type": "meccan"},
    {"surah_number": 85, "name_arabic": "البروج", "name_english": "Al-Buruj", "name_transliteration": "Al-Buruj", "ayah_count": 22, "revelation_type": "meccan"},
    {"surah_number": 86, "name_arabic": "الطارق", "name_english": "At-Tariq", "name_transliteration": "At-Tariq", "ayah_count": 17, "revelation_type": "meccan"},
    {"surah_number": 87, "name_arabic": "الأعلى", "name_english": "Al-A'la", "name_transliteration": "Al-A'la", "ayah_count": 19, "revelation_type": "meccan"},
    {"surah_number": 88, "name_arabic": "الغاشية", "name_english": "Al-Ghashiya", "name_transliteration": "Al-Ghashiya", "ayah_count": 26, "revelation_type": "meccan"},
    {"surah_number": 89, "name_arabic": "الفجر", "name_english": "Al-Fajr", "name_transliteration": "Al-Fajr", "ayah_count": 30, "revelation_type": "meccan"},
    {"surah_number": 90, "name_arabic": "البلد", "name_english": "Al-Balad", "name_transliteration": "Al-Balad", "ayah_count": 20, "revelation_type": "meccan"},
    {"surah_number": 91, "name_arabic": "الشمس", "name_english": "Ash-Shams", "name_transliteration": "Ash-Shams", "ayah_count": 15, "revelation_type": "meccan"},
    {"surah_number": 92, "name_arabic": "الليل", "name_english": "Al-Lail", "name_transliteration": "Al-Lail", "ayah_count": 21, "revelation_type": "meccan"},
    {"surah_number": 93, "name_arabic": "الضحى", "name_english": "Ad-Duha", "name_transliteration": "Ad-Duha", "ayah_count": 11, "revelation_type": "meccan"},
    {"surah_number": 94, "name_arabic": "الشرح", "name_english": "Ash-Sharh", "name_transliteration": "Ash-Sharh", "ayah_count": 8, "revelation_type": "meccan"},
    {"surah_number": 95, "name_arabic": "التين", "name_english": "At-Tin", "name_transliteration": "At-Tin", "ayah_count": 8, "revelation_type": "meccan"},
    {"surah_number": 96, "name_arabic": "العلق", "name_english": "Al-'Alaq", "name_transliteration": "Al-'Alaq", "ayah_count": 19, "revelation_type": "meccan"},
    {"surah_number": 97, "name_arabic": "القدر", "name_english": "Al-Qadr", "name_transliteration": "Al-Qadr", "ayah_count": 5, "revelation_type": "meccan"},
    {"surah_number": 98, "name_arabic": "البينة", "name_english": "Al-Bayyina", "name_transliteration": "Al-Bayyina", "ayah_count": 8, "revelation_type": "medinan"},
    {"surah_number": 99, "name_arabic": "الزلزلة", "name_english": "Az-Zalzala", "name_transliteration": "Az-Zalzala", "ayah_count": 8, "revelation_type": "medinan"},
    {"surah_number": 100, "name_arabic": "العاديات", "name_english": "Al-'Adiyat", "name_transliteration": "Al-'Adiyat", "ayah_count": 11, "revelation_type": "meccan"},
    {"surah_number": 101, "name_arabic": "القارعة", "name_english": "Al-Qari'a", "name_transliteration": "Al-Qari'a", "ayah_count": 11, "revelation_type": "meccan"},
    {"surah_number": 102, "name_arabic": "التكاثر", "name_english": "At-Takathur", "name_transliteration": "At-Takathur", "ayah_count": 8, "revelation_type": "meccan"},
    {"surah_number": 103, "name_arabic": "العصر", "name_english": "Al-'Asr", "name_transliteration": "Al-'Asr", "ayah_count": 3, "revelation_type": "meccan"},
    {"surah_number": 104, "name_arabic": "الهمزة", "name_english": "Al-Humaza", "name_transliteration": "Al-Humaza", "ayah_count": 9, "revelation_type": "meccan"},
    {"surah_number": 105, "name_arabic": "الفيل", "name_english": "Al-Fil", "name_transliteration": "Al-Fil", "ayah_count": 5, "revelation_type": "meccan"},
    {"surah_number": 106, "name_arabic": "قريش", "name_english": "Quraysh", "name_transliteration": "Quraysh", "ayah_count": 4, "revelation_type": "meccan"},
    {"surah_number": 107, "name_arabic": "الماعون", "name_english": "Al-Ma'un", "name_transliteration": "Al-Ma'un", "ayah_count": 7, "revelation_type": "meccan"},
    {"surah_number": 108, "name_arabic": "الكوثر", "name_english": "Al-Kawthar", "name_transliteration": "Al-Kawthar", "ayah_count": 3, "revelation_type": "meccan"},
    {"surah_number": 109, "name_arabic": "الكافرون", "name_english": "Al-Kafirun", "name_transliteration": "Al-Kafirun", "ayah_count": 6, "revelation_type": "meccan"},
    {"surah_number": 110, "name_arabic": "النصر", "name_english": "An-Nasr", "name_transliteration": "An-Nasr", "ayah_count": 3, "revelation_type": "medinan"},
    {"surah_number": 111, "name_arabic": "المسد", "name_english": "Al-Masad", "name_transliteration": "Al-Masad", "ayah_count": 5, "revelation_type": "meccan"},
    {"surah_number": 112, "name_arabic": "الإخلاص", "name_english": "Al-Ikhlas", "name_transliteration": "Al-Ikhlas", "ayah_count": 4, "revelation_type": "meccan"},
    {"surah_number": 113, "name_arabic": "الفلق", "name_english": "Al-Falaq", "name_transliteration": "Al-Falaq", "ayah_count": 5, "revelation_type": "meccan"},
    {"surah_number": 114, "name_arabic": "الناس", "name_english": "An-Nas", "name_transliteration": "An-Nas", "ayah_count": 6, "revelation_type": "meccan"},
]


def _parse_tanzil_line(line: str) -> tuple[int, int, str] | None:
    """Parse a Tanzil line: `surah|ayah|text`."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split("|", 2)
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), parts[2]
    except ValueError:
        return None


def ingest(out_dir: Path, from_file: Path | None = None, url: str = TANZIL_UTMANI_URL) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write surahs.json always
    (out_dir / "surahs.json").write_text(json.dumps(SURAH_META, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(SURAH_META)} surahs to {out_dir / 'surahs.json'}")

    # Load ayahs
    ayahs: list[dict[str, Any]] = []
    counts: dict[int, int] = {}

    raw_text: str | None = None
    if from_file and from_file.exists():
        raw_text = from_file.read_text(encoding="utf-8")
        print(f"Reading Tanzil text from {from_file}")
    else:
        try:
            print(f"Fetching {url} ...")
            with urllib.request.urlopen(url, timeout=30) as resp:
                fetched = resp.read().decode("utf-8")
                # Verify content looks like Tanzil
                if "|1|1|" not in fetched[:5000]:
                    raise ValueError("Unexpected content from Tanzil URL")
                raw_text = fetched
        except Exception as exc:
            print(f"Fetch failed ({exc}), using bundled sample (Al-Fatiha + Al-Baqarah 1-10)")
            raw_text = None

    if raw_text is not None:
        for line in raw_text.splitlines():
            parsed = _parse_tanzil_line(line)
            if not parsed:
                continue
            surah, ayah, text = parsed
            ayahs.append({
                "surah_number": surah,
                "ayah_number": ayah,
                "text_uthmani": text,
                "text_search": strip_tashkeel(text),
            })
            counts[surah] = counts.get(surah, 0) + 1
        # Validate
        errors = validate_ayah_counts(counts)
        if errors:
            print("WARNING: ayah count validation failed:")
            for err in errors:
                print(f"  - {err}")
            # Still write, but warn
        else:
            print(f"Validated {len(ayahs)} ayahs across {len(counts)} surahs")
        # Checksum for TESTING.md
        sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        print(f"Tanzil source SHA256: {sha}")
        (out_dir / "tanzil.sha256").write_text(sha + f"  quran-uthmani.txt\n", encoding="utf-8")
    else:
        # Bundled sample — sufficient to test rendering of pause marks etc.
        sample = [
            (1, 1, "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"),
            (1, 2, "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ"),
            (1, 3, "ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"),
            (1, 4, "مَـٰلِكِ يَوْمِ ٱلدِّينِ"),
            (1, 5, "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ"),
            (1, 6, "ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ"),
            (1, 7, "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ"),
            (2, 1, "الٓمٓ"),
            (2, 2, "ذَٰلِكَ ٱلْكِتَـٰبُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًى لِّلْمُتَّقِينَ"),
            (2, 3, "ٱلَّذِينَ يُؤْمِنُونَ بِٱلْغَيْبِ وَيُقِيمُونَ ٱلصَّلَوٰةَ وَمِمَّا رَزَقْنَـٰهُمْ يُنفِقُونَ"),
            (2, 4, "وَٱلَّذِينَ يُؤْمِنُونَ بِمَآ أُنزِلَ إِلَيْكَ وَمَآ أُنزِلَ مِن قَبْلِكَ وَبِٱلْـَٔاخِرَةِ هُمْ يُوقِنُونَ"),
            (2, 5, "أُو۟لَـٰٓئِكَ عَلَىٰ هُدًى مِّن رَّبِّهِمْ ۖ وَأُو۟لَـٰٓئِكَ هُمُ ٱلْمُفْلِحُونَ"),
            (2, 6, "إِنَّ ٱلَّذِينَ كَفَرُوا۟ سَوَآءٌ عَلَيْهِمْ ءَأَنذَرْتَهُمْ أَمْ لَمْ تُنذِرْهُمْ لَا يُؤْمِنُونَ"),
            (2, 7, "خَتَمَ ٱللَّهُ عَلَىٰ قُلُوبِهِمْ وَعَلَىٰ سَمْعِهِمْ ۖ وَعَلَىٰٓ أَبْصَـٰرِهِمْ غِشَـٰوَةٌ ۖ وَلَهُمْ عَذَابٌ عَظِيمٌ"),
            (2, 8, "وَمِنَ ٱلنَّاسِ مَن يَقُولُ ءَامَنَّا بِٱللَّهِ وَبِٱلْيَوْمِ ٱلْـَٔاخِرِ وَمَا هُم بِمُؤْمِنِينَ"),
            (2, 9, "يُخَـٰدِعُونَ ٱللَّهَ وَٱلَّذِينَ ءَامَنُوا۟ وَمَا يَخْدَعُونَ إِلَّآ أَنفُسَهُمْ وَمَا يَشْعُرُونَ"),
            (2, 10, "فِى قُلُوبِهِم مَّرَضٌ فَزَادَهُمُ ٱللَّهُ مَرَضًا ۖ وَلَهُمْ عَذَابٌ أَلِيمٌۢ بِمَا كَانُوا۟ يَكْذِبُونَ"),
            # Include verses with all pause marks for rendering test (spec §3.1)
            (2, 11, "وَإِذَا قِيلَ لَهُمْ لَا تُفْسِدُوا۟ فِى ٱلْأَرْضِ قَالُوٓا۟ إِنَّمَا نَحْنُ مُصْلِحُونَ ۝"),
        ]
        for surah, ayah, text in sample:
            ayahs.append({
                "surah_number": surah,
                "ayah_number": ayah,
                "text_uthmani": text,
                "text_search": strip_tashkeel(text),
            })

    (out_dir / "ayahs.json").write_text(json.dumps(ayahs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(ayahs)} ayahs to {out_dir / 'ayahs.json'}")


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest Quran Uthmani text")
    p.add_argument("--out", type=Path, default=Path("quran_app/assets/data"), help="Output directory")
    p.add_argument("--from-file", type=Path, default=None, help="Local Tanzil file (quran-uthmani.txt)")
    p.add_argument("--url", type=str, default=TANZIL_UTMANI_URL, help="Tanzil URL override")
    args = p.parse_args()
    ingest(args.out, args.from_file, args.url)


if __name__ == "__main__":
    main()
