# Transcription Storage Implementation Plan

**Status:** done
**Last verified:** 2026-09-28
**Status evidence:** transcribe.py FasterWhisperTranscriber + transcribe_pending, transcript_export.py, cli transcribe/export present; commits 0e55ec4..74bf901 (2026-06-01/02)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Milestone 2: transcribe imported German self-talk media, store one durable transcript with timestamped segments per media file, skip completed work on rerun, and export transcripts for inspection.

**Architecture:** Extend the current SQLite repository in `db.py`, replace the S2 stub in `transcribe.py` with testable ffmpeg and faster-whisper services, and keep the Typer CLI as a thin orchestration layer. The transcription service accepts injectable transcriber and audio-extractor callables so unit tests never need real media, ffmpeg, or model downloads.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, stdlib `subprocess`, stdlib `json`, `faster-whisper`, Typer, pytest.

---

## File Structure

- Modify `src/self_talk_coach/domain.py`
  - Adds transcript status and transcription run outcome enums.
- Modify `src/self_talk_coach/db.py`
  - Adds transcript repository functions and media status updates.
- Replace `src/self_talk_coach/transcribe.py`
  - Owns ffmpeg audio extraction, faster-whisper transcription, and idempotent transcription orchestration.
- Create `src/self_talk_coach/transcript_export.py`
  - Owns JSON and Markdown transcript inspection exports.
- Modify `src/self_talk_coach/cli.py`
  - Adds `stc transcribe` and `stc export transcripts`.
- Modify `tests/test_db.py`
  - Verifies transcript repository behavior and completed-transcript skip queries.
- Create `tests/test_transcribe.py`
  - Verifies ffmpeg invocation, forced German faster-whisper adapter behavior, idempotent storage, and recoverable failures.
- Create `tests/test_transcript_export.py`
  - Verifies JSON and Markdown transcript exports.
- Modify `tests/test_cli_media_library.py`
  - Adds CLI coverage for transcription and transcript export commands.
- Modify `tests/test_smoke.py`
  - Includes the new transcript export module.
- Modify `README.md`
  - Documents the local transcription workflow.
- Modify `BACKLOG.md`
  - Moves `transcription-storage` from Open to Done this session.
- Modify `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`
  - Marks Milestone 2 as planned in this file and completed when tests pass.

---

## Task 1: Transcript Domain And Repository Functions

**Files:**
- Modify: `src/self_talk_coach/domain.py`
- Modify: `src/self_talk_coach/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add failing repository tests**

Append to `tests/test_db.py`:

```python
from self_talk_coach.db import (
    get_transcript_by_media_file_id,
    list_media_files_for_transcription,
    replace_transcript,
    update_media_file_status,
)
from self_talk_coach.domain import TranscriptStatus


def insert_test_media(conn, *, content_hash: str = "transcript-hash") -> int:
    return insert_media_file(
        conn,
        original_filename=f"{content_hash}.mp4",
        original_path=f"data/media/inbox/{content_hash}.mp4",
        managed_path=f"data/media/processed/2026/06/{content_hash}.mp4",
        content_hash=content_hash,
        size_bytes=128,
        duration_seconds=None,
        inferred_session_at="2026-06-01T08:30:00+00:00",
        date_confidence=DateConfidence.MEDIUM,
        status=MediaStatus.IMPORTED,
    )


def test_replace_transcript_inserts_transcript_and_segments(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn)
        transcript_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="tiny",
            duration_seconds=2.5,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
                {"start_seconds": 1.0, "end_seconds": 2.5, "text": "Ich uebe Deutsch."},
            ],
        )
        transcript = get_transcript_by_media_file_id(conn, media_id)
        rows = conn.execute(
            "SELECT start_seconds, end_seconds, text FROM transcript_segments WHERE transcript_id = ? ORDER BY id",
            (transcript_id,),
        ).fetchall()

    assert transcript is not None
    assert transcript["language"] == "de"
    assert transcript["model"] == "tiny"
    assert transcript["status"] == "completed"
    assert [dict(row) for row in rows] == [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
        {"start_seconds": 1.0, "end_seconds": 2.5, "text": "Ich uebe Deutsch."},
    ]


def test_replace_transcript_replaces_failed_attempt_for_same_media(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_test_media(conn, content_hash="retry-hash")
        failed_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="tiny",
            duration_seconds=None,
            status=TranscriptStatus.FAILED,
            error_message="ffmpeg failed",
            segments=[],
        )
        completed_id = replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="tiny",
            duration_seconds=1.0,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[{"start_seconds": 0.0, "end_seconds": 1.0, "text": "Fertig."}],
        )
        transcript_count = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        segment_count = conn.execute("SELECT COUNT(*) FROM transcript_segments").fetchone()[0]

    assert failed_id != completed_id
    assert transcript_count == 1
    assert segment_count == 1


