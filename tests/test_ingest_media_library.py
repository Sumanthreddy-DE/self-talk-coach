from datetime import UTC, datetime
from pathlib import Path

from self_talk_coach.db import connect, get_media_file_by_hash, init_db
from self_talk_coach.domain import DateConfidence, ImportOutcome
from self_talk_coach.ingest import (
    SUPPORTED_MEDIA_EXTENSIONS,
    archived_dir_for,
    build_managed_filename,
    hash_file,
    import_inbox,
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


def test_import_inbox_moves_file_to_processed_and_records_db(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    source = paths.media_inbox / "random123.mp4"
    source.write_bytes(b"video bytes")
    expected_hash = hash_file(source)

    with connect(paths.db_path) as conn:
        init_db(conn)
        results = import_inbox(conn, paths)
        row = get_media_file_by_hash(conn, expected_hash)

    assert len(results) == 1
    assert results[0].outcome == ImportOutcome.IMPORTED
    assert not source.exists()
    assert results[0].managed_path is not None
    assert results[0].managed_path.exists()
    assert row is not None
    assert row["original_filename"] == "random123.mp4"
    assert row["status"] == "imported"


def test_import_inbox_archives_duplicate_without_second_db_row(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()

    with connect(paths.db_path) as conn:
        init_db(conn)

        first = paths.media_inbox / "first.mp4"
        first.write_bytes(b"same bytes")
        first_results = import_inbox(conn, paths)

        duplicate = paths.media_inbox / "second.mp4"
        duplicate.write_bytes(b"same bytes")
        duplicate_results = import_inbox(conn, paths)

        count = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]

    assert first_results[0].outcome == ImportOutcome.IMPORTED
    assert duplicate_results[0].outcome == ImportOutcome.DUPLICATE
    assert not duplicate.exists()
    assert duplicate_results[0].managed_path is not None
    assert duplicate_results[0].managed_path.exists()
    assert "archived" in duplicate_results[0].managed_path.parts
    assert count == 1


def test_import_inbox_moves_processed_file_to_failed_when_insert_fails(
    tmp_path: Path, monkeypatch
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    source = paths.media_inbox / "random123.mp4"
    source.write_bytes(b"video bytes")

    def fail_insert_media_file(*args, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr("self_talk_coach.ingest.insert_media_file", fail_insert_media_file)

    with connect(paths.db_path) as conn:
        init_db(conn)
        results = import_inbox(conn, paths)
        count = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]

    assert len(results) == 1
    assert results[0].outcome == ImportOutcome.FAILED
    assert not source.exists()
    assert not any(paths.media_processed.rglob("*.*"))
    assert results[0].managed_path is not None
    assert results[0].managed_path.exists()
    assert paths.media_failed in results[0].managed_path.parents
    assert count == 0
