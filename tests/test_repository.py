import tempfile
from pathlib import Path
import json

from quran_app.data.db import Database, initialize_database, seed_surahs, seed_ayahs, seed_translation_sources, seed_translations
from quran_app.data.repository import QuranRepository
from quran_app.data.models import Surah, Ayah, TranslationSource, Translation, RevelationType


def _make_db() -> Database:
    db = Database(Path(tempfile.mktemp(suffix=".db")))
    initialize_database(db)
    return db


def test_verse_lookup_by_surah_ayah():
    db = _make_db()
    surahs = [Surah(1, "الفاتحة", "Al-Fatiha", "Al-Fatiha", 7, RevelationType.MECCAN)]
    ayahs = [
        Ayah(1, 1, "بِسْمِ ٱللَّهِ", "بسم الله"),
        Ayah(1, 2, "ٱلْحَمْدُ لِلَّهِ", "الحمد لله"),
    ]
    seed_surahs(db, surahs)
    seed_ayahs(db, ayahs)
    repo = QuranRepository(db)
    assert repo.get_ayah(1, 1).text_uthmani == "بِسْمِ ٱللَّهِ"
    assert repo.get_ayah(1, 99) is None
    assert len(repo.get_ayahs(1)) == 2
    assert repo.get_all_surahs()[0].surah_number == 1
    db.close()


def test_search_uses_text_search():
    db = _make_db()
    seed_surahs(db, [Surah(1, "الفاتحة", "Al-Fatiha", "Al-Fatiha", 7, RevelationType.MECCAN)])
    # Uthmani with tashkeel, search column normalized
    seed_ayahs(db, [Ayah(1, 2, "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ", "الحمد لله رب العلمين")])
    repo = QuranRepository(db)
    # Plain typing without tashkeel should match
    assert len(repo.search_ayahs("الحمد")) == 1
    assert len(repo.search_ayahs("ٱلْحَمْدُ")) == 1
    assert len(repo.search_ayahs("العلمين")) == 1
    assert len(repo.search_ayahs("xyz")) == 0
    db.close()


def test_search_surahs():
    db = _make_db()
    seed_surahs(db, [
        Surah(1, "الفاتحة", "Al-Fatiha", "Al-Fatiha", 7, RevelationType.MECCAN),
        Surah(2, "البقرة", "Al-Baqara", "Al-Baqara", 286, RevelationType.MEDINAN),
    ])
    repo = QuranRepository(db)
    assert len(repo.search_surahs("البقرة")) == 1
    assert len(repo.search_surahs("Fatiha")) == 1
    assert len(repo.search_surahs("2")) == 1
    db.close()


def test_translation_toggle_logic():
    db = _make_db()
    seed_surahs(db, [Surah(1, "الفاتحة", "Al-Fatiha", "Al-Fatiha", 7, RevelationType.MECCAN)])
    seed_ayahs(db, [Ayah(1, 1, "بِسْمِ", "بسم")])
    seed_translation_sources(db, [TranslationSource(1, "en_sahih", "Sahih International", "en")])
    seed_translations(db, [Translation(1, 1, 1, "In the name of Allah")])
    repo = QuranRepository(db)
    # With source filter
    assert repo.get_translations(1, 1, source_id=1)[0].text == "In the name of Allah"
    # Without filter returns same
    assert len(repo.get_translations(1, 1)) == 1
    # Wrong source returns empty
    assert repo.get_translations(1, 1, source_id=999) == []
    # No translation for other ayah
    assert repo.get_translations(1, 2) == []
    db.close()


def test_bookmarks_and_last_position():
    db = _make_db()
    repo = QuranRepository(db)
    bid = repo.add_bookmark(2, 255, note="Ayatul Kursi")
    assert bid > 0
    assert len(repo.get_bookmarks()) == 1
    repo.set_last_position(2, 255)
    assert repo.get_last_position() == (2, 255)
    repo.remove_bookmark(bid)
    assert len(repo.get_bookmarks()) == 0
    db.close()


def test_settings():
    db = _make_db()
    repo = QuranRepository(db)
    assert repo.get_setting("theme") is None
    repo.set_setting("theme", "dark")
    assert repo.get_setting("theme") == "dark"
    db.close()
