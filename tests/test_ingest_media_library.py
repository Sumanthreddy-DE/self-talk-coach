from datetime import UTC, datetime
from pathlib import Path

from self_talk_coach.domain import DateConfidence
from self_talk_coach.ingest import (
    SUPPORTED_MEDIA_EXTENSIONS,
    archived_dir_for,
    build_managed_filename,
    hash_file,
    infer_session_datetime,
    iter_media_files,
    move_file,
    processed_dir_for,
)
from self_talk_coach.paths import AppPaths


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


def test_processed_dir_for_uses_session_year_and_month(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    session_at = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)

    assert processed_dir_for(paths, session_at) == paths.media_processed / "2026" / "05"


def test_archived_dir_for_uses_session_year_and_month(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    session_at = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)

    assert archived_dir_for(paths, session_at) == paths.media_archived / "2026" / "05"


def test_move_file_moves_file_and_creates_destination_parent(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    destination = tmp_path / "nested" / "destination.mp4"
    source.write_bytes(b"video")

    move_file(source, destination)

    assert not source.exists()
    assert destination.read_bytes() == b"video"


def test_move_file_raises_when_destination_exists_and_preserves_files(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    destination = tmp_path / "destination.mp4"
    source.write_bytes(b"source")
    destination.write_bytes(b"destination")

    try:
        move_file(source, destination)
    except FileExistsError as error:
        assert str(destination) in str(error)
    else:
        raise AssertionError("move_file should not overwrite an existing destination")

    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"destination"
