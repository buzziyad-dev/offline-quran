"""
Repository layer for Quran data.

Provides typed query methods over the SQLite Database.
Mirrors spec §4 (repository.py) and §3.7 testing requirements.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from .db import Database
from .models import (
    Ayah,
    Bookmark,
    MemorizationProgress,
    Reciter,
    AudioFile,
    AyahTimestamp,
    Surah,
    Translation,
    TranslationSource,
    RevelationType,
)
from .text_utils import normalize_search_query


def _row_to_surah(row: sqlite3.Row) -> Surah:
    return Surah(
        surah_number=row["surah_number"],
        name_arabic=row["name_arabic"],
        name_english=row["name_english"],
        name_transliteration=row["name_transliteration"],
        ayah_count=row["ayah_count"],
        revelation_type=RevelationType(row["revelation_type"]),
    )


def _row_to_ayah(row: sqlite3.Row) -> Ayah:
    return Ayah(
        surah_number=row["surah_number"],
        ayah_number=row["ayah_number"],
        text_uthmani=row["text_uthmani"],
        text_search=row["text_search"],
    )


class QuranRepository:
    """Query layer for Quran text, translations, and user data."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- Surahs --

    def get_all_surahs(self) -> list[Surah]:
        rows = self.db.fetchall("SELECT * FROM surahs ORDER BY surah_number")
        return [_row_to_surah(r) for r in rows]

    def get_surah(self, surah_number: int) -> Optional[Surah]:
        row = self.db.fetchone("SELECT * FROM surahs WHERE surah_number = ?", (surah_number,))
        return _row_to_surah(row) if row else None

    def search_surahs(self, query: str) -> list[Surah]:
        """Search surahs by Arabic/English/transliteration name or number (LIKE, case-insensitive)."""
        q = query.strip()
        like = f"%{q}%"
        if q.isdigit():
            rows = self.db.fetchall(
                """
                SELECT * FROM surahs
                WHERE surah_number = ? OR name_arabic LIKE ? OR name_english LIKE ? OR COALESCE(name_transliteration,'') LIKE ?
                ORDER BY surah_number
                """,
                (int(q), like, like, like),
            )
        else:
            rows = self.db.fetchall(
                """
                SELECT * FROM surahs
                WHERE name_arabic LIKE ? OR name_english LIKE ? OR COALESCE(name_transliteration,'') LIKE ?
                ORDER BY surah_number
                """,
                (like, like, like),
            )
        return [_row_to_surah(r) for r in rows]

    # -- Ayahs --

    def get_ayahs(self, surah_number: int) -> list[Ayah]:
        rows = self.db.fetchall(
            "SELECT * FROM ayahs WHERE surah_number = ? ORDER BY ayah_number",
            (surah_number,),
        )
        return [_row_to_ayah(r) for r in rows]

    def get_ayah(self, surah_number: int, ayah_number: int) -> Optional[Ayah]:
        row = self.db.fetchone(
            "SELECT * FROM ayahs WHERE surah_number = ? AND ayah_number = ?",
            (surah_number, ayah_number),
        )
        return _row_to_ayah(row) if row else None

    def search_ayahs(self, query: str, limit: int = 50) -> list[Ayah]:
        """
        Search ayahs using the diacritic-stripped text_search column.
        Falls back to text_uthmani if text_search is NULL.
        """
        normalized = normalize_search_query(query)
        if not normalized:
            return []
        pattern = f"%{normalized}%"
        rows = self.db.fetchall(
            """
            SELECT * FROM ayahs
            WHERE COALESCE(text_search, text_uthmani) LIKE ?
            ORDER BY surah_number, ayah_number
            LIMIT ?
            """,
            (pattern, limit),
        )
        return [_row_to_ayah(r) for r in rows]

    # -- Translations --

    def get_translation_sources(self) -> list[TranslationSource]:
        rows = self.db.fetchall("SELECT * FROM translation_sources ORDER BY id")
        return [
            TranslationSource(
                id=r["id"],
                slug=r["slug"],
                display_name=r["display_name"],
                language=r["language"],
                license=r["license"],
                attribution=r["attribution"],
            )
            for r in rows
        ]

    def get_translations(
        self, surah_number: int, ayah_number: int, source_id: Optional[int] = None
    ) -> list[Translation]:
        if source_id is not None:
            rows = self.db.fetchall(
                "SELECT * FROM translations WHERE surah_number=? AND ayah_number=? AND translation_source_id=?",
                (surah_number, ayah_number, source_id),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM translations WHERE surah_number=? AND ayah_number=?",
                (surah_number, ayah_number),
            )
        return [
            Translation(
                translation_source_id=r["translation_source_id"],
                surah_number=r["surah_number"],
                ayah_number=r["ayah_number"],
                text=r["text"],
            )
            for r in rows
        ]

    def get_translations_for_surah(
        self, surah_number: int, source_id: int
    ) -> list[Translation]:
        rows = self.db.fetchall(
            "SELECT * FROM translations WHERE surah_number=? AND translation_source_id=? ORDER BY ayah_number",
            (surah_number, source_id),
        )
        return [
            Translation(
                translation_source_id=r["translation_source_id"],
                surah_number=r["surah_number"],
                ayah_number=r["ayah_number"],
                text=r["text"],
            )
            for r in rows
        ]

    # -- Bookmarks --

    def get_bookmarks(self) -> list[Bookmark]:
        rows = self.db.fetchall("SELECT * FROM bookmarks ORDER BY created_at DESC")
        return [
            Bookmark(surah_number=r["surah_number"], ayah_number=r["ayah_number"], note=r["note"], id=r["id"])
            for r in rows
        ]

    def add_bookmark(self, surah_number: int, ayah_number: int, note: Optional[str] = None) -> int:
        cur = self.db.execute(
            "INSERT INTO bookmarks (surah_number, ayah_number, note) VALUES (?, ?, ?)",
            (surah_number, ayah_number, note),
        )
        self.db.connect().commit()
        return int(cur.lastrowid or 0)

    def remove_bookmark(self, bookmark_id: int) -> None:
        self.db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        self.db.connect().commit()

    # -- Last position --

    def get_last_position(self) -> Optional[tuple[int, int]]:
        row = self.db.fetchone("SELECT surah_number, ayah_number FROM last_position WHERE id=1")
        if row and row["surah_number"] is not None:
            return (int(row["surah_number"]), int(row["ayah_number"]))
        return None

    def set_last_position(self, surah_number: int, ayah_number: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO last_position (id, surah_number, ayah_number, updated_at) VALUES (1, ?, ?, datetime('now'))",
            (surah_number, ayah_number),
        )
        self.db.connect().commit()

    # -- Memorization --

    def get_memorization(self, surah_number: int, ayah_number: int) -> Optional[MemorizationProgress]:
        row = self.db.fetchone(
            "SELECT * FROM memorization_progress WHERE surah_number=? AND ayah_number=?",
            (surah_number, ayah_number),
        )
        if not row:
            return None
        return MemorizationProgress(
            surah_number=row["surah_number"],
            ayah_number=row["ayah_number"],
            repeat_count_target=row["repeat_count_target"],
            repeat_count_done=row["repeat_count_done"],
            mastered=bool(row["mastered"]),
        )

    def upsert_memorization(self, progress: MemorizationProgress) -> None:
        self.db.execute(
            """
            INSERT OR REPLACE INTO memorization_progress
            (surah_number, ayah_number, repeat_count_target, repeat_count_done, mastered, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                progress.surah_number,
                progress.ayah_number,
                progress.repeat_count_target,
                progress.repeat_count_done,
                1 if progress.mastered else 0,
            ),
        )
        self.db.connect().commit()

    # -- Settings (key-value) --

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.db.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.db.connect().commit()


class AudioRepository:
    """Query layer for reciters and audio files."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_reciters(self) -> list[Reciter]:
        rows = self.db.fetchall("SELECT * FROM reciters ORDER BY name")
        result: list[Reciter] = []
        for r in rows:
            files = self._get_files_for_reciter(r["id"])
            result.append(
                Reciter(
                    id=r["id"],
                    name=r["name"],
                    name_arabic=r["name_arabic"],
                    audio_format=r["audio_format"],
                    source_attribution=r["source_attribution"],
                    license=r["license"],
                    files=files,
                )
            )
        return result

    def get_reciter(self, reciter_id: str) -> Optional[Reciter]:
        row = self.db.fetchone("SELECT * FROM reciters WHERE id=?", (reciter_id,))
        if not row:
            return None
        files = self._get_files_for_reciter(reciter_id)
        return Reciter(
            id=row["id"],
            name=row["name"],
            name_arabic=row["name_arabic"],
            audio_format=row["audio_format"],
            source_attribution=row["source_attribution"],
            license=row["license"],
            files=files,
        )

    def _get_files_for_reciter(self, reciter_id: str) -> list[AudioFile]:
        rows = self.db.fetchall(
            "SELECT * FROM audio_files WHERE reciter_id=? ORDER BY surah_number, ayah_start",
            (reciter_id,),
        )
        files: list[AudioFile] = []
        for r in rows:
            ts_rows = self.db.fetchall(
                "SELECT ayah_number, start_ms FROM audio_ayah_timestamps WHERE audio_file_id=? ORDER BY start_ms",
                (r["id"],),
            )
            timestamps = [AyahTimestamp(ayah_number=t["ayah_number"], start_ms=t["start_ms"]) for t in ts_rows]
            files.append(
                AudioFile(
                    reciter_id=r["reciter_id"],
                    relative_path=r["relative_path"],
                    surah_number=r["surah_number"],
                    ayah_start=r["ayah_start"],
                    ayah_end=r["ayah_end"],
                    duration_ms=r["duration_ms"],
                    checksum_sha256=r["checksum_sha256"],
                    ayah_timestamps=timestamps,
                )
            )
        return files

    def find_audio_for(self, reciter_id: str, surah_number: int, ayah_number: int) -> Optional[AudioFile]:
        """Find audio file covering given ayah for a reciter."""
        row = self.db.fetchone(
            """
            SELECT * FROM audio_files
            WHERE reciter_id=? AND surah_number=? AND ayah_start <= ? AND ayah_end >= ?
            LIMIT 1
            """,
            (reciter_id, surah_number, ayah_number, ayah_number),
        )
        if not row:
            return None
        ts_rows = self.db.fetchall(
            "SELECT ayah_number, start_ms FROM audio_ayah_timestamps WHERE audio_file_id=? ORDER BY start_ms",
            (row["id"],),
        )
        timestamps = [AyahTimestamp(ayah_number=t["ayah_number"], start_ms=t["start_ms"]) for t in ts_rows]
        return AudioFile(
            reciter_id=row["reciter_id"],
            relative_path=row["relative_path"],
            surah_number=row["surah_number"],
            ayah_start=row["ayah_start"],
            ayah_end=row["ayah_end"],
            duration_ms=row["duration_ms"],
            checksum_sha256=row["checksum_sha256"],
            ayah_timestamps=timestamps,
        )

    def get_audio_files_for_surah(self, reciter_id: str, surah_number: int) -> list[AudioFile]:
        rows = self.db.fetchall(
            "SELECT * FROM audio_files WHERE reciter_id=? AND surah_number=? ORDER BY ayah_start",
            (reciter_id, surah_number),
        )
        result: list[AudioFile] = []
        for r in rows:
            ts_rows = self.db.fetchall(
                "SELECT ayah_number, start_ms FROM audio_ayah_timestamps WHERE audio_file_id=? ORDER BY start_ms",
                (r["id"],),
            )
            timestamps = [AyahTimestamp(ayah_number=t["ayah_number"], start_ms=t["start_ms"]) for t in ts_rows]
            result.append(
                AudioFile(
                    reciter_id=r["reciter_id"],
                    relative_path=r["relative_path"],
                    surah_number=r["surah_number"],
                    ayah_start=r["ayah_start"],
                    ayah_end=r["ayah_end"],
                    duration_ms=r["duration_ms"],
                    checksum_sha256=r["checksum_sha256"],
                    ayah_timestamps=timestamps,
                )
            )
        return result
