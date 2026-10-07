"""Filesystem paths for the local self-talk-coach workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Resolved paths under the application data root."""

    data_root: Path

    @classmethod
    def from_data_root(cls, data_root: Path | str = "data") -> AppPaths:
        return cls(Path(data_root))

    @property
    def db_path(self) -> Path:
        return self.data_root / "db" / "self_talk_coach.sqlite"

    @property
    def media_root(self) -> Path:
        return self.data_root / "media"

    @property
    def media_inbox(self) -> Path:
        return self.media_root / "inbox"

    @property
    def media_processing(self) -> Path:
        return self.media_root / "processing"

    @property
    def media_processed(self) -> Path:
        return self.media_root / "processed"

    @property
    def media_failed(self) -> Path:
        return self.media_root / "failed"

    @property
    def media_archived(self) -> Path:
        return self.media_root / "archived"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"

    @property
    def exports_transcripts(self) -> Path:
        return self.exports_root / "transcripts"

    @property
    def exports_anki(self) -> Path:
        return self.exports_root / "anki"

    @property
    def exports_reports(self) -> Path:
        return self.exports_root / "reports"

    @property
    def conversations_root(self) -> Path:
        return self.data_root / "conversations"

    def conversation_dir(self, conversation_id: int) -> Path:
        return self.conversations_root / f"{conversation_id:04d}"

    @property
    def learner_profile_path(self) -> Path:
        return self.data_root / "learner-profile.md"

    def ensure_workspace(self) -> None:
        for directory in (
            self.db_path.parent,
            self.media_inbox,
            self.media_processing,
            self.media_processed,
            self.media_failed,
            self.media_archived,
            self.exports_transcripts,
            self.exports_anki,
            self.exports_reports,
            self.conversations_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
