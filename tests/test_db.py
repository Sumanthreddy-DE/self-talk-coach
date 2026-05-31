import sqlite3
from pathlib import Path

import pytest

from self_talk_coach.db import connect, get_media_file_by_hash, init_db, insert_media_file
from self_talk_coach.domain import DateConfidence, MediaStatus


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
