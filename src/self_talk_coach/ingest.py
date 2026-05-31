"""Managed media-library import for local self-talk videos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import hashlib
import shutil
import sqlite3

from self_talk_coach.db import get_media_file_by_hash, insert_media_file
from self_talk_coach.domain import DateConfidence, ImportOutcome, MediaStatus
from self_talk_coach.paths import AppPaths

SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".m4a",
    ".mp3",
    ".wav",
}


@dataclass(frozen=True)
class ImportedMedia:
    source_path: Path
    outcome: ImportOutcome
    managed_path: Path | None = None
    media_file_id: int | None = None
    message: str | None = None


def iter_media_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS
    )


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_session_datetime(path: Path) -> tuple[datetime, DateConfidence]:
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return modified_at.replace(microsecond=0), DateConfidence.MEDIUM


def build_managed_filename(
    *,
    original_path: Path,
    session_at: datetime,
    content_hash: str,
) -> str:
    timestamp = session_at.strftime("%Y-%m-%d_%H%M")
    suffix = original_path.suffix.lower()
    return f"{timestamp}_{content_hash[:8]}{suffix}"


def processed_dir_for(paths: AppPaths, session_at: datetime) -> Path:
    return paths.media_processed / f"{session_at.year:04d}" / f"{session_at.month:02d}"


def archived_dir_for(paths: AppPaths, session_at: datetime) -> Path:
    return paths.media_archived / f"{session_at.year:04d}" / f"{session_at.month:02d}"


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise FileExistsError(f"No unique destination available for: {path}")


def move_file(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))


def import_inbox(conn: sqlite3.Connection, paths: AppPaths) -> list[ImportedMedia]:
    paths.ensure_workspace()
    imported: list[ImportedMedia] = []

    for source_path in iter_media_files(paths.media_inbox):
        content_hash: str | None = None
        managed_path: Path | None = None

        try:
            content_hash = hash_file(source_path)
            session_at, date_confidence = infer_session_datetime(source_path)
            managed_filename = build_managed_filename(
                original_path=source_path,
                session_at=session_at,
                content_hash=content_hash,
            )
            existing = get_media_file_by_hash(conn, content_hash)

            if existing is not None:
                managed_path = unique_destination(
                    archived_dir_for(paths, session_at) / managed_filename
                )
                move_file(source_path, managed_path)
                imported.append(
                    ImportedMedia(
                        source_path=source_path,
                        outcome=ImportOutcome.DUPLICATE,
                        managed_path=managed_path,
                        media_file_id=int(existing["id"]),
                        message="duplicate content hash",
                    )
                )
                continue

            managed_path = unique_destination(processed_dir_for(paths, session_at) / managed_filename)
            original_path = str(source_path)
            original_filename = source_path.name
            move_file(source_path, managed_path)
            media_file_id = insert_media_file(
                conn,
                original_filename=original_filename,
                original_path=original_path,
                managed_path=str(managed_path),
                content_hash=content_hash,
                size_bytes=managed_path.stat().st_size,
                duration_seconds=None,
                inferred_session_at=session_at.isoformat(),
                date_confidence=date_confidence,
                status=MediaStatus.IMPORTED,
            )
            conn.commit()
            imported.append(
                ImportedMedia(
                    source_path=source_path,
                    outcome=ImportOutcome.IMPORTED,
                    managed_path=managed_path,
                    media_file_id=media_file_id,
                )
            )
        except Exception as error:
            conn.rollback()
            failed_path = _move_failed_source(source_path, paths, content_hash)
            imported.append(
                ImportedMedia(
                    source_path=source_path,
                    outcome=ImportOutcome.FAILED,
                    managed_path=failed_path,
                    message=str(error),
                )
            )

    return imported


def _move_failed_source(source_path: Path, paths: AppPaths, content_hash: str | None) -> Path | None:
    if not source_path.exists():
        return None

    failed_path = paths.media_failed / source_path.name
    if failed_path.exists():
        suffix = content_hash[:8] if content_hash is not None else datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        failed_path = paths.media_failed / f"{source_path.stem}-{suffix}{source_path.suffix}"

    failed_path = unique_destination(failed_path)
    move_file(source_path, failed_path)
    return failed_path
