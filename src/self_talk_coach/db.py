"""SQLite persistence for local self-talk-coach state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from self_talk_coach.domain import DateConfidence, MediaStatus

SCHEMA_VERSION = 1


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
            media_file_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
            language TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_seconds REAL,
            status TEXT NOT NULL,
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
    conn.commit()
    return int(cursor.lastrowid)


def get_media_file_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM media_files WHERE content_hash = ?",
        (content_hash,),
    ).fetchone()
