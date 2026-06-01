"""Transcription foundations and audio extraction."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


class FasterWhisperTranscriber(Transcriber):
    def __init__(
        self,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any | None = None

    @property
    def model_name(self) -> str:
        return (
            f"faster-whisper:{self.model_size}:{self.device}:"
            f"{self.compute_type}"
        )

    def _load_model(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        model = self._load_model()
        segments, info = model.transcribe(
            str(audio_path), language="de", vad_filter=True
        )
        segment_drafts = tuple(
            TranscriptSegmentDraft(
                start_seconds=segment.start,
                end_seconds=segment.end,
                text=text,
            )
            for segment in segments
            if (text := segment.text.strip())
        )
        return TranscriptDraft(
            language=getattr(info, "language", None) or "de",
            duration_seconds=getattr(info, "duration", None),
            segments=segment_drafts,
        )


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
    except subprocess.CalledProcessError as exc:
        details = exc.stderr or f"exit code {exc.returncode}"
        raise RuntimeError(f"ffmpeg audio extraction failed: {details}") from exc
