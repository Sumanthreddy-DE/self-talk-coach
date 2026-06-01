import sqlite3
from pathlib import Path

import pytest

from self_talk_coach.db import (
    connect,
    get_media_file_by_hash,
    get_transcript_by_media_file_id,
    init_db,
    insert_media_file,
    list_media_files_for_transcription,
    replace_transcript,
)
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus


def insert_test_media(
    conn: sqlite3.Connection,
    *,
    content_hash: str = "transcript-hash",
    status: MediaStatus = MediaStatus.IMPORTED,
    inferred_session_at: str = "2026-05-31T21:30:00+00:00",
) -> int:
    return insert_media_file(
        conn,
        original_filename=f"{content_hash}.mp4",
        original_path=f"data/media/inbox/{content_hash}.mp4",
        managed_path=f"data/media/processed/2026/05/{content_hash}.mp4",
        content_hash=content_hash,
        size_bytes=128,
        duration_seconds=None,
        inferred_session_at=inferred_session_at,
        date_confidence=DateConfidence.MEDIUM,
        status=status,
    )


def test_init_db_creates_schema_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        init_db(conn)

        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        }

    assert user_version == 1
    assert {
        "media_files",
        "transcripts",
        "transcript_segments",
        "learning_candidates",
        "practice_items",
        "review_events",
    } <= table_names


def test_insert_and_get_media_file_by_hash(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="random-video.mp4",
            original_path="data/media/inbox/random-video.mp4",
            managed_path="data/media/processed/2026/05/2026-05-31_2130_ab12cd34.mp4",
            content_hash="ab12cd34ef",
            size_bytes=128,
            duration_seconds=None,
            inferred_session_at="2026-05-31T21:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.IMPORTED,
        )

        row = get_media_file_by_hash(conn, "ab12cd34ef")

    assert media_id > 0
    assert row is not None
    assert row["original_filename"] == "random-video.mp4"
    assert row["content_hash"] == "ab12cd34ef"
    assert row["date_confidence"] == "medium"
    assert row["status"] == "imported"


def test_insert_media_file_respects_caller_owned_rollback(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        insert_media_file(
            conn,
            original_filename="rollback-video.mp4",
            original_path="data/media/inbox/rollback-video.mp4",
            managed_path="data/media/processed/2026/05/rollback-video.mp4",
            content_hash="rollback-hash",
            size_bytes=128,
            duration_seconds=None,
            inferred_session_at="2026-05-31T21:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.IMPORTED,
        )
        conn.rollback()

        row = get_media_file_by_hash(conn, "rollback-hash")

    assert row is None


def test_transcripts_allow_one_transcript_per_media_file(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="one-transcript.mp4",
            original_path="data/media/inbox/one-transcript.mp4",
            managed_path="data/media/processed/2026/05/one-transcript.mp4",
            content_hash="one-transcript-hash",
            size_bytes=128,
            duration_seconds=None,
            inferred_session_at="2026-05-31T21:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.IMPORTED,
        )
        conn.execute(
            """
            INSERT INTO transcripts (media_file_id, language, model, status)
            VALUES (?, ?, ?, ?)
            """,
            (media_id, "en", "test-model", "completed"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO transcripts (media_file_id, language, model, status)
                VALUES (?, ?, ?, ?)
                """,
                (media_id, "en", "test-model", "completed"),
            )


def test_transcripts_reject_unknown_status(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO transcripts (media_file_id, language, model, status)
                VALUES (?, ?, ?, ?)
                """,
                (media_id, "en", "test-model", "nonsense"),
            )


def test_replace_transcript_inserts_transcript_and_timestamped_segments(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn)

        transcript_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[
                {"start_seconds": 0.0, "end_seconds": 2.5, "text": "hello"},
                {"start_seconds": 2.5, "end_seconds": 12.5, "text": "world"},
            ],
        )

        transcript = get_transcript_by_media_file_id(conn, media_id)
        segments = conn.execute(
            """
            SELECT start_seconds, end_seconds, text
            FROM transcript_segments
            WHERE transcript_id = ?
            ORDER BY start_seconds
            """,
            (transcript_id,),
        ).fetchall()

    assert transcript is not None
    assert transcript["id"] == transcript_id
    assert transcript["media_file_id"] == media_id
    assert transcript["language"] == "en"
    assert transcript["model"] == "whisper-test"
    assert transcript["duration_seconds"] == 12.5
    assert transcript["status"] == TranscriptStatus.COMPLETED.value
    assert transcript["error_message"] is None
    assert [dict(segment) for segment in segments] == [
        {"start_seconds": 0.0, "end_seconds": 2.5, "text": "hello"},
        {"start_seconds": 2.5, "end_seconds": 12.5, "text": "world"},
    ]


def test_replace_transcript_replaces_failed_attempt_for_same_media_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn)
        replace_transcript(
            conn,
            media_file_id=media_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.FAILED,
            error_message="audio decode failed",
            segments=[
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "partial"},
            ],
        )

        final_transcript_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[
                {"start_seconds": 1.0, "end_seconds": 12.5, "text": "final"},
            ],
        )
        transcript_count = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        segments = conn.execute(
            "SELECT transcript_id, start_seconds, end_seconds, text FROM transcript_segments"
        ).fetchall()
        transcript = get_transcript_by_media_file_id(conn, media_id)

    assert transcript_count == 1
    assert transcript is not None
    assert transcript["id"] == final_transcript_id
    assert transcript["status"] == TranscriptStatus.COMPLETED.value
    assert transcript["error_message"] is None
    assert [dict(segment) for segment in segments] == [
        {
            "transcript_id": final_transcript_id,
            "start_seconds": 1.0,
            "end_seconds": 12.5,
            "text": "final",
        }
    ]


