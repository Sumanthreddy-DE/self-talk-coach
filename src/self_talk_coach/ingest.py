"""Managed media-library import for local self-talk videos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import hashlib
import shutil

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


def move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
