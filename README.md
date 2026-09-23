# Offline Quran

A fully offline desktop app for reading and listening to the Quran (Windows + Linux). Built with Python + PyQt6/PySide6, SQLite, and `python-vlc`.

## Features
- Uthmani Arabic rendering (RTL, `QTextDocument`, 16–40pt) with diacritics and pause marks
- 114 surahs, searchable by Arabic/English/name/number; diacritic-stripped search
- Quran as home with sidebar surah navigation
- Audio playback (VLC) with auto-advance, per-ayah highlighting (via `ayah_timestamps_ms`), repeat/speed/seek
- Fully offline — no network calls at runtime

## Setup

```fish
# fish shell (bash: source venv/bin/activate)
source venv/bin/activate.fish
pip install -r requirements.txt

# ingest Quran text (if you replace the bundled data)
python -m quran_app.data.ingest --out quran_app/assets/data

# run
python -m quran_app.main

# tests / typing
pytest tests -v
mypy quran_app/data quran_app/audio
```

On Linux you need VLC installed for audio (`sudo apt install vlc` / `sudo dnf install vlc`).

## Quran Text — Copyright & Attribution

**Source:** Tanzil Project — https://tanzil.net — Uthmani text (6,236 ayahs).

> Permission is granted to copy and distribute verbatim copies of the Quran text provided here, but changing the text is not allowed. The text can be used in any website or application, provided that its source (Tanzil Project) is clearly indicated, and a link is made to tanzil.net to enable users to keep track of changes.

This app complies as follows:

- `text_uthmani` in `quran_app/assets/data/ayahs.json` is a **verbatim copy** of the Tanzil Uthmani text — no edits, only an added `text_search` (diacritic-stripped) column for search.
- Source is indicated here and in-app; see https://tanzil.net and https://tanzil.net/updates/ for updates.
- SHA256 of the ingested source is stored in `quran_app/assets/data/tanzil.sha256` (`7f30c647...` for the bundled file).
- No ayah text is modified at runtime; rendering uses `QTextDocument` (`QLabel` with RichText) to preserve ligatures/diacritics.

If you replace the text, re-run ingestion and update the checksum, and keep this attribution.

## Other Licenses
- Fonts: see `quran_app/FONT_LICENSE.md` (Scheherazade New + Amiri Quran, SIL OFL — bundled verbatim).
- Translations: see `quran_app/TRANSLATIONS.md`.