def test_replace_transcript_preserves_existing_transcript_when_segment_insert_fails(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn)
        original_transcript_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[
                {"start_seconds": 0.0, "end_seconds": 12.5, "text": "original"},
            ],
        )

        with pytest.raises(KeyError):
            replace_transcript(
                conn,
                media_file_id=media_id,
                language="en",
                model="whisper-test",
                duration_seconds=12.5,
                status=TranscriptStatus.FAILED,
                error_message="bad segment",
                segments=[
                    {"start_seconds": 0.0, "end_seconds": 12.5},
                ],
            )
        conn.commit()

        transcript = get_transcript_by_media_file_id(conn, media_id)
        segments = conn.execute(
            """
            SELECT transcript_id, start_seconds, end_seconds, text
            FROM transcript_segments
            ORDER BY id
            """
        ).fetchall()

    assert transcript is not None
    assert transcript["id"] == original_transcript_id
    assert transcript["status"] == TranscriptStatus.COMPLETED.value
    assert transcript["error_message"] is None
    assert [dict(segment) for segment in segments] == [
        {
            "transcript_id": original_transcript_id,
            "start_seconds": 0.0,
            "end_seconds": 12.5,
            "text": "original",
        }
    ]


def test_list_media_files_for_transcription_skips_completed_transcripts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        imported_id = insert_test_media(
            conn,
            content_hash="imported-hash",
            status=MediaStatus.IMPORTED,
            inferred_session_at="2026-05-31T21:30:00+00:00",
        )
        failed_media_id = insert_test_media(
            conn,
            content_hash="failed-media-hash",
            status=MediaStatus.FAILED,
            inferred_session_at="2026-05-31T21:31:00+00:00",
        )
        completed_id = insert_test_media(
            conn,
            content_hash="completed-hash",
            status=MediaStatus.IMPORTED,
            inferred_session_at="2026-05-31T21:32:00+00:00",
        )
        failed_transcript_id = insert_test_media(
            conn,
            content_hash="failed-transcript-hash",
            status=MediaStatus.IMPORTED,
            inferred_session_at="2026-05-31T21:33:00+00:00",
        )
        transcribed_id = insert_test_media(
            conn,
            content_hash="transcribed-hash",
            status=MediaStatus.TRANSCRIBED,
            inferred_session_at="2026-05-31T21:34:00+00:00",
        )
        replace_transcript(
            conn,
            media_file_id=completed_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[],
        )
        replace_transcript(
            conn,
            media_file_id=failed_transcript_id,
            language="en",
            model="whisper-test",
            duration_seconds=12.5,
            status=TranscriptStatus.FAILED,
            error_message="network failed",
            segments=[],
        )

        rows = list_media_files_for_transcription(conn)

    assert [row["id"] for row in rows] == [
        imported_id,
        failed_media_id,
        failed_transcript_id,
    ]
    assert transcribed_id not in [row["id"] for row in rows]
