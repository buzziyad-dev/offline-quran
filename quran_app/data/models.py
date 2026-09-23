"""
Data models for the Quran Desktop App.

These are plain dataclasses mirroring schema.sql. Kept dependency-free
(no ORM) so the data layer stays easy to read and test — consistent
with the project's goal of being a learning-friendly codebase.
"""

from dataclasses import dataclass, field
from enum import Enum


class RevelationType(str, Enum):
    MECCAN = "meccan"
    MEDINAN = "medinan"


@dataclass(frozen=True)
class Surah:
    surah_number: int
    name_arabic: str
    name_english: str
    name_transliteration: str | None
    ayah_count: int
    revelation_type: RevelationType

    def __post_init__(self) -> None:
        # Allow construction from JSON where revelation_type is a plain string
        if isinstance(self.revelation_type, str):
            object.__setattr__(self, "revelation_type", RevelationType(self.revelation_type))


@dataclass(frozen=True)
class Ayah:
    surah_number: int
    ayah_number: int
    text_uthmani: str
    text_search: str | None = None


@dataclass(frozen=True)
class TranslationSource:
    id: int
    slug: str
    display_name: str
    language: str
    license: str | None = None
    attribution: str | None = None


@dataclass(frozen=True)
class Translation:
    translation_source_id: int
    surah_number: int
    ayah_number: int
    text: str


@dataclass(frozen=True)
class AyahTimestamp:
    ayah_number: int
    start_ms: int


@dataclass(frozen=True)
class AudioFile:
    reciter_id: str
    relative_path: str
    surah_number: int
    ayah_start: int
    ayah_end: int
    duration_ms: int | None = None
    checksum_sha256: str | None = None
    ayah_timestamps: list[AyahTimestamp] = field(default_factory=list)

    def covers_ayah(self, ayah_number: int) -> bool:
        """True if this audio file's range includes the given ayah."""
        return self.ayah_start <= ayah_number <= self.ayah_end


@dataclass(frozen=True)
class Reciter:
    id: str
    name: str
    name_arabic: str | None
    audio_format: str
    source_attribution: str | None = None
    license: str | None = None
    files: list[AudioFile] = field(default_factory=list)

    def find_audio_for(self, surah_number: int, ayah_number: int) -> AudioFile | None:
        """Look up which audio file (if any) covers a given verse."""
        for f in self.files:
            if f.surah_number == surah_number and f.covers_ayah(ayah_number):
                return f
        return None


@dataclass
class Bookmark:
    surah_number: int
    ayah_number: int
    note: str | None = None
    id: int | None = None  # set once persisted


@dataclass
class MemorizationProgress:
    surah_number: int
    ayah_number: int
    repeat_count_target: int = 0
    repeat_count_done: int = 0
    mastered: bool = False
