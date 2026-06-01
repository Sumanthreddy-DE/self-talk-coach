from pathlib import Path

import pytest

from self_talk_coach.transcribe import extract_audio


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
