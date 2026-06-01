"""Transcription foundations and audio extraction."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from self_talk_coach.db import (
    get_transcript_by_media_file_id,
    list_media_files_for_transcription,
    replace_transcript,
    update_media_file_status,
)
from self_talk_coach.domain import (
    MediaStatus,
    TranscriptStatus,
    TranscriptionOutcome,
)
from self_talk_coach.paths import AppPaths


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


def audio_path_for(paths: AppPaths, media_file_id: int) -> Path:
    return paths.media_processing / f"media-{media_file_id}.wav"


def _transcriber_model_name(transcriber: Transcriber) -> str:
    return str(getattr(transcriber, "model_name", type(transcriber).__name__))


def transcribe_media_file(
    conn: Any,
    paths: AppPaths,
    media_row: Any,
    *,
    transcriber: Transcriber,
    audio_extractor: AudioExtractor = extract_audio,
) -> TranscriptionRunResult:
    media_file_id = int(media_row["id"])
    existing_transcript = get_transcript_by_media_file_id(conn, media_file_id)
    if (
        existing_transcript is not None
        and existing_transcript["status"] == TranscriptStatus.COMPLETED.value
    ):
        return TranscriptionRunResult(
            media_file_id=media_file_id,
            outcome=TranscriptionOutcome.SKIPPED,
            transcript_id=int(existing_transcript["id"]),
        )

    audio_path = audio_path_for(paths, media_file_id)
    try:
        managed_path = Path(media_row["managed_path"])
        if not managed_path.exists():
            raise FileNotFoundError(
                f"managed media path does not exist: {managed_path}"
            )

        audio_extractor(managed_path, audio_path)
        draft = transcriber.transcribe(audio_path)
        transcript_id = replace_transcript(
            conn,
            media_file_id=media_file_id,
            language=draft.language,
            model=_transcriber_model_name(transcriber),
            duration_seconds=draft.duration_seconds,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[segment.as_storage_dict() for segment in draft.segments],
        )
        update_media_file_status(
            conn,
            media_file_id=media_file_id,
            status=MediaStatus.TRANSCRIBED,
            error_message=None,
        )
        conn.commit()
        return TranscriptionRunResult(
            media_file_id=media_file_id,
            outcome=TranscriptionOutcome.TRANSCRIBED,
            transcript_id=transcript_id,
        )
    except Exception as exc:
        conn.rollback()
        error_message = str(exc)
        transcript_id = replace_transcript(
            conn,
            media_file_id=media_file_id,
            language="de",
            model=_transcriber_model_name(transcriber),
            duration_seconds=None,
            status=TranscriptStatus.FAILED,
            error_message=error_message,
            segments=[],
        )
        update_media_file_status(
            conn,
            media_file_id=media_file_id,
            status=MediaStatus.FAILED,
            error_message=error_message,
        )
        conn.commit()
        return TranscriptionRunResult(
            media_file_id=media_file_id,
            outcome=TranscriptionOutcome.FAILED,
            transcript_id=transcript_id,
            error_message=error_message,
        )
    finally:
        audio_path.unlink(missing_ok=True)


def transcribe_pending(
    conn: Any,
    paths: AppPaths,
    *,
    transcriber: Transcriber,
    audio_extractor: AudioExtractor = extract_audio,
) -> list[TranscriptionRunResult]:
    paths.ensure_workspace()
    return [
        transcribe_media_file(
            conn,
            paths,
            media_row,
            transcriber=transcriber,
            audio_extractor=audio_extractor,
        )
        for media_row in list_media_files_for_transcription(conn)
    ]
