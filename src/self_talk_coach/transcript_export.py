"""Export stored transcripts to local transcript files."""

from __future__ import annotations

import json
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any

from self_talk_coach.paths import AppPaths


class TranscriptExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


def list_completed_transcripts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            transcripts.id AS transcript_id,
            transcripts.media_file_id AS media_file_id,
            transcripts.language AS transcript_language,
            transcripts.model AS transcript_model,
            transcripts.duration_seconds AS transcript_duration_seconds,
            transcripts.status AS transcript_status,
            transcripts.created_at AS transcript_created_at,
            transcripts.error_message AS transcript_error_message,
            media_files.original_filename AS original_filename,
            media_files.original_path AS original_path,
            media_files.managed_path AS managed_path,
            media_files.content_hash AS content_hash,
            media_files.size_bytes AS size_bytes,
            media_files.duration_seconds AS media_duration_seconds,
            media_files.inferred_session_at AS inferred_session_at,
            media_files.date_confidence AS date_confidence,
            media_files.status AS media_status
        FROM transcripts
        JOIN media_files ON media_files.id = transcripts.media_file_id
        WHERE transcripts.status = 'completed'
        ORDER BY media_files.inferred_session_at, media_files.id
        """
    ).fetchall()


def list_segments(conn: sqlite3.Connection, transcript_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, start_seconds, end_seconds, text
        FROM transcript_segments
        WHERE transcript_id = ?
        ORDER BY start_seconds, id
        """,
        (transcript_id,),
    ).fetchall()


def export_stem(row: sqlite3.Row) -> str:
    managed_path = row["managed_path"]
    if managed_path:
        stem = Path(managed_path).stem
        if stem:
            return stem
    return f"transcript-{row['transcript_id']}"


def transcript_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    segments = list_segments(conn, int(row["transcript_id"]))
    return {
        "media": {
            "id": row["media_file_id"],
            "original_filename": row["original_filename"],
            "original_path": row["original_path"],
            "managed_path": row["managed_path"],
            "content_hash": row["content_hash"],
            "size_bytes": row["size_bytes"],
            "duration_seconds": row["media_duration_seconds"],
            "inferred_session_at": row["inferred_session_at"],
            "date_confidence": row["date_confidence"],
            "status": row["media_status"],
        },
        "transcript": {
            "id": row["transcript_id"],
            "language": row["transcript_language"],
            "model": row["transcript_model"],
            "duration_seconds": row["transcript_duration_seconds"],
            "status": row["transcript_status"],
            "created_at": row["transcript_created_at"],
            "error_message": row["transcript_error_message"],
        },
        "segments": [
            {
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment["end_seconds"],
                "text": segment["text"],
            }
            for segment in segments
        ],
    }


def write_json_export(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    destination: Path,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    export_path = destination / f"{export_stem(row)}.json"
    payload = transcript_payload(conn, row)
    export_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return export_path


def write_markdown_export(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    destination: Path,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    export_path = destination / f"{export_stem(row)}.md"
    payload = transcript_payload(conn, row)
    transcript = payload["transcript"]
    media = payload["media"]

    lines = [
        f"# {media['original_filename']}",
        "",
        f"Language: {transcript['language']}",
        f"Model: {transcript['model']}",
        f"Transcript ID: {transcript['id']}",
        f"Media ID: {media['id']}",
        "",
    ]
    lines.extend(
        f"[{segment['start_seconds']:.2f} - {segment['end_seconds']:.2f}] {segment['text']}"
        for segment in payload["segments"]
    )
    export_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return export_path


def export_all_transcripts(
    conn: sqlite3.Connection,
    paths: AppPaths,
    *,
    export_format: TranscriptExportFormat | str,
) -> list[Path]:
    try:
        selected_format = TranscriptExportFormat(export_format)
    except ValueError as exc:
        raise ValueError("unsupported transcript export format") from exc

    destination = paths.exports_transcripts
    destination.mkdir(parents=True, exist_ok=True)
    exported_paths: list[Path] = []
    for row in list_completed_transcripts(conn):
        if selected_format is TranscriptExportFormat.JSON:
            exported_paths.append(write_json_export(conn, row, destination))
        elif selected_format is TranscriptExportFormat.MARKDOWN:
            exported_paths.append(write_markdown_export(conn, row, destination))
        else:
            raise ValueError("unsupported transcript export format")
    return exported_paths