def test_list_media_files_for_transcription_skips_completed_transcripts(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        pending_id = insert_test_media(conn, content_hash="pending-hash")
        completed_id = insert_test_media(conn, content_hash="completed-hash")
        failed_id = insert_test_media(conn, content_hash="failed-hash")
        replace_transcript(
            conn,
            media_file_id=completed_id,
            language="de",
            model="tiny",
            duration_seconds=1.0,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[{"start_seconds": 0.0, "end_seconds": 1.0, "text": "Schon fertig."}],
        )
        update_media_file_status(
            conn,
            media_file_id=failed_id,
            status=MediaStatus.FAILED,
            error_message="previous attempt failed",
        )
        rows = list_media_files_for_transcription(conn)

    assert [row["id"] for row in rows] == [pending_id, failed_id]
```

- [ ] **Step 2: Run DB tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_db.py
```

Expected: FAIL with import errors for `TranscriptStatus`, `replace_transcript`, `get_transcript_by_media_file_id`, `list_media_files_for_transcription`, and `update_media_file_status`.

- [ ] **Step 3: Add transcript enums**

Replace `src/self_talk_coach/domain.py` with:

```python
"""Domain enums shared by the local-first learning core."""

from __future__ import annotations

from enum import StrEnum


class DateConfidence(StrEnum):
    """Confidence level for inferred session timestamps."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MediaStatus(StrEnum):
    """Lifecycle state for an imported media file."""

    IMPORTED = "imported"
    TRANSCRIBED = "transcribed"
    ANALYZED = "analyzed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ImportOutcome(StrEnum):
    """Outcome category for one inbox file import attempt."""

    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class TranscriptStatus(StrEnum):
    """Storage status for one media transcription attempt."""

    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionOutcome(StrEnum):
    """Outcome category for one transcription run item."""

    TRANSCRIBED = "transcribed"
    SKIPPED = "skipped"
    FAILED = "failed"
```

- [ ] **Step 4: Add transcript repository functions**

In `src/self_talk_coach/db.py`, add this import near the other imports:

```python
from collections.abc import Iterable
```

Update the existing domain import to include `TranscriptStatus`:

```python
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus
```

Then append these repository functions to `src/self_talk_coach/db.py`:

```python
def get_media_file_by_id(conn: sqlite3.Connection, media_file_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM media_files WHERE id = ?",
        (media_file_id,),
    ).fetchone()


def list_media_files_for_transcription(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT media_files.*
        FROM media_files
        WHERE media_files.status IN ('imported', 'failed')
          AND NOT EXISTS (
              SELECT 1
              FROM transcripts
              WHERE transcripts.media_file_id = media_files.id
                AND transcripts.status = 'completed'
          )
        ORDER BY media_files.inferred_session_at, media_files.id
        """
    ).fetchall()


def get_transcript_by_media_file_id(
    conn: sqlite3.Connection,
    media_file_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM transcripts WHERE media_file_id = ?",
        (media_file_id,),
    ).fetchone()


def replace_transcript(
    conn: sqlite3.Connection,
    *,
    media_file_id: int,
    language: str,
    model: str,
    duration_seconds: float | None,
    status: TranscriptStatus,
    error_message: str | None,
    segments: Iterable[dict[str, float | str]],
) -> int:
    existing = get_transcript_by_media_file_id(conn, media_file_id)
    if existing is not None:
        conn.execute("DELETE FROM transcripts WHERE id = ?", (existing["id"],))

    cursor = conn.execute(
        """
        INSERT INTO transcripts (
            media_file_id,
            language,
            model,
            duration_seconds,
            status,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            media_file_id,
            language,
            model,
            duration_seconds,
            status.value,
            error_message,
        ),
    )
    transcript_id = int(cursor.lastrowid)
    conn.executemany(
        """
        INSERT INTO transcript_segments (
            transcript_id,
            start_seconds,
            end_seconds,
            text
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                transcript_id,
                float(segment["start_seconds"]),
                float(segment["end_seconds"]),
                str(segment["text"]),
            )
            for segment in segments
        ],
    )
    return transcript_id


def update_media_file_status(
    conn: sqlite3.Connection,
    *,
    media_file_id: int,
    status: MediaStatus,
    error_message: str | None,
) -> None:
    conn.execute(
        """
        UPDATE media_files
        SET status = ?,
            error_message = ?,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (status.value, error_message, media_file_id),
    )
```

- [ ] **Step 5: Add transcript indexes**

In `init_db`, after the `CREATE TABLE IF NOT EXISTS transcript_segments` block, add:

```python
        CREATE INDEX IF NOT EXISTS idx_transcript_segments_transcript_id
            ON transcript_segments(transcript_id);

        CREATE INDEX IF NOT EXISTS idx_transcript_segments_time
            ON transcript_segments(transcript_id, start_seconds);
```

- [ ] **Step 6: Run DB tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_db.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/self_talk_coach/domain.py src/self_talk_coach/db.py tests/test_db.py
git commit -m "feat: add transcript repository"
```

---

## Task 2: ffmpeg Audio Extraction

**Files:**
- Replace: `src/self_talk_coach/transcribe.py`
- Create: `tests/test_transcribe.py`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Write failing ffmpeg extraction tests**

Create `tests/test_transcribe.py`:

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from self_talk_coach.transcribe import extract_audio


def test_extract_audio_runs_ffmpeg_for_16khz_mono_wav(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    destination = tmp_path / "processing" / "clip.wav"
    source.write_bytes(b"video")
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append(
            {
                "command": command,
                "check": check,
                "capture_output": capture_output,
                "text": text,
            }
        )
        destination.write_bytes(b"wav")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("self_talk_coach.transcribe.subprocess.run", fake_run)

    extract_audio(source, destination)

    assert destination.read_bytes() == b"wav"
    assert calls == [
        {
            "command": [
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
            "check": True,
            "capture_output": True,
            "text": True,
        }
    ]


def test_extract_audio_wraps_ffmpeg_errors(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "clip.mp4"
    destination = tmp_path / "processing" / "clip.wav"
    source.write_bytes(b"video")

    def fake_run(command, check, capture_output, text):
        raise RuntimeError("ffmpeg unavailable")

    monkeypatch.setattr("self_talk_coach.transcribe.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg unavailable"):
        extract_audio(source, destination)
```

- [ ] **Step 2: Run transcription tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py
```

Expected: FAIL because `extract_audio` does not exist.

- [ ] **Step 3: Add ffmpeg extraction code**

Replace `src/self_talk_coach/transcribe.py` with:

```python
"""Transcription services for imported German self-talk media."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import subprocess

from self_talk_coach.db import (
    get_transcript_by_media_file_id,
    list_media_files_for_transcription,
    replace_transcript,
    update_media_file_status,
)
from self_talk_coach.domain import MediaStatus, TranscriptStatus, TranscriptionOutcome
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


AudioExtractor = Callable[[Path, Path], None]


def extract_audio(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
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
        ],
        check=True,
        capture_output=True,
        text=True,
    )
```

- [ ] **Step 4: Update smoke test imports**

Modify `tests/test_smoke.py` so `test_import_stubs` imports `transcript_export` after Task 5 creates it. For this task, keep the import list unchanged.

- [ ] **Step 5: Run transcription tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py
```

Expected: PASS.

- [ ] **Step 6: Run smoke tests**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_smoke.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/self_talk_coach/transcribe.py tests/test_transcribe.py tests/test_smoke.py
git commit -m "feat: extract audio for transcription"
```

---

## Task 3: Faster-Whisper German Adapter

**Files:**
- Modify: `src/self_talk_coach/transcribe.py`
- Modify: `tests/test_transcribe.py`

- [ ] **Step 1: Add failing faster-whisper adapter tests**

Append to `tests/test_transcribe.py`:

```python
import sys

from self_talk_coach.transcribe import FasterWhisperTranscriber


class FakeWhisperSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class FakeWhisperInfo:
    duration = 2.5
    language = "de"


def test_faster_whisper_transcriber_forces_german(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    calls = []

    class FakeWhisperModel:
        def __init__(self, model_size, device, compute_type):
            calls.append(
                {
                    "model_size": model_size,
                    "device": device,
                    "compute_type": compute_type,
                }
            )

        def transcribe(self, audio_path_arg, language, vad_filter):
            calls.append(
                {
                    "audio_path": audio_path_arg,
                    "language": language,
                    "vad_filter": vad_filter,
                }
            )
            return (
                [
                    FakeWhisperSegment(0.0, 1.0, " Hallo "),
                    FakeWhisperSegment(1.0, 2.5, " Ich uebe Deutsch. "),
                ],
                FakeWhisperInfo(),
            )

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))

    transcriber = FasterWhisperTranscriber(model_size="tiny", device="cpu", compute_type="int8")
    draft = transcriber.transcribe(audio_path)

    assert calls == [
        {"model_size": "tiny", "device": "cpu", "compute_type": "int8"},
        {"audio_path": str(audio_path), "language": "de", "vad_filter": True},
    ]
    assert draft.language == "de"
    assert draft.duration_seconds == 2.5
    assert [segment.text for segment in draft.segments] == ["Hallo", "Ich uebe Deutsch."]
```

- [ ] **Step 2: Run the new adapter test and verify it fails**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py::test_faster_whisper_transcriber_forces_german
```

Expected: FAIL because `FasterWhisperTranscriber` does not exist.

- [ ] **Step 3: Add the faster-whisper adapter**

Append to `src/self_talk_coach/transcribe.py`:

```python
class FasterWhisperTranscriber(Transcriber):
    def __init__(
        self,
        *,
        model_size: str = "medium",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    @property
    def model_name(self) -> str:
        return f"faster-whisper:{self.model_size}:{self.device}:{self.compute_type}"

    def _load_model(self):
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
            str(audio_path),
            language="de",
            vad_filter=True,
        )
        segment_drafts = tuple(
            TranscriptSegmentDraft(
                start_seconds=float(segment.start),
                end_seconds=float(segment.end),
                text=segment.text.strip(),
            )
            for segment in segments
            if segment.text.strip()
        )
        return TranscriptDraft(
            language=str(getattr(info, "language", "de") or "de"),
            duration_seconds=getattr(info, "duration", None),
            segments=segment_drafts,
        )
```

- [ ] **Step 4: Run transcription tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/self_talk_coach/transcribe.py tests/test_transcribe.py
git commit -m "feat: add german whisper adapter"
```

---

## Task 4: Idempotent Transcription Storage Service

**Files:**
- Modify: `src/self_talk_coach/transcribe.py`
- Modify: `tests/test_transcribe.py`

- [ ] **Step 1: Add failing service tests**

Append to `tests/test_transcribe.py`:

```python
from self_talk_coach.db import (
    connect,
    get_transcript_by_media_file_id,
    init_db,
    insert_media_file,
)
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptionOutcome
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcribe import (
    TranscriptDraft,
    TranscriptSegmentDraft,
    transcribe_pending,
)


class FakeTranscriber:
    model_name = "fake-whisper"

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> TranscriptDraft:
        self.calls.append(audio_path)
        if self.should_fail:
            raise RuntimeError("model failed")
        return TranscriptDraft(
            language="de",
            duration_seconds=2.0,
            segments=(
                TranscriptSegmentDraft(0.0, 1.0, "Hallo."),
                TranscriptSegmentDraft(1.0, 2.0, "Ich uebe Deutsch."),
            ),
        )


def insert_imported_media(conn, managed_path: Path, *, content_hash: str = "storage-hash") -> int:
    return insert_media_file(
        conn,
        original_filename=managed_path.name,
        original_path=f"data/media/inbox/{managed_path.name}",
        managed_path=str(managed_path),
        content_hash=content_hash,
        size_bytes=managed_path.stat().st_size,
        duration_seconds=None,
        inferred_session_at="2026-06-01T08:30:00+00:00",
        date_confidence=DateConfidence.MEDIUM,
        status=MediaStatus.IMPORTED,
    )


def fake_audio_extractor(source_path: Path, destination_path: Path) -> None:
    assert source_path.exists()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(b"wav")


def test_transcribe_pending_stores_completed_transcript_and_segments(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    media_path = paths.media_processed / "2026" / "06" / "clip.mp4"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"video")
    transcriber = FakeTranscriber()

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = insert_imported_media(conn, media_path)
        conn.commit()
        results = transcribe_pending(
            conn,
            paths,
            transcriber=transcriber,
            audio_extractor=fake_audio_extractor,
        )
        transcript = get_transcript_by_media_file_id(conn, media_id)
        media_row = conn.execute("SELECT status, error_message FROM media_files WHERE id = ?", (media_id,)).fetchone()
        segment_rows = conn.execute(
            "SELECT start_seconds, end_seconds, text FROM transcript_segments ORDER BY id"
        ).fetchall()

    assert [result.outcome for result in results] == [TranscriptionOutcome.TRANSCRIBED]
    assert transcript is not None
    assert transcript["status"] == "completed"
    assert transcript["language"] == "de"
    assert transcript["model"] == "fake-whisper"
    assert media_row["status"] == "transcribed"
    assert media_row["error_message"] is None
    assert [dict(row) for row in segment_rows] == [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
        {"start_seconds": 1.0, "end_seconds": 2.0, "text": "Ich uebe Deutsch."},
    ]
    assert list(paths.media_processing.glob("*.wav")) == []


def test_transcribe_pending_skips_completed_transcript_on_rerun(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    media_path = paths.media_processed / "2026" / "06" / "clip.mp4"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"video")

    with connect(paths.db_path) as conn:
        init_db(conn)
        insert_imported_media(conn, media_path, content_hash="rerun-hash")
        conn.commit()
        first_transcriber = FakeTranscriber()
        first_results = transcribe_pending(
            conn,
            paths,
            transcriber=first_transcriber,
            audio_extractor=fake_audio_extractor,
        )
        second_transcriber = FakeTranscriber()
        second_results = transcribe_pending(
            conn,
            paths,
            transcriber=second_transcriber,
            audio_extractor=fake_audio_extractor,
        )

    assert [result.outcome for result in first_results] == [TranscriptionOutcome.TRANSCRIBED]
    assert second_results == []
    assert len(first_transcriber.calls) == 1
    assert second_transcriber.calls == []


def test_failed_transcription_is_recorded_and_can_be_retried(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    media_path = paths.media_processed / "2026" / "06" / "clip.mp4"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"video")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = insert_imported_media(conn, media_path, content_hash="recover-hash")
        conn.commit()
        failed_results = transcribe_pending(
            conn,
            paths,
            transcriber=FakeTranscriber(should_fail=True),
            audio_extractor=fake_audio_extractor,
        )
        failed_transcript = get_transcript_by_media_file_id(conn, media_id)
        recovered_results = transcribe_pending(
            conn,
            paths,
            transcriber=FakeTranscriber(),
            audio_extractor=fake_audio_extractor,
        )
        recovered_transcript = get_transcript_by_media_file_id(conn, media_id)
        transcript_count = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]

    assert [result.outcome for result in failed_results] == [TranscriptionOutcome.FAILED]
    assert failed_transcript is not None
    assert failed_transcript["status"] == "failed"
    assert failed_transcript["error_message"] == "model failed"
    assert [result.outcome for result in recovered_results] == [TranscriptionOutcome.TRANSCRIBED]
    assert recovered_transcript is not None
    assert recovered_transcript["status"] == "completed"
    assert recovered_transcript["error_message"] is None
    assert transcript_count == 1
```

- [ ] **Step 2: Run the new service tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py::test_transcribe_pending_stores_completed_transcript_and_segments tests/test_transcribe.py::test_transcribe_pending_skips_completed_transcript_on_rerun tests/test_transcribe.py::test_failed_transcription_is_recorded_and_can_be_retried
```

Expected: FAIL because `transcribe_pending` does not exist.

- [ ] **Step 3: Add transcription storage orchestration**

Append to `src/self_talk_coach/transcribe.py`:

```python
def audio_path_for(paths: AppPaths, media_file_id: int) -> Path:
    return paths.media_processing / f"media-{media_file_id}.wav"


def transcribe_media_file(
    conn: sqlite3.Connection,
    paths: AppPaths,
    media_row: sqlite3.Row,
    *,
    transcriber: Transcriber,
    audio_extractor: AudioExtractor = extract_audio,
) -> TranscriptionRunResult:
    media_file_id = int(media_row["id"])
    existing = get_transcript_by_media_file_id(conn, media_file_id)
    if existing is not None and existing["status"] == TranscriptStatus.COMPLETED.value:
        return TranscriptionRunResult(
            media_file_id=media_file_id,
            outcome=TranscriptionOutcome.SKIPPED,
            transcript_id=int(existing["id"]),
        )

    media_path = Path(str(media_row["managed_path"]))
    audio_path = audio_path_for(paths, media_file_id)
    try:
        audio_extractor(media_path, audio_path)
        draft = transcriber.transcribe(audio_path)
        transcript_id = replace_transcript(
            conn,
            media_file_id=media_file_id,
            language=draft.language,
            model=getattr(transcriber, "model_name", transcriber.__class__.__name__),
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
    except Exception as error:
        conn.rollback()
        transcript_id = replace_transcript(
            conn,
            media_file_id=media_file_id,
            language="de",
            model=getattr(transcriber, "model_name", transcriber.__class__.__name__),
            duration_seconds=None,
            status=TranscriptStatus.FAILED,
            error_message=str(error),
            segments=[],
        )
        update_media_file_status(
            conn,
            media_file_id=media_file_id,
            status=MediaStatus.FAILED,
            error_message=str(error),
        )
        conn.commit()
        return TranscriptionRunResult(
            media_file_id=media_file_id,
            outcome=TranscriptionOutcome.FAILED,
            transcript_id=transcript_id,
            error_message=str(error),
        )
    finally:
        if audio_path.exists():
            audio_path.unlink()


def transcribe_pending(
    conn: sqlite3.Connection,
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
```

- [ ] **Step 4: Run transcription tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcribe.py
```

Expected: PASS.

- [ ] **Step 5: Run DB tests**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_db.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/transcribe.py tests/test_transcribe.py
git commit -m "feat: store transcriptions idempotently"
```

---

## Task 5: Transcript JSON And Markdown Exports

**Files:**
- Create: `src/self_talk_coach/transcript_export.py`
- Create: `tests/test_transcript_export.py`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Write failing transcript export tests**

Create `tests/test_transcript_export.py`:

```python
import json
from pathlib import Path

from self_talk_coach.db import connect, init_db, insert_media_file, replace_transcript
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcript_export import TranscriptExportFormat, export_all_transcripts


def create_completed_transcript(paths: AppPaths) -> None:
    media_path = paths.media_processed / "2026" / "06" / "2026-06-01_0830_ab12cd34.mp4"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"video")
    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="daily.mp4",
            original_path="data/media/inbox/daily.mp4",
            managed_path=str(media_path),
            content_hash="ab12cd34ef56",
            size_bytes=media_path.stat().st_size,
            duration_seconds=None,
            inferred_session_at="2026-06-01T08:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.TRANSCRIBED,
        )
        replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="fake-whisper",
            duration_seconds=2.0,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
                {"start_seconds": 1.0, "end_seconds": 2.0, "text": "Ich uebe Deutsch."},
            ],
        )
        conn.commit()


def test_export_all_transcripts_writes_json(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    create_completed_transcript(paths)

    with connect(paths.db_path) as conn:
        exported = export_all_transcripts(conn, paths, export_format=TranscriptExportFormat.JSON)

    assert len(exported) == 1
    payload = json.loads(exported[0].read_text(encoding="utf-8"))
    assert payload["media"]["original_filename"] == "daily.mp4"
    assert payload["transcript"]["language"] == "de"
    assert payload["segments"] == [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo."},
        {"start_seconds": 1.0, "end_seconds": 2.0, "text": "Ich uebe Deutsch."},
    ]


def test_export_all_transcripts_writes_markdown(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    create_completed_transcript(paths)

    with connect(paths.db_path) as conn:
        exported = export_all_transcripts(conn, paths, export_format=TranscriptExportFormat.MARKDOWN)

    assert len(exported) == 1
    markdown = exported[0].read_text(encoding="utf-8")
    assert "# daily.mp4" in markdown
    assert "- Model: fake-whisper" in markdown
    assert "[0.00 - 1.00] Hallo." in markdown
    assert "[1.00 - 2.00] Ich uebe Deutsch." in markdown
```

- [ ] **Step 2: Run transcript export tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcript_export.py
```

Expected: FAIL because `self_talk_coach.transcript_export` does not exist.

- [ ] **Step 3: Implement transcript exports**

Create `src/self_talk_coach/transcript_export.py`:

```python
"""Transcript inspection exports."""

from __future__ import annotations

from enum import StrEnum
import json
from pathlib import Path
import sqlite3

from self_talk_coach.paths import AppPaths


class TranscriptExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


def list_completed_transcripts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            media_files.id AS media_file_id,
            media_files.original_filename,
            media_files.original_path,
            media_files.managed_path,
            media_files.content_hash,
            media_files.inferred_session_at,
            transcripts.id AS transcript_id,
            transcripts.language,
            transcripts.model,
            transcripts.duration_seconds,
            transcripts.created_at
        FROM transcripts
        JOIN media_files ON media_files.id = transcripts.media_file_id
        WHERE transcripts.status = 'completed'
        ORDER BY media_files.inferred_session_at, media_files.id
        """
    ).fetchall()


def list_segments(conn: sqlite3.Connection, transcript_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT start_seconds, end_seconds, text
        FROM transcript_segments
        WHERE transcript_id = ?
        ORDER BY start_seconds, id
        """,
        (transcript_id,),
    ).fetchall()


def export_stem(row: sqlite3.Row) -> str:
    managed_stem = Path(str(row["managed_path"])).stem
    return managed_stem or f"transcript-{row['transcript_id']}"


def transcript_payload(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    segments = [
        {
            "start_seconds": float(segment["start_seconds"]),
            "end_seconds": float(segment["end_seconds"]),
            "text": str(segment["text"]),
        }
        for segment in list_segments(conn, int(row["transcript_id"]))
    ]
    return {
        "media": {
            "id": int(row["media_file_id"]),
            "original_filename": str(row["original_filename"]),
            "original_path": str(row["original_path"]),
            "managed_path": str(row["managed_path"]),
            "content_hash": str(row["content_hash"]),
            "inferred_session_at": str(row["inferred_session_at"]),
        },
        "transcript": {
            "id": int(row["transcript_id"]),
            "language": str(row["language"]),
            "model": str(row["model"]),
            "duration_seconds": row["duration_seconds"],
            "created_at": str(row["created_at"]),
        },
        "segments": segments,
    }


def write_json_export(conn: sqlite3.Connection, row: sqlite3.Row, destination: Path) -> Path:
    payload = transcript_payload(conn, row)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def write_markdown_export(conn: sqlite3.Connection, row: sqlite3.Row, destination: Path) -> Path:
    segments = list_segments(conn, int(row["transcript_id"]))
    lines = [
        f"# {row['original_filename']}",
        "",
        f"- Media ID: {row['media_file_id']}",
        f"- Transcript ID: {row['transcript_id']}",
        f"- Language: {row['language']}",
        f"- Model: {row['model']}",
        f"- Session: {row['inferred_session_at']}",
        "",
        "## Segments",
        "",
    ]
    for segment in segments:
        lines.append(
            f"[{float(segment['start_seconds']):.2f} - {float(segment['end_seconds']):.2f}] {segment['text']}"
        )
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def export_all_transcripts(
    conn: sqlite3.Connection,
    paths: AppPaths,
    *,
    export_format: TranscriptExportFormat,
) -> list[Path]:
    paths.ensure_workspace()
    paths.exports_transcripts.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for row in list_completed_transcripts(conn):
        if export_format == TranscriptExportFormat.JSON:
            destination = paths.exports_transcripts / f"{export_stem(row)}.json"
            exported.append(write_json_export(conn, row, destination))
        elif export_format == TranscriptExportFormat.MARKDOWN:
            destination = paths.exports_transcripts / f"{export_stem(row)}.md"
            exported.append(write_markdown_export(conn, row, destination))
        else:
            raise ValueError(f"Unsupported transcript export format: {export_format}")
    return exported
```

- [ ] **Step 4: Update smoke imports**

Modify `tests/test_smoke.py`:

```python
def test_import_stubs() -> None:
    from self_talk_coach import (  # noqa: F401
        anki,
        cli,
        db,
        domain,
        enrich,
        ingest,
        mine,
        paths,
        transcript_export,
        transcribe,
    )
```

- [ ] **Step 5: Run transcript export tests and smoke tests**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_transcript_export.py tests/test_smoke.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/transcript_export.py tests/test_transcript_export.py tests/test_smoke.py
git commit -m "feat: export stored transcripts"
```

---

## Task 6: CLI Commands For Transcription And Transcript Export

**Files:**
- Modify: `src/self_talk_coach/cli.py`
- Modify: `tests/test_cli_media_library.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/test_cli_media_library.py`:

```python
from self_talk_coach.db import connect, init_db, insert_media_file, replace_transcript
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus


def test_cli_transcribe_stores_imported_media_transcript(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    media_path = data_root / "media" / "processed" / "2026" / "06" / "clip.mp4"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"video")
    runner.invoke(app, ["init", "--data-root", str(data_root)])
    with connect(data_root / "db" / "self_talk_coach.sqlite") as conn:
        init_db(conn)
        insert_media_file(
            conn,
            original_filename="clip.mp4",
            original_path="data/media/inbox/clip.mp4",
            managed_path=str(media_path),
            content_hash="cli-transcribe-hash",
            size_bytes=media_path.stat().st_size,
            duration_seconds=None,
            inferred_session_at="2026-06-01T08:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.IMPORTED,
        )
        conn.commit()

    def fake_audio_extractor(source_path: Path, destination_path: Path) -> None:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(b"wav")

    class FakeTranscriber:
        model_name = "fake-cli-whisper"

        def __init__(self, *, model_size: str, device: str, compute_type: str) -> None:
            self.model_size = model_size
            self.device = device
            self.compute_type = compute_type

        def transcribe(self, audio_path: Path):
            from self_talk_coach.transcribe import TranscriptDraft, TranscriptSegmentDraft

            return TranscriptDraft(
                language="de",
                duration_seconds=1.0,
                segments=(TranscriptSegmentDraft(0.0, 1.0, "Hallo CLI."),),
            )

    monkeypatch.setattr("self_talk_coach.cli.FasterWhisperTranscriber", FakeTranscriber)
    monkeypatch.setattr("self_talk_coach.cli.extract_audio", fake_audio_extractor)

    result = runner.invoke(app, ["transcribe", "--data-root", str(data_root), "--model-size", "tiny"])

    assert result.exit_code == 0
    assert "Transcribed: 1" in result.stdout
    assert "Skipped: 0" in result.stdout
    assert "Failed: 0" in result.stdout


def test_cli_export_transcripts_writes_markdown(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    media_path = data_root / "media" / "processed" / "2026" / "06" / "clip.mp4"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"video")
    runner.invoke(app, ["init", "--data-root", str(data_root)])
    with connect(data_root / "db" / "self_talk_coach.sqlite") as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="clip.mp4",
            original_path="data/media/inbox/clip.mp4",
            managed_path=str(media_path),
            content_hash="cli-export-hash",
            size_bytes=media_path.stat().st_size,
            duration_seconds=None,
            inferred_session_at="2026-06-01T08:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.TRANSCRIBED,
        )
        replace_transcript(
            conn,
            media_file_id=media_id,
            language="de",
            model="fake-cli-whisper",
            duration_seconds=1.0,
            status=TranscriptStatus.COMPLETED,
            error_message=None,
            segments=[{"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hallo Export."}],
        )
        conn.commit()

    result = runner.invoke(
        app,
        ["export", "transcripts", "--data-root", str(data_root), "--format", "markdown"],
    )

    assert result.exit_code == 0
    assert "Exported transcripts: 1" in result.stdout
    exported_files = list((data_root / "exports" / "transcripts").glob("*.md"))
    assert len(exported_files) == 1
    assert "Hallo Export." in exported_files[0].read_text(encoding="utf-8")
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_cli_media_library.py
```

Expected: FAIL because `transcribe` and `export transcripts` commands do not exist.

- [ ] **Step 3: Add CLI commands**

Replace `src/self_talk_coach/cli.py` with:

```python
"""Typer CLI entry point for self-talk-coach."""

from __future__ import annotations

from pathlib import Path

import typer

from self_talk_coach.db import connect, init_db
from self_talk_coach.domain import ImportOutcome, TranscriptionOutcome
from self_talk_coach.ingest import import_inbox
from self_talk_coach.paths import AppPaths
from self_talk_coach.transcribe import (
    FasterWhisperTranscriber,
    extract_audio,
    transcribe_pending,
)
from self_talk_coach.transcript_export import TranscriptExportFormat, export_all_transcripts

app = typer.Typer(help="self-talk-coach: German self-talk learning system")
export_app = typer.Typer(help="Export stored learning artifacts.")
app.add_typer(export_app, name="export")


@app.command()
def version() -> None:
    """Print version."""
    from self_talk_coach import __version__

    typer.echo(__version__)


@app.command()
def info() -> None:
    """Print project info."""
    typer.echo("self-talk-coach - local-first German self-talk learning system")


@app.command("init")
def init_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
) -> None:
    """Initialize local database and managed media folders."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
    typer.echo(f"Initialized workspace at {paths.data_root}")


@app.command("import")
def import_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
) -> None:
    """Import videos from the managed inbox into the local media library."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        results = import_inbox(conn, paths)

    imported = sum(1 for result in results if result.outcome == ImportOutcome.IMPORTED)
    duplicates = sum(1 for result in results if result.outcome == ImportOutcome.DUPLICATE)
    failed = sum(1 for result in results if result.outcome == ImportOutcome.FAILED)

    typer.echo(f"Imported: {imported}")
    typer.echo(f"Duplicates: {duplicates}")
    typer.echo(f"Failed: {failed}")


@app.command("transcribe")
def transcribe_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
    model_size: str = typer.Option("medium", "--model-size", help="faster-whisper model size."),
    device: str = typer.Option("cpu", "--device", help="faster-whisper device."),
    compute_type: str = typer.Option("int8", "--compute-type", help="faster-whisper compute type."),
) -> None:
    """Transcribe imported media and store timestamped German transcript segments."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    transcriber = FasterWhisperTranscriber(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
    )
    with connect(paths.db_path) as conn:
        init_db(conn)
        results = transcribe_pending(
            conn,
            paths,
            transcriber=transcriber,
            audio_extractor=extract_audio,
        )

    transcribed = sum(1 for result in results if result.outcome == TranscriptionOutcome.TRANSCRIBED)
    skipped = sum(1 for result in results if result.outcome == TranscriptionOutcome.SKIPPED)
    failed = sum(1 for result in results if result.outcome == TranscriptionOutcome.FAILED)
    typer.echo(f"Transcribed: {transcribed}")
    typer.echo(f"Skipped: {skipped}")
    typer.echo(f"Failed: {failed}")


@export_app.command("transcripts")
def export_transcripts_command(
    data_root: Path = typer.Option(Path("data"), "--data-root", help="Application data root."),
    export_format: TranscriptExportFormat = typer.Option(
        TranscriptExportFormat.JSON,
        "--format",
        help="Transcript export format.",
    ),
) -> None:
    """Export completed transcripts for inspection."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        exported = export_all_transcripts(conn, paths, export_format=export_format)
    typer.echo(f"Exported transcripts: {len(exported)}")
```

- [ ] **Step 4: Run CLI tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_cli_media_library.py
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
.venv/Scripts/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/cli.py tests/test_cli_media_library.py
git commit -m "feat: add transcription cli"
```

---

## Task 7: Documentation And Milestone Tracking

**Files:**
- Modify: `README.md`
- Modify: `BACKLOG.md`
- Modify: `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`

- [ ] **Step 1: Update README local workflow**

In `README.md`, update the local workflow under both quickstart sections to include transcription and transcript export:

```bash
# Lokale Mediathek initialisieren und eigene Videos importieren
stc init
# Put daily German self-talk videos into data/media/inbox/
stc import

# German transcription is stored in SQLite
stc transcribe

# Optional inspection exports
stc export transcripts --format json
stc export transcripts --format markdown
```

- [ ] **Step 2: Update BACKLOG**

Move this line from `Open - S2`:

```markdown
- transcription-storage - Implement ffmpeg/faster-whisper transcription into SQLite transcripts and transcript_segments tables.
```

To `Done this session (2026-06-01)` as:

```markdown
- transcription-storage - Planned and implemented ffmpeg/faster-whisper transcription into SQLite transcripts and transcript_segments tables.
```

Leave `first-language-analysis` and `review-queue` in `Open - S2`.

- [ ] **Step 3: Mark Milestone 2 planned in the design spec**

In `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`, under `### Milestone 2: Transcription Storage`, add:

```markdown
Implementation status: planned in `docs/superpowers/plans/2026-06-01-transcription-storage.md`; completed when `stc transcribe`, transcript storage tests, and transcript export tests pass the full test suite.
```

- [ ] **Step 4: Run final verification**

Run:

```bash
.venv/Scripts/python -m pytest -q
```

Expected: all tests pass.

Run:

```bash
git status --short
```

Expected: only README, BACKLOG, and design-spec documentation changes are unstaged.

- [ ] **Step 5: Commit docs**

```bash
git add README.md BACKLOG.md docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md
git commit -m "docs: document transcription storage workflow"
```

---

## Plan Self-Review

- Spec coverage:
  - Extract audio with ffmpeg: Task 2.
  - Transcribe with faster-whisper: Task 3.
  - Force German transcription: Task 3 verifies `language="de"`.
  - Store transcripts and timestamped segments in SQLite: Tasks 1 and 4.
  - Avoid duplicate transcriptions on rerun: Tasks 1 and 4.
  - Export transcripts to JSON or Markdown for inspection: Task 5 and Task 6.
  - CLI `stc transcribe`: Task 6.
  - Idempotent commands: Task 4 service tests and Task 6 CLI command.
- Deferred from this plan:
  - Language-learning candidate generation begins in Milestone 3.
  - Review queue behavior begins in Milestone 4.
  - Anki practice export remains in Milestone 5.
- Placeholder scan:
  - This plan does not use open-ended implementation instructions.
  - Each code task includes the test, implementation, command, expected result, and commit.
- Type consistency:
  - `TranscriptStatus` and `TranscriptionOutcome` are defined before use.
  - `TranscriptDraft`, `TranscriptSegmentDraft`, `FasterWhisperTranscriber`, `transcribe_pending`, and `TranscriptExportFormat` names match across implementation and tests.
  - Repository functions are introduced before orchestration and export layers depend on them.
