"""SQLite persistence for local self-talk-coach state."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from self_talk_coach.domain import (
    ConversationStatus,
    DateConfidence,
    MediaStatus,
    TranscriptStatus,
    TurnSpeaker,
)

SCHEMA_VERSION = 2


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY,
            original_filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            managed_path TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL,
            duration_seconds REAL,
            inferred_session_at TEXT NOT NULL,
            date_confidence TEXT NOT NULL CHECK (date_confidence IN ('high', 'medium', 'low')),
            status TEXT NOT NULL CHECK (status IN ('imported', 'transcribed', 'analyzed', 'failed', 'archived')),
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_media_files_status
            ON media_files(status);

        CREATE INDEX IF NOT EXISTS idx_media_files_inferred_session_at
            ON media_files(inferred_session_at);

        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY,
            media_file_id INTEGER NOT NULL UNIQUE REFERENCES media_files(id) ON DELETE CASCADE,
            language TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_seconds REAL,
            status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_segments (
            id INTEGER PRIMARY KEY,
            transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            text TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_transcript_segments_transcript_id
            ON transcript_segments(transcript_id);

        CREATE INDEX IF NOT EXISTS idx_transcript_segments_time
            ON transcript_segments(transcript_id, start_seconds);

        CREATE TABLE IF NOT EXISTS learning_candidates (
            id INTEGER PRIMARY KEY,
            candidate_type TEXT NOT NULL,
            transcript_segment_id INTEGER REFERENCES transcript_segments(id) ON DELETE SET NULL,
            original_text TEXT NOT NULL,
            suggested_text TEXT,
            explanation TEXT NOT NULL,
            severity INTEGER NOT NULL DEFAULT 1,
            usefulness INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            producer TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS practice_items (
            id INTEGER PRIMARY KEY,
            learning_candidate_id INTEGER NOT NULL REFERENCES learning_candidates(id) ON DELETE CASCADE,
            practice_type TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            notes TEXT,
            export_status TEXT NOT NULL DEFAULT 'not_exported',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS review_events (
            id INTEGER PRIMARY KEY,
            learning_candidate_id INTEGER REFERENCES learning_candidates(id) ON DELETE SET NULL,
            practice_item_id INTEGER REFERENCES practice_items(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            scenario TEXT,
            stt_model TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            tts_voice TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'aborted')),
            report_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (report_status IN ('pending', 'done', 'failed'))
        );

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            turn_index INTEGER NOT NULL,
            speaker TEXT NOT NULL CHECK (speaker IN ('learner', 'partner')),
            text TEXT NOT NULL,
            audio_path TEXT,
            words_json TEXT,
            seed TEXT,
            partner_turn_json TEXT,
            llm_model TEXT,
            freeze_seconds REAL,
            ladder_step_reached INTEGER NOT NULL DEFAULT 0,
            replay_count INTEGER NOT NULL DEFAULT 0,
            slower_count INTEGER NOT NULL DEFAULT 0,
            show_text_count INTEGER NOT NULL DEFAULT 0,
            comprehension_check INTEGER NOT NULL DEFAULT 0,
            out_of_baseline_ratio REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (conversation_id, turn_index)
        );
        """
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def insert_media_file(
    conn: sqlite3.Connection,
    *,
    original_filename: str,
    original_path: str,
    managed_path: str,
    content_hash: str,
    size_bytes: int,
    duration_seconds: float | None,
    inferred_session_at: str,
    date_confidence: DateConfidence,
    status: MediaStatus,
    error_message: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO media_files (
            original_filename,
            original_path,
            managed_path,
            content_hash,
            size_bytes,
            duration_seconds,
            inferred_session_at,
            date_confidence,
            status,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            original_filename,
            original_path,
            managed_path,
            content_hash,
            size_bytes,
            duration_seconds,
            inferred_session_at,
            date_confidence.value,
            status.value,
            error_message,
        ),
    )
    return int(cursor.lastrowid)


def get_media_file_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM media_files WHERE content_hash = ?",
        (content_hash,),
    ).fetchone()


def get_media_file_by_id(conn: sqlite3.Connection, media_file_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM media_files WHERE id = ?",
        (media_file_id,),
    ).fetchone()


