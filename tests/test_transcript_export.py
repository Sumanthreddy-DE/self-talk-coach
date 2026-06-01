import json
from pathlib import Path

import pytest

from self_talk_coach.db import connect, init_db, insert_media_file, replace_transcript
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcript_export import (
    TranscriptExportFormat,
    export_all_transcripts,
)


def insert_media(
    conn,
    *,
    original_filename: str = "daily.mp4",
    managed_path: str = "data/media/processed/2026/05/daily.mp4",
    content_hash: str = "daily-hash",
) -> int:
    return insert_media_file(
        conn,
        original_filename=original_filename,
        original_path=f"data/media/inbox/{original_filename}",
        managed_path=managed_path,
        content_hash=content_hash,
        size_bytes=128,
        duration_seconds=1.0,
        inferred_session_at="2026-05-31T21:30:00+00:00",
        date_confidence=DateConfidence.MEDIUM,
        status=MediaStatus.TRANSCRIBED,
    )


def create_completed_transcript(conn) -> int:
    media_id = insert_media(conn)
    return replace_transcript(
        conn,
        media_file_id=media_id,
        language="de",
        model="whisper-test",
        duration_seconds=1.0,
        status=TranscriptStatus.COMPLETED,
        error_message=None,
        segments=[
            {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
        ],
    )


def test_export_all_transcripts_writes_completed_transcript_json(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        create_completed_transcript(conn)

        exported_paths = export_all_transcripts(
            conn,
            paths,
            export_format=TranscriptExportFormat.JSON,
        )

    assert exported_paths == [paths.exports_transcripts / "daily.json"]
    payload = json.loads(exported_paths[0].read_text(encoding="utf-8"))
    assert payload["media"]["original_filename"] == "daily.mp4"
    assert payload["transcript"]["language"] == "de"
    assert payload["transcript"]["model"] == "whisper-test"
    assert payload["segments"] == [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
    ]


def test_export_all_transcripts_writes_completed_transcript_markdown(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        create_completed_transcript(conn)

        exported_paths = export_all_transcripts(
            conn,
            paths,
            export_format=TranscriptExportFormat.MARKDOWN,
        )

    assert exported_paths == [paths.exports_transcripts / "daily.md"]
    markdown = exported_paths[0].read_text(encoding="utf-8")
    assert "# daily.mp4" in markdown
    assert "Model: whisper-test" in markdown
    assert "[0.00 - 1.00] Hallo." in markdown


def test_export_all_transcripts_skips_failed_transcripts(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = insert_media(
            conn,
            original_filename="failed.mp4",
            managed_path="data/media/processed/2026/05/failed.mp4",
            content_hash="failed-hash",
        )
        replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="whisper-test",
            duration_seconds=None,
            status=TranscriptStatus.FAILED,
            error_message="decode failed",
            segments=[],
        )

        exported_paths = export_all_transcripts(
            conn,
            paths,
            export_format=TranscriptExportFormat.JSON,
        )

    assert exported_paths == []
    assert not list(paths.exports_transcripts.glob("*"))


def test_export_all_transcripts_rejects_unsupported_format(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)

        with pytest.raises(ValueError, match="unsupported transcript export format"):
            export_all_transcripts(conn, paths, export_format="csv")
