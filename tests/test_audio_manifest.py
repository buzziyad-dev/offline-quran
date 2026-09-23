import json
import tempfile
from pathlib import Path

from quran_app.data.manifest import parse_manifest, validate_audio_files_exist


def _write_manifest(data: dict) -> Path:
    p = Path(tempfile.mktemp(suffix=".json"))
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


VALID = {
    "schema_version": "1.0.0",
    "reciters": [
        {
            "id": "test_reciter",
            "name": "Test Reciter",
            "name_arabic": "اختبار",
            "audio_format": "mp3",
            "files": [
                {
                    "relative_path": "test/001.mp3",
                    "surah": 1,
                    "ayah_start": 1,
                    "ayah_end": 7,
                    "duration_ms": 45000,
                    "ayah_timestamps_ms": [
                        {"ayah": 1, "start_ms": 0},
                        {"ayah": 2, "start_ms": 6200},
                    ],
                }
            ],
        }
    ],
}


def test_valid_manifest():
    p = _write_manifest(VALID)
    r = parse_manifest(p)
    assert r.errors == []
    assert len(r.reciters) == 1
    assert r.reciters[0].id == "test_reciter"
    assert len(r.reciters[0].files) == 1
    assert len(r.reciters[0].files[0].ayah_timestamps) == 2


def test_malformed_manifest_invalid_version():
    data = {**VALID, "schema_version": "bad"}
    p = _write_manifest(data)
    r = parse_manifest(p)
    assert any("schema_version" in e for e in r.errors)


def test_malformed_missing_fields():
    p = _write_manifest({"schema_version": "1.0.0", "reciters": [{}]})
    r = parse_manifest(p)
    assert len(r.errors) > 0


def test_missing_file():
    p = Path("/nonexistent/manifest.json")
    r = parse_manifest(p)
    assert len(r.errors) == 1
    assert "not found" in r.errors[0].lower()


def test_audio_mismatch_missing_file():
    p = _write_manifest(VALID)
    r = parse_manifest(p)
    # No file on disk
    missing = validate_audio_files_exist(r.reciters, Path(tempfile.gettempdir()))
    assert len(missing) == 1
    assert "test/001.mp3" in missing[0]
    # Create file -> no missing
    root = Path(tempfile.mkdtemp())
    (root / "test").mkdir()
    (root / "test" / "001.mp3").write_bytes(b"fake")
    missing2 = validate_audio_files_exist(r.reciters, root)
    assert missing2 == []


def test_duplicate_relative_path():
    data = {
        "schema_version": "1.0.0",
        "reciters": [
            {
                "id": "r1",
                "name": "R1",
                "name_arabic": "ر1",
                "audio_format": "mp3",
                "files": [
                    {"relative_path": "a.mp3", "surah": 1, "ayah_start": 1, "ayah_end": 1},
                    {"relative_path": "a.mp3", "surah": 1, "ayah_start": 2, "ayah_end": 2},
                ],
            }
        ],
    }
    r = parse_manifest(_write_manifest(data))
    assert any("duplicate" in e.lower() for e in r.errors)