def list_media_files_for_transcription(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT media_files.*
        FROM media_files
        WHERE media_files.status IN (?, ?)
          AND NOT EXISTS (
              SELECT 1
              FROM transcripts
              WHERE transcripts.media_file_id = media_files.id
                AND transcripts.status = ?
          )
        ORDER BY media_files.inferred_session_at, media_files.id
        """,
        (
            MediaStatus.IMPORTED.value,
            MediaStatus.FAILED.value,
            TranscriptStatus.COMPLETED.value,
        ),
    ).fetchall()


def get_transcript_by_media_file_id(
    conn: sqlite3.Connection, media_file_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM transcripts WHERE media_file_id = ?",
        (media_file_id,),
    ).fetchone()


def replace_transcript(
    conn: sqlite3.Connection,
    *,
    media_file_id: int,
    language: str,
    model: str,
    duration_seconds: float | None,
    status: TranscriptStatus,
    error_message: str | None,
    segments: Iterable[dict[str, float | str]],
) -> int:
    conn.execute("SAVEPOINT replace_transcript")
    try:
        conn.execute("DELETE FROM transcripts WHERE media_file_id = ?", (media_file_id,))
        cursor = conn.execute(
            """
            INSERT INTO transcripts (
                media_file_id,
                language,
                model,
                duration_seconds,
                status,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                media_file_id,
                language,
                model,
                duration_seconds,
                status.value,
                error_message,
            ),
        )
        transcript_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO transcript_segments (
                transcript_id,
                start_seconds,
                end_seconds,
                text
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                (
                    transcript_id,
                    segment["start_seconds"],
                    segment["end_seconds"],
                    segment["text"],
                )
                for segment in segments
            ),
        )
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT replace_transcript")
        conn.execute("RELEASE SAVEPOINT replace_transcript")
        raise

    conn.execute("RELEASE SAVEPOINT replace_transcript")
    return transcript_id


def update_media_file_status(
    conn: sqlite3.Connection,
    *,
    media_file_id: int,
    status: MediaStatus,
    error_message: str | None,
) -> None:
    conn.execute(
        """
        UPDATE media_files
        SET status = ?,
            error_message = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (status.value, error_message, media_file_id),
    )


def insert_conversation(
    conn: sqlite3.Connection,
    *,
    started_at: str,
    scenario: str | None,
    stt_model: str,
    llm_model: str,
    tts_voice: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO conversations (started_at, scenario, stt_model, llm_model, tts_voice, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (started_at, scenario, stt_model, llm_model, tts_voice, ConversationStatus.ACTIVE.value),
    )
    conn.commit()
    return int(cursor.lastrowid)


def finish_conversation(
    conn: sqlite3.Connection, conversation_id: int, *, ended_at: str, status: ConversationStatus
) -> None:
    conn.execute(
        "UPDATE conversations SET ended_at = ?, status = ? WHERE id = ?",
        (ended_at, status.value, conversation_id),
    )
    conn.commit()


def get_conversation(conn: sqlite3.Connection, conversation_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()


def insert_turn(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
    turn_index: int,
    speaker: TurnSpeaker,
    text: str,
    audio_path: str | None = None,
    words_json: str | None = None,
    seed: str | None = None,
    partner_turn_json: str | None = None,
    llm_model: str | None = None,
    freeze_seconds: float | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO turns (
            conversation_id, turn_index, speaker, text, audio_path, words_json,
            seed, partner_turn_json, llm_model, freeze_seconds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id, turn_index, speaker.value, text, audio_path, words_json,
            seed, partner_turn_json, llm_model, freeze_seconds,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_turn_listening(
    conn: sqlite3.Connection,
    turn_id: int,
    *,
    ladder_step_reached: int,
    replay_count: int,
    slower_count: int,
    show_text_count: int,
) -> None:
    conn.execute(
        """
        UPDATE turns
        SET ladder_step_reached = ?, replay_count = ?, slower_count = ?, show_text_count = ?
        WHERE id = ?
        """,
        (ladder_step_reached, replay_count, slower_count, show_text_count, turn_id),
    )
    conn.commit()


def list_turns(conn: sqlite3.Connection, conversation_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM turns WHERE conversation_id = ? ORDER BY turn_index", (conversation_id,)
    ).fetchall()