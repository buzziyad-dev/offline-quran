"""
Audio manifest parsing and validation.

Validates manifest JSON against expected structure, surfaces diagnostics
instead of failing silently (spec §3.4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AudioFile, AyahTimestamp, Reciter


@dataclass
class ManifestResult:
    reciters: list[Reciter]
    errors: list[str]
    warnings: list[str]
    schema_version: str


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def parse_manifest(path: Path) -> ManifestResult:
    """
    Parse and validate an audio manifest file.

    Returns ManifestResult with reciters (may be partial) plus errors/warnings.
    Missing file → errors, not exception (handled gracefully per spec §3.4).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return ManifestResult(reciters=[], errors=[f"Manifest not found: {path}"], warnings=[], schema_version="")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return ManifestResult(reciters=[], errors=[f"Invalid JSON: {e}"], warnings=[], schema_version="")
    except OSError as e:
        return ManifestResult(reciters=[], errors=[f"Cannot read manifest: {e}"], warnings=[], schema_version="")

    schema_version = str(data.get("schema_version", ""))
    if not _VERSION_RE.match(schema_version):
        errors.append(f"schema_version must be semver (x.y.z), got: {schema_version!r}")

    raw_reciters = data.get("reciters")
    if not isinstance(raw_reciters, list) or len(raw_reciters) == 0:
        errors.append("reciters must be a non-empty array")
        return ManifestResult(reciters=[], errors=errors, warnings=warnings, schema_version=schema_version)

    reciters: list[Reciter] = []
    seen_paths: set[tuple[str, str]] = set()  # (reciter_id, relative_path)

    for ri, raw in enumerate(raw_reciters):
        prefix = f"reciters[{ri}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        reciter_id = raw.get("id")
        name = raw.get("name")
        audio_format = raw.get("audio_format")
        name_arabic = raw.get("name_arabic")
        files_raw = raw.get("files")

        if not isinstance(reciter_id, str) or not reciter_id.strip():
            errors.append(f"{prefix}.id: required non-empty string")
            continue
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix}.name: required non-empty string")
            continue
        if audio_format not in ("mp3", "ogg", "flac"):
            errors.append(f"{prefix}.audio_format: must be mp3/ogg/flac, got {audio_format!r}")
            continue
        if not isinstance(files_raw, list) or len(files_raw) == 0:
            errors.append(f"{prefix}.files: required non-empty array")
            continue

        audio_files: list[AudioFile] = []
        for fi, fraw in enumerate(files_raw):
            fprefix = f"{prefix}.files[{fi}]"
            if not isinstance(fraw, dict):
                errors.append(f"{fprefix}: must be an object")
                continue
            rel = fraw.get("relative_path")
            surah = fraw.get("surah")
            a_start = fraw.get("ayah_start")
            a_end = fraw.get("ayah_end")

            if not isinstance(rel, str) or not rel.strip():
                errors.append(f"{fprefix}.relative_path: required")
                continue
            if not isinstance(surah, int) or not (1 <= surah <= 114):
                errors.append(f"{fprefix}.surah: must be int 1-114, got {surah!r}")
                continue
            if not isinstance(a_start, int) or a_start < 1:
                errors.append(f"{fprefix}.ayah_start: must be int >=1")
                continue
            if not isinstance(a_end, int) or a_end < a_start:
                errors.append(f"{fprefix}.ayah_end: must be int >= ayah_start")
                continue

            key = (reciter_id, rel)
            if key in seen_paths:
                errors.append(f"{fprefix}.relative_path: duplicate {rel!r} for reciter {reciter_id!r}")
                continue
            seen_paths.add(key)

            duration_ms = fraw.get("duration_ms")
            if duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0):
                errors.append(f"{fprefix}.duration_ms: must be int >=0 if present")
                duration_ms = None

            checksum = fraw.get("checksum_sha256")
            if checksum is not None and not isinstance(checksum, str):
                warnings.append(f"{fprefix}.checksum_sha256: expected string, ignoring")
                checksum = None

            # Parse per-ayah timestamps
            timestamps: list[AyahTimestamp] = []
            ts_raw = fraw.get("ayah_timestamps_ms", [])
            if ts_raw is not None:
                if not isinstance(ts_raw, list):
                    errors.append(f"{fprefix}.ayah_timestamps_ms: must be array if present")
                else:
                    for ti, traw in enumerate(ts_raw):
                        tprefix = f"{fprefix}.ayah_timestamps_ms[{ti}]"
                        if not isinstance(traw, dict):
                            errors.append(f"{tprefix}: must be object")
                            continue
                        ayah = traw.get("ayah")
                        start_ms = traw.get("start_ms")
                        if not isinstance(ayah, int) or ayah < 1:
                            errors.append(f"{tprefix}.ayah: must be int >=1")
                            continue
                        if not isinstance(start_ms, int) or start_ms < 0:
                            errors.append(f"{tprefix}.start_ms: must be int >=0")
                            continue
                        if not (a_start <= ayah <= a_end):
                            warnings.append(f"{tprefix}.ayah {ayah} outside file range {a_start}-{a_end}")
                        timestamps.append(AyahTimestamp(ayah_number=ayah, start_ms=start_ms))
                    # Validate timestamps are sorted
                    if timestamps != sorted(timestamps, key=lambda t: t.start_ms):
                        warnings.append(f"{fprefix}.ayah_timestamps_ms: not sorted by start_ms")

            audio_files.append(
                AudioFile(
                    reciter_id=reciter_id,
                    relative_path=rel,
                    surah_number=surah,
                    ayah_start=a_start,
                    ayah_end=a_end,
                    duration_ms=duration_ms,
                    checksum_sha256=checksum,
                    ayah_timestamps=timestamps,
                )
            )

        reciters.append(
            Reciter(
                id=reciter_id,
                name=name,
                name_arabic=name_arabic if isinstance(name_arabic, str) else None,
                audio_format=audio_format,
                source_attribution=raw.get("source_attribution") if isinstance(raw.get("source_attribution"), str) else None,
                license=raw.get("license") if isinstance(raw.get("license"), str) else None,
                files=audio_files,
            )
        )

    return ManifestResult(reciters=reciters, errors=errors, warnings=warnings, schema_version=schema_version)


def validate_audio_files_exist(
    reciters: list[Reciter], audio_root: Path
) -> list[str]:
    """Check that every file referenced in manifest exists on disk. Returns missing-file messages."""
    missing: list[str] = []
    for reciter in reciters:
        for f in reciter.files:
            full = audio_root / f.relative_path
            if not full.exists():
                missing.append(f"Missing audio file: {f.relative_path} (reciter={reciter.id}, surah {f.surah_number}:{f.ayah_start}-{f.ayah_end})")
    return missing
