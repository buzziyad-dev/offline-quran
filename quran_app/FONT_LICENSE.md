# FONT_LICENSE.md

Document every font bundled with the app here before building any installer.

### Scheherazade New
- **Source URL:** https://software.sil.org/scheherazade/ (download https://software.sil.org/downloads/r/scheherazade/ScheherazadeNew-4.000.zip)
- **Version / date downloaded:** 4.000 / 2026-09-23
- **License type:** SIL Open Font License 1.1 with Reserved Font Name "Scheherazade"
- **License file location in repo:** `quran_app/assets/fonts/ScheherazadeNew/LICENSE` (copied from `OFL.txt`) + `OFL-FAQ.txt` in upstream zip
- **Redistribution confirmed?** Yes — OFL permits bundling verbatim as-is in installer; RFN only restricts renaming derivatives. No written confirmation needed.
- **File bundled:** `ScheherazadeNew-Regular.ttf` (316KB)
- **Notes:** Purpose-built for Quranic diacritic stacking; handles ۖ ۗ ۘ ۙ ۚ ۛ and stacked shadda+fatha. Primary in `QURAN_FONT_FAMILY`.

### Amiri Quran
- **Source URL:** https://github.com/aliftype/amiri/releases/tag/1.003 (asset `Amiri-1.003.zip`)
- **Version / date downloaded:** 1.003 / 2026-09-23
- **License type:** SIL Open Font License 1.1 with Reserved Font Name "Amiri"
- **License file location in repo:** `quran_app/assets/fonts/AmiriQuran/LICENSE` (copied from `OFL.txt`)
- **Redistribution confirmed?** Yes — OFL permits bundling verbatim. RFN restricts renaming derivatives only.
- **File bundled:** `AmiriQuran.ttf` (134KB) — distinct Quran-tuned build within Amiri project (OpenType positioning/substitution for ayah numbers ۝+numerals); do not substitute plain `Amiri-Regular.ttf`.
- **Notes:** Fallback in `QURAN_FONT_FAMILY` after Scheherazade New. Handles verse numbers via OpenType. Do not use plain `Amiri` as fallback — it lacks Quran shaping.

---

## Status
- [x] Scheherazade New — license reviewed, OFL, redistribution confirmed (bundled)
- [x] Amiri Quran — license reviewed, OFL, redistribution confirmed (bundled)
- [ ] Kitab — not bundled; deferred (would require license file review if added)
- [ ] QCF4 — **not bundled**; known historical restrictions, do not bundle without written confirmation

Do not check the acceptance criterion "Font and translation licenses documented and confirmed redistributable" in the main spec until every font actually bundled in `assets/fonts/` has a completed entry above — now satisfied for bundled fonts.
