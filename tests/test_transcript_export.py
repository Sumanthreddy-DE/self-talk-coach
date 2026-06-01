import json
import sqlite3
from pathlib import Path

import pytest

from self_talk_coach.db import connect, init_db, insert_media_file, replace_transcript
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcript_export import (
    TranscriptExportFormat,
    export_all_transcripts,
    list_completed_transcripts,
)


def insert_media(
    conn: sqlite3.Connection,
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


def create_completed_transcript(conn: sqlite3.Connection) -> tuple[int, int]:
    media_id = insert_media(conn)
    transcript_id = replace_transcript(
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
    return media_id, transcript_id


def test_list_completed_transcripts_uses_explicit_transcript_aliases(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        _, transcript_id = create_completed_transcript(conn)

        row = list_completed_transcripts(conn)[0]

    assert row["transcript_id"] == transcript_id
    assert "id" not in row.keys()
    assert "language" not in row.keys()
    assert "model" not in row.keys()


def test_export_all_transcripts_writes_completed_transcript_json(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id, transcript_id = create_completed_transcript(conn)
        transcript = conn.execute(
            "SELECT created_at FROM transcripts WHERE id = ?",
            (transcript_id,),
        ).fetchone()

        exported_paths = export_all_transcripts(
            conn,
            paths=paths,
            export_format="json",
        )

    assert exported_paths == [paths.exports_transcripts / "daily.json"]
    payload = json.loads(exported_paths[0].read_text(encoding="utf-8"))
    assert transcript is not None
    assert payload == {
        "media": {
            "id": media_id,
            "original_filename": "daily.mp4",
            "original_path": "data/media/inbox/daily.mp4",
            "managed_path": "data/media/processed/2026/05/daily.mp4",
            "content_hash": "daily-hash",
            "size_bytes": 128,
            "duration_seconds": 1.0,
            "inferred_session_at": "2026-05-31T21:30:00+00:00",
            "date_confidence": "medium",
            "status": "transcribed",
        },
        "transcript": {
            "id": transcript_id,
            "language": "de",
            "model": "whisper-test",
            "duration_seconds": 1.0,
            "status": "completed",
            "created_at": transcript["created_at"],
            "error_message": None,
        },
        "segments": [
            {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
        ],
    }


def test_export_all_transcripts_writes_completed_transcript_markdown(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id, transcript_id = create_completed_transcript(conn)

        exported_paths = export_all_transcripts(
            conn,
            paths,
            export_format=TranscriptExportFormat.MARKDOWN,
        )

    assert exported_paths == [paths.exports_transcripts / "daily.md"]
    markdown = exported_paths[0].read_text(encoding="utf-8")
    assert (
        markdown
        == f"""# daily.mp4

Language: de
Model: whisper-test
Transcript ID: {transcript_id}
Media ID: {media_id}

[0.00 - 1.00] Hallo.
"""
    )


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
