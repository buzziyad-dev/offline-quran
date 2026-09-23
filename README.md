# Offline Quran

A fully offline desktop app for reading and listening to the Quran (Windows + Linux). Built with Python + PyQt6/PySide6, SQLite, and `python-vlc`.

## Features
- Uthmani Arabic rendering (RTL, `QTextDocument`, 16–40pt) with diacritics and pause marks
- 114 surahs, searchable by Arabic/English/name/number; diacritic-stripped search
- Quran as home with sidebar surah navigation
- Audio playback (VLC) with repeat/speed/seek, per-ayah highlighting
- Fully offline — no network calls at runtime

## Setup

```fish
# fish shell (bash: source venv/bin/activate)
source venv/bin/activate.fish
pip install -r requirements.txt

# ingest Quran text (required)
python -m quran_app.data.ingest --from-file Roadmap/quran-uthmani.txt --out quran_app/assets/data

# run (actual user experience — no dry-run mode)
python -m quran_app.main

# tests / typing
pytest tests -v
mypy quran_app/data quran_app/audio
```

On Linux you need VLC installed for audio (`sudo apt install vlc` / `sudo dnf install vlc`).

## Quran Text — Copyright & Attribution

**Source:** Tanzil Project — https://tanzil.net — Uthmani text provided as `Roadmap/quran-uthmani.txt`.

> Permission is granted to copy and distribute verbatim copies of the Quran text provided here, but changing the text is not allowed. The text can be used in any website or application, provided that its source (Tanzil Project) is clearly indicated, and a link is made to tanzil.net to enable users to keep track of changes.

This app complies as follows:

- `text_uthmani` in `quran_app/assets/data/ayahs.json` is a **verbatim copy** of `Roadmap/quran-uthmani.txt` — no edits, only an added `text_search` (diacritic-stripped) column for search per spec §11.
- Source is indicated here and in-app; see https://tanzil.net and https://tanzil.net/updates/ for updates.
- SHA256 of the ingested source is stored in `quran_app/assets/data/tanzil.sha256` (`7f30c647...` for the bundled file) — verify with `sha256sum Roadmap/quran-uthmani.txt`.
- No ayah text is modified at runtime; rendering uses `QTextDocument` to preserve ligatures/diacritics.

If you replace the text, re-run ingestion and update the checksum, and keep this attribution.

## Other Licenses
- Fonts: see `quran_app/FONT_LICENSE.md` and `Roadmap/FONT_LICENSE.md` (verify redistribution before bundling).
- Translations: see `quran_app/TRANSLATIONS.md` and `Roadmap/TRANSLATIONS.md`.

## Project Docs
Spec and schemas in `Roadmap/` (gitignored, planning only): `quran-desktop-app-spec-python.md`, `schema.sql`, `models.py`, `audio_manifest.*`, `TESTING.md`.
Progress is tracked in `Roadmap/PROGRESS.md`.
