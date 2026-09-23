#!/usr/bin/env python3
"""
Database layer for Offline Quran Desktop App.

Handles SQLite initialization, schema creation, and data seeding.
Uses Python's built-in sqlite3 module (no external ORM dependency).
"""

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

from .models import (
    Surah,
    Ayah,
    TranslationSource,
    Translation,
    Reciter,
    AudioFile,
    AyahTimestamp,
    RevelationType,
)


SCHEMA_SQL = """
-- Quran Desktop App — SQLite Schema
-- Target: sqlite3 (Python stdlib). Run once at first launch via db.py seed loader.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Surah metadata
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS surahs (
    surah_number     INTEGER PRIMARY KEY CHECK (surah_number BETWEEN 1 AND 114),
    name_arabic      TEXT NOT NULL,
    name_english     TEXT NOT NULL,
    name_transliteration TEXT,
    ayah_count       INTEGER NOT NULL,
    revelation_type  TEXT NOT NULL CHECK (revelation_type IN ('meccan', 'medinan'))
);

-- ---------------------------------------------------------------------
-- Verse text (Uthmani script)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ayahs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_number     INTEGER NOT NULL REFERENCES surahs(surah_number),
    ayah_number      INTEGER NOT NULL,
    text_uthmani     TEXT NOT NULL,
    -- Optional plain-text (no diacritics) copy for search functionality,
    -- since searching diacritic-laden text is unreliable.
    text_search      TEXT,
    UNIQUE (surah_number, ayah_number)
);

CREATE INDEX IF NOT EXISTS idx_ayahs_surah ON ayahs(surah_number);

-- ---------------------------------------------------------------------
-- Translations (one row per translation source, e.g. "Saheeh International")
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS translation_sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    slug             TEXT NOT NULL UNIQUE,       -- e.g. 'saheeh_international'
    display_name     TEXT NOT NULL,
    language         TEXT NOT NULL,              -- ISO 639-1, e.g. 'en'
    license          TEXT,
    attribution      TEXT
);

CREATE TABLE IF NOT EXISTS translations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    translation_source_id INTEGER NOT NULL REFERENCES translation_sources(id),
    surah_number          INTEGER NOT NULL,
    ayah_number           INTEGER NOT NULL,
    text                  TEXT NOT NULL,
    FOREIGN KEY (surah_number, ayah_number) REFERENCES ayahs(surah_number, ayah_number),
    UNIQUE (translation_source_id, surah_number, ayah_number)
);

CREATE INDEX IF NOT EXISTS idx_translations_lookup
    ON translations(translation_source_id, surah_number, ayah_number);

-- ---------------------------------------------------------------------
-- Reciters (mirrors audio_manifest.json; DB is the queryable source of
-- truth at runtime, manifest JSON is the on-disk/import format)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reciters (
    id               TEXT PRIMARY KEY,           -- matches manifest 'id' slug
    name             TEXT NOT NULL,
    name_arabic      TEXT,
    audio_format     TEXT NOT NULL,
    source_attribution TEXT,
    license          TEXT
);

CREATE TABLE IF NOT EXISTS audio_files (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reciter_id       TEXT NOT NULL REFERENCES reciters(id),
    relative_path    TEXT NOT NULL,
    surah_number     INTEGER NOT NULL,
    ayah_start       INTEGER NOT NULL,
    ayah_end         INTEGER NOT NULL,
    duration_ms      INTEGER,
    checksum_sha256  TEXT,
    UNIQUE (reciter_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_audio_files_lookup
    ON audio_files(reciter_id, surah_number, ayah_start, ayah_end);

-- Per-ayah timestamps within a multi-ayah audio file (optional, sparse)
CREATE TABLE IF NOT EXISTS audio_ayah_timestamps (
    audio_file_id    INTEGER NOT NULL REFERENCES audio_files(id) ON DELETE CASCADE,
    ayah_number      INTEGER NOT NULL,
    start_ms         INTEGER NOT NULL,
    PRIMARY KEY (audio_file_id, ayah_number)
);

-- ---------------------------------------------------------------------
-- User data: bookmarks, last read/listen position, memorization progress
-- (not in original spec — added since these are near-universal Quran-app
-- features and cost little to schema up front)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookmarks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_number     INTEGER NOT NULL,
    ayah_number      INTEGER NOT NULL,
    note             TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS last_position (
    id               INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    surah_number     INTEGER,
    ayah_number      INTEGER,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memorization_progress (
    surah_number     INTEGER NOT NULL,
    ayah_number      INTEGER NOT NULL,
    repeat_count_target INTEGER DEFAULT 0,
    repeat_count_done   INTEGER DEFAULT 0,
    mastered         INTEGER NOT NULL DEFAULT 0 CHECK (mastered IN (0, 1)),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (surah_number, ayah_number)
);

-- ---------------------------------------------------------------------
-- App settings (key-value; simpler than a rigid settings table for a
-- small single-user desktop app)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key              TEXT PRIMARY KEY,
    value            TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- Schema versioning (for future migrations)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key              TEXT PRIMARY KEY,
    value            TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '1.0.0');
"""


