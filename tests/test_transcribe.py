import sys
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

from self_talk_coach.transcribe import (
    FasterWhisperTranscriber,
    TranscriptDraft,
    TranscriptSegmentDraft,
    extract_audio,
)


def test_extract_audio_runs_ffmpeg_for_16khz_mono_wav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "session.mp4"
    destination = tmp_path / "audio" / "session.wav"
    calls: list[tuple[list[str], bool, bool, bool]] = []

    def fake_run(
        command: list[str], *, check: bool, capture_output: bool, text: bool
    ) -> None:
        calls.append((command, check, capture_output, text))

    monkeypatch.setattr("self_talk_coach.transcribe.subprocess.run", fake_run)

    extract_audio(source, destination)

    assert destination.parent.exists()
    assert calls == [
        (
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(destination),
            ],
            True,
            True,
            True,
        )
    ]


def test_extract_audio_reports_unavailable_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "session.mp4"
    destination = tmp_path / "audio" / "session.wav"

    def fake_run(
        command: list[str], *, check: bool, capture_output: bool, text: bool
    ) -> None:
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr("self_talk_coach.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg unavailable"):
        extract_audio(source, destination)


def test_extract_audio_reports_ffmpeg_stderr_on_failed_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "session.mp4"
    destination = tmp_path / "audio" / "session.wav"

    def fake_run(
        command: list[str], *, check: bool, capture_output: bool, text: bool
    ) -> None:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=command, stderr="bad media"
        )

    monkeypatch.setattr("self_talk_coach.transcribe.subprocess.run", fake_run)

    with pytest.raises(
        RuntimeError, match="ffmpeg audio extraction failed: bad media"
    ):
        extract_audio(source, destination)


def test_faster_whisper_transcriber_lazily_reuses_model_and_builds_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    constructor_calls: list[tuple[str, str, str]] = []
    transcribe_calls: list[tuple[str, str, bool]] = []

    class FakeWhisperModel:
        def __init__(
            self, model_size: str, *, device: str, compute_type: str
        ) -> None:
            constructor_calls.append((model_size, device, compute_type))

        def transcribe(
            self, audio: str, *, language: str, vad_filter: bool
        ) -> tuple[list[SimpleNamespace], SimpleNamespace]:
            transcribe_calls.append((audio, language, vad_filter))
            return (
                [
                    SimpleNamespace(start=0.0, end=1.25, text="  Hallo  "),
                    SimpleNamespace(start=1.25, end=2.0, text="   "),
                    SimpleNamespace(start=2.0, end=3.5, text="Welt"),
                ],
                SimpleNamespace(language="de", duration=3.5),
            )

    fake_module = SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    transcriber = FasterWhisperTranscriber(
        model_size="small", device="cuda", compute_type="float16"
    )

    assert transcriber.model_name == "faster-whisper:small:cuda:float16"
    assert constructor_calls == []

    transcript = transcriber.transcribe(audio_path)
    second_transcript = transcriber.transcribe(audio_path)

    assert constructor_calls == [("small", "cuda", "float16")]
    assert transcribe_calls == [
        (str(audio_path), "de", True),
        (str(audio_path), "de", True),
    ]
    assert transcript == TranscriptDraft(
        language="de",
        duration_seconds=3.5,
        segments=(
            TranscriptSegmentDraft(
                start_seconds=0.0, end_seconds=1.25, text="Hallo"
            ),
            TranscriptSegmentDraft(
                start_seconds=2.0, end_seconds=3.5, text="Welt"
            ),
        ),
    )
    assert second_transcript == transcript


def test_faster_whisper_transcriber_defaults_language_to_german(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWhisperModel:
        def __init__(
            self, model_size: str, *, device: str, compute_type: str
        ) -> None:
            pass

        def transcribe(
            self, audio: str, *, language: str, vad_filter: bool
        ) -> tuple[list[SimpleNamespace], SimpleNamespace]:
            return ([], SimpleNamespace(language="", duration=None))

    fake_module = SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    transcript = FasterWhisperTranscriber().transcribe(tmp_path / "audio.wav")

    assert transcript == TranscriptDraft(
        language="de", duration_seconds=None, segments=()
    )
