"""Transcription foundations and audio extraction."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from self_talk_coach.domain import TranscriptionOutcome


@dataclass(frozen=True)
class TranscriptSegmentDraft:
    start_seconds: float
    end_seconds: float
    text: str

    def as_storage_dict(self) -> dict[str, float | str]:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }


@dataclass(frozen=True)
class TranscriptDraft:
    language: str
    duration_seconds: float | None
    segments: tuple[TranscriptSegmentDraft, ...]


@dataclass(frozen=True)
class TranscriptionRunResult:
    media_file_id: int
    outcome: TranscriptionOutcome
    transcript_id: int | None = None
    error_message: str | None = None


class Transcriber:
    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        raise NotImplementedError


AudioExtractor = Callable[[Path, Path], None]


def extract_audio(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(destination_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg unavailable") from exc