class Database:
    """SQLite database wrapper with connection management."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Open database connection with row factory."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement."""
        conn = self.connect()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """Execute SQL with multiple parameter sets."""
        conn = self.connect()
        return conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Fetch a single row."""
        return self.execute(sql, params).fetchone()  # type: ignore[no-any-return]

    def fetchall(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Fetch all rows."""
        return self.execute(sql, params).fetchall()  # type: ignore[no-any-return]


def initialize_database(db: Database) -> None:
    """Create all tables and indexes from schema."""
    with db.transaction() as conn:
        conn.executescript(SCHEMA_SQL)


def get_schema_version(db: Database) -> str:
    """Get current schema version from database."""
    row = db.fetchone("SELECT value FROM schema_meta WHERE key = 'schema_version'")
    return str(row["value"]) if row else "0.0.0"


def seed_surahs(db: Database, surahs: List[Surah]) -> None:
    """Insert or update surah metadata."""
    sql = """
        INSERT OR REPLACE INTO surahs 
        (surah_number, name_arabic, name_english, name_transliteration, ayah_count, revelation_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = [
        (
            s.surah_number,
            s.name_arabic,
            s.name_english,
            s.name_transliteration,
            s.ayah_count,
            s.revelation_type.value,
        )
        for s in surahs
    ]
    with db.transaction() as conn:
        conn.executemany(sql, params)


def seed_ayahs(db: Database, ayahs: List[Ayah]) -> None:
    """Insert or update verse text."""
    sql = """
        INSERT OR REPLACE INTO ayahs 
        (surah_number, ayah_number, text_uthmani, text_search)
        VALUES (?, ?, ?, ?)
    """
    params = [
        (a.surah_number, a.ayah_number, a.text_uthmani, a.text_search)
        for a in ayahs
    ]
    with db.transaction() as conn:
        conn.executemany(sql, params)


def seed_translation_sources(db: Database, sources: List[TranslationSource]) -> None:
    """Insert or update translation sources."""
    sql = """
        INSERT OR REPLACE INTO translation_sources 
        (id, slug, display_name, language, license, attribution)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = [
        (s.id, s.slug, s.display_name, s.language, s.license, s.attribution)
        for s in sources
    ]
    with db.transaction() as conn:
        conn.executemany(sql, params)


def seed_translations(db: Database, translations: List[Translation]) -> None:
    """Insert or update translation texts."""
    sql = """
        INSERT OR REPLACE INTO translations 
        (translation_source_id, surah_number, ayah_number, text)
        VALUES (?, ?, ?, ?)
    """
    params = [
        (t.translation_source_id, t.surah_number, t.ayah_number, t.text)
        for t in translations
    ]
    with db.transaction() as conn:
        conn.executemany(sql, params)


def seed_reciters(db: Database, reciters: List[Reciter]) -> None:
    """Insert or update reciters and their audio files."""
    reciter_sql = """
        INSERT OR REPLACE INTO reciters 
        (id, name, name_arabic, audio_format, source_attribution, license)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    audio_sql = """
        INSERT OR REPLACE INTO audio_files 
        (id, reciter_id, relative_path, surah_number, ayah_start, ayah_end, duration_ms, checksum_sha256)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    timestamp_sql = """
        INSERT OR REPLACE INTO audio_ayah_timestamps 
        (audio_file_id, ayah_number, start_ms)
        VALUES (?, ?, ?)
    """

    with db.transaction() as conn:
        for reciter in reciters:
            conn.execute(reciter_sql, (
                reciter.id,
                reciter.name,
                reciter.name_arabic,
                reciter.audio_format,
                reciter.source_attribution,
                reciter.license,
            ))
            for audio_file in reciter.files:
                cursor = conn.execute(audio_sql, (
                    audio_file.id if hasattr(audio_file, 'id') and audio_file.id else None,
                    reciter.id,
                    audio_file.relative_path,
                    audio_file.surah_number,
                    audio_file.ayah_start,
                    audio_file.ayah_end,
                    audio_file.duration_ms,
                    audio_file.checksum_sha256,
                ))
                audio_file_id = cursor.lastrowid
                for ts in audio_file.ayah_timestamps:
                    conn.execute(timestamp_sql, (audio_file_id, ts.ayah_number, ts.start_ms))


