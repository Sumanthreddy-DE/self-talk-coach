import subprocess
import sys
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from self_talk_coach.db import (
    connect,
    get_transcript_by_media_file_id,
    init_db,
    insert_media_file,
)
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptionOutcome
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcribe import (
    FasterWhisperTranscriber,
    TranscriptDraft,
    TranscriptSegmentDraft,
    TranscriptionRunResult,
    audio_path_for,
    extract_audio,
    transcribe_pending,
)


class FakeTranscriber:
    model_name = "fake-whisper"

    def __init__(self, transcript: TranscriptDraft | None = None) -> None:
        self.transcript = transcript or TranscriptDraft(
            language="de",
            duration_seconds=2.5,
            segments=(
                TranscriptSegmentDraft(
                    start_seconds=0.0, end_seconds=1.0, text="Hallo"
                ),
                TranscriptSegmentDraft(
                    start_seconds=1.0, end_seconds=2.5, text="Welt"
                ),
            ),
        )
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        self.calls.append(audio_path)
        return self.transcript


class FailingTranscriber:
    model_name = "fake-whisper"

    def __init__(self, message: str = "transcription failed") -> None:
        self.message = message
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        self.calls.append(audio_path)
        raise RuntimeError(self.message)


def open_test_db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "self_talk_coach.sqlite")
    init_db(conn)
    return conn


def insert_test_media(
    conn: sqlite3.Connection,
    managed_path: Path,
    *,
    content_hash: str = "transcribe-hash",
    status: MediaStatus = MediaStatus.IMPORTED,
    error_message: str | None = None,
) -> int:
    return insert_media_file(
        conn,
        original_filename=f"{content_hash}.mp4",
        original_path=f"data/media/inbox/{content_hash}.mp4",
        managed_path=str(managed_path),
        content_hash=content_hash,
        size_bytes=128,
        duration_seconds=None,
        inferred_session_at="2026-05-31T21:30:00+00:00",
        date_confidence=DateConfidence.MEDIUM,
        status=status,
        error_message=error_message,
    )


def write_managed_media(paths: AppPaths, name: str = "session.mp4") -> Path:
    managed_path = paths.media_processed / "2026" / "05" / name
    managed_path.parent.mkdir(parents=True, exist_ok=True)
    managed_path.write_bytes(b"managed media")
    return managed_path


def fake_audio_extractor(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(source_path.read_bytes() + b" wav")


def test_transcribe_pending_stores_completed_transcript_and_cleans_temp_wav(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    transcriber = FakeTranscriber()

    with open_test_db(tmp_path) as conn:
        media_id = insert_test_media(conn, write_managed_media(paths))
        conn.commit()

        results = transcribe_pending(
            conn,
            paths,
            transcriber=transcriber,
            audio_extractor=fake_audio_extractor,
        )

        transcript = get_transcript_by_media_file_id(conn, media_id)
        media = conn.execute(
            "SELECT status, error_message FROM media_files WHERE id = ?",
            (media_id,),
        ).fetchone()
        segments = conn.execute(
            """
            SELECT start_seconds, end_seconds, text
            FROM transcript_segments
            WHERE transcript_id = ?
            ORDER BY start_seconds
            """,
            (transcript["id"],),
        ).fetchall()

    assert results == [
        TranscriptionRunResult(
            media_file_id=media_id,
            outcome=TranscriptionOutcome.TRANSCRIBED,
            transcript_id=transcript["id"],
        )
    ]
    assert transcript["language"] == "de"
    assert transcript["model"] == "fake-whisper"
    assert transcript["duration_seconds"] == 2.5
    assert transcript["status"] == "completed"
    assert transcript["error_message"] is None
    assert [dict(segment) for segment in segments] == [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo"},
        {"start_seconds": 1.0, "end_seconds": 2.5, "text": "Welt"},
    ]
    assert dict(media) == {
        "status": MediaStatus.TRANSCRIBED.value,
        "error_message": None,
    }
    assert transcriber.calls == [audio_path_for(paths, media_id)]
    assert not audio_path_for(paths, media_id).exists()


def test_transcribe_pending_rerun_skips_completed_transcript_work(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    first_transcriber = FakeTranscriber()
    second_transcriber = FakeTranscriber()

    with open_test_db(tmp_path) as conn:
        insert_test_media(conn, write_managed_media(paths))
        conn.commit()

        first_results = transcribe_pending(
            conn,
            paths,
            transcriber=first_transcriber,
            audio_extractor=fake_audio_extractor,
        )
        second_results = transcribe_pending(
            conn,
            paths,
            transcriber=second_transcriber,
            audio_extractor=fake_audio_extractor,
        )

    assert [result.outcome for result in first_results] == [
        TranscriptionOutcome.TRANSCRIBED
    ]
    assert second_results == []
    assert len(first_transcriber.calls) == 1
    assert second_transcriber.calls == []


def test_failed_transcription_is_recorded_and_successful_retry_replaces_it(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    managed_path = write_managed_media(paths)
    failing_transcriber = FailingTranscriber("decode failed")
    successful_transcriber = FakeTranscriber()

    with open_test_db(tmp_path) as conn:
        media_id = insert_test_media(conn, managed_path)
        conn.commit()

        failed_results = transcribe_pending(
            conn,
            paths,
            transcriber=failing_transcriber,
            audio_extractor=fake_audio_extractor,
        )
        failed_transcript = get_transcript_by_media_file_id(conn, media_id)
        failed_media = conn.execute(
            "SELECT status, error_message FROM media_files WHERE id = ?",
            (media_id,),
        ).fetchone()

        successful_results = transcribe_pending(
            conn,
            paths,
            transcriber=successful_transcriber,
            audio_extractor=fake_audio_extractor,
        )
        final_transcript = get_transcript_by_media_file_id(conn, media_id)
        transcript_count = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE media_file_id = ?",
            (media_id,),
        ).fetchone()[0]
        final_media = conn.execute(
            "SELECT status, error_message FROM media_files WHERE id = ?",
            (media_id,),
        ).fetchone()

    assert failed_results == [
        TranscriptionRunResult(
            media_file_id=media_id,
            outcome=TranscriptionOutcome.FAILED,
            transcript_id=failed_transcript["id"],
            error_message="decode failed",
        )
    ]
    assert failed_transcript["status"] == "failed"
    assert failed_transcript["error_message"] == "decode failed"
    assert dict(failed_media) == {
        "status": MediaStatus.FAILED.value,
        "error_message": "decode failed",
    }
    assert [result.outcome for result in successful_results] == [
        TranscriptionOutcome.TRANSCRIBED
    ]
    assert transcript_count == 1
    assert final_transcript["status"] == "completed"
    assert final_transcript["error_message"] is None
    assert dict(final_media) == {
        "status": MediaStatus.TRANSCRIBED.value,
        "error_message": None,
    }


def test_missing_managed_media_path_records_failure_without_crashing_batch(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    transcriber = FakeTranscriber()
    missing_path = paths.media_processed / "missing.mp4"
    existing_path = write_managed_media(paths, "existing.mp4")

    with open_test_db(tmp_path) as conn:
        missing_media_id = insert_test_media(
            conn, missing_path, content_hash="missing-hash"
        )
        existing_media_id = insert_test_media(
            conn,
            existing_path,
            content_hash="existing-hash",
        )
        conn.commit()

        results = transcribe_pending(
            conn,
            paths,
            transcriber=transcriber,
            audio_extractor=fake_audio_extractor,
        )

        failed_transcript = get_transcript_by_media_file_id(
            conn, missing_media_id
        )
        completed_transcript = get_transcript_by_media_file_id(
            conn, existing_media_id
        )

    assert [result.outcome for result in results] == [
        TranscriptionOutcome.FAILED,
        TranscriptionOutcome.TRANSCRIBED,
    ]
    assert failed_transcript["status"] == "failed"
    assert "managed media path does not exist" in failed_transcript["error_message"]
    assert completed_transcript["status"] == "completed"
    assert transcriber.calls == [audio_path_for(paths, existing_media_id)]


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
