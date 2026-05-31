from datetime import UTC, datetime
from pathlib import Path

from self_talk_coach.domain import DateConfidence
from self_talk_coach.ingest import (
    SUPPORTED_MEDIA_EXTENSIONS,
    build_managed_filename,
    hash_file,
    infer_session_datetime,
    iter_media_files,
)


def test_iter_media_files_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "one.mp4").write_bytes(b"video")
    (tmp_path / "two.MOV").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("not media", encoding="utf-8")

    found = [path.name for path in iter_media_files(tmp_path)]

    assert found == ["one.mp4", "two.MOV"]
    assert ".mp4" in SUPPORTED_MEDIA_EXTENSIONS


def test_hash_file_returns_sha256_hex(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"abc")

    assert hash_file(media) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_infer_session_datetime_uses_modified_time(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"abc")
    expected = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)
    timestamp = expected.timestamp()
    media.touch()
    import os

    os.utime(media, (timestamp, timestamp))

    inferred, confidence = infer_session_datetime(media)

    assert inferred == expected
    assert confidence == DateConfidence.MEDIUM


def test_build_managed_filename_uses_timestamp_and_short_hash() -> None:
    session_at = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)

    name = build_managed_filename(
        original_path=Path("random name.MP4"),
        session_at=session_at,
        content_hash="ab12cd34ef56",
    )

    assert name == "2026-05-31_2130_ab12cd34.mp4"