def load_quran_data(db: Database, data_dir: Path) -> None:
    """
    Load Quran data from JSON files into database.
    
    Expected files in data_dir:
    - surahs.json: List of surah metadata
    - ayahs.json: List of verse texts (Uthmani)
    - translations/*.json: Translation files per source
    """
    # Load surahs
    surahs_file = data_dir / "surahs.json"
    if surahs_file.exists():
        with open(surahs_file, "r", encoding="utf-8") as f:
            surahs_data = json.load(f)
        surahs = [Surah(**s) for s in surahs_data]
        seed_surahs(db, surahs)
        print(f"Seeded {len(surahs)} surahs")

    # Load ayahs
    ayahs_file = data_dir / "ayahs.json"
    if ayahs_file.exists():
        with open(ayahs_file, "r", encoding="utf-8") as f:
            ayahs_data = json.load(f)
        ayahs = [Ayah(**a) for a in ayahs_data]
        seed_ayahs(db, ayahs)
        print(f"Seeded {len(ayahs)} ayahs")

    # Load translations
    translations_dir = data_dir / "translations"
    if translations_dir.exists():
        for trans_file in translations_dir.glob("*.json"):
            with open(trans_file, "r", encoding="utf-8") as f:
                trans_data = json.load(f)
            
            # First, ensure translation source exists
            source_info = trans_data.get("source", {})
            if source_info:
                source = TranslationSource(**source_info)
                seed_translation_sources(db, [source])
            
            # Then load translations
            translations = [Translation(**t) for t in trans_data.get("translations", [])]
            if translations:
                seed_translations(db, translations)
                print(f"Seeded {len(translations)} translations from {trans_file.stem}")


def load_audio_manifest(db: Database, manifest_path: Path) -> None:
    """Load audio manifest JSON into database."""
    if not manifest_path.exists():
        print(f"Audio manifest not found: {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    reciters = []
    for r_data in manifest.get("reciters", []):
        # Convert audio files
        audio_files = []
        for af_data in r_data.get("files", []):
            timestamps = [
                AyahTimestamp(ayah_number=ts["ayah"], start_ms=ts["start_ms"])
                for ts in af_data.get("ayah_timestamps_ms", [])
            ]
            audio_file = AudioFile(
                reciter_id=r_data["id"],
                relative_path=af_data["relative_path"],
                surah_number=af_data["surah"],
                ayah_start=af_data["ayah_start"],
                ayah_end=af_data["ayah_end"],
                duration_ms=af_data.get("duration_ms"),
                checksum_sha256=af_data.get("checksum_sha256"),
                ayah_timestamps=timestamps,
            )
            audio_files.append(audio_file)

        reciter = Reciter(
            id=r_data["id"],
            name=r_data["name"],
            name_arabic=r_data.get("name_arabic"),
            audio_format=r_data["audio_format"],
            source_attribution=r_data.get("source_attribution"),
            license=r_data.get("license"),
            files=audio_files,
        )
        reciters.append(reciter)

    if reciters:
        seed_reciters(db, reciters)
        total_files = sum(len(r.files) for r in reciters)
        print(f"Seeded {len(reciters)} reciters with {total_files} audio files")


def seed_database(db: Database, assets_dir: Path) -> None:
    """
    Full database seeding from bundled assets.
    
    Args:
        db: Database instance
        assets_dir: Path to assets directory containing data/ and audio_manifest.json
    """
    data_dir = assets_dir / "data"
    manifest_path = assets_dir / "audio_manifest.json"

    print("Initializing database schema...")
    initialize_database(db)

    print("Loading Quran text data...")
    load_quran_data(db, data_dir)

    print("Loading audio manifest...")
    load_audio_manifest(db, manifest_path)

    print("Database seeding complete!")


def get_database_path() -> Path:
    """Get the default database path in user's app data directory."""
    # On Linux: ~/.local/share/offline-quran/quran.db
    # On Windows: %APPDATA%/OfflineQuran/quran.db
    import platform
    system = platform.system()
    
    if system == "Windows":
        import os
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    
    app_dir = base / "OfflineQuran"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "quran.db"


def create_database(assets_dir: Optional[Path] = None) -> Database:
    """
    Create and initialize database.
    
    Args:
        assets_dir: Path to assets directory for seeding. If None, only schema is created.
    
    Returns:
        Initialized Database instance.
    """
    db_path = get_database_path()
    db = Database(db_path)
    
    initialize_database(db)
    
    if assets_dir and assets_dir.exists():
        seed_database(db, assets_dir)
    
    return db


if __name__ == "__main__":
    # CLI usage: python -m quran_app.data.db [assets_dir]
    import sys
    
    assets_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if assets_dir:
        assets_dir = Path(assets_dir)
    
    db = create_database(assets_dir)
    print(f"Database created at: {db.db_path}")
    print(f"Schema version: {get_schema_version(db)}")
    db.close()