# Local DB Media Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Milestone 1: initialize the local SQLite database, create the managed media folders, and import inbox videos into an organized local media library.

**Architecture:** Add focused Python modules for paths, domain enums, SQLite schema management, and media import. The CLI remains a thin Typer orchestration layer; all durable state goes through SQLite and all media files move through the managed `data/media/*` folders.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, stdlib `pathlib`, stdlib `hashlib`, stdlib `shutil`, Typer, pytest.

---

## File Structure

- Create `src/self_talk_coach/domain.py`
  - Owns enums and small immutable value objects used by DB/media code.
- Create `src/self_talk_coach/paths.py`
  - Owns workspace path resolution and directory creation.
- Create `src/self_talk_coach/db.py`
  - Owns SQLite connection, schema creation, schema versioning, and media-file repository functions.
- Replace `src/self_talk_coach/ingest.py`
  - Owns inbox scanning, hashing, date inference, stable managed naming, and file moves.
- Modify `src/self_talk_coach/cli.py`
  - Adds `stc init` and `stc import` commands.
- Create `tests/test_paths.py`
  - Verifies workspace directory creation.
- Create `tests/test_db.py`
  - Verifies schema creation, idempotence, and repository functions.
- Create `tests/test_ingest_media_library.py`
  - Verifies media import, duplicate behavior, and failed-file behavior.
- Modify `tests/test_smoke.py`
  - Keeps import smoke coverage aligned with the new modules.

---

## Task 1: Domain Enums And Workspace Paths

**Files:**
- Create: `src/self_talk_coach/domain.py`
- Create: `src/self_talk_coach/paths.py`
- Test: `tests/test_paths.py`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Write failing tests for workspace paths**

Create `tests/test_paths.py`:

```python
from pathlib import Path

from self_talk_coach.paths import AppPaths


def test_app_paths_uses_data_root(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)

    assert paths.data_root == tmp_path
    assert paths.db_path == tmp_path / "db" / "self_talk_coach.sqlite"
    assert paths.media_inbox == tmp_path / "media" / "inbox"
    assert paths.media_processing == tmp_path / "media" / "processing"
    assert paths.media_processed == tmp_path / "media" / "processed"
    assert paths.media_failed == tmp_path / "media" / "failed"
    assert paths.media_archived == tmp_path / "media" / "archived"
    assert paths.exports_transcripts == tmp_path / "exports" / "transcripts"
    assert paths.exports_anki == tmp_path / "exports" / "anki"
    assert paths.exports_reports == tmp_path / "exports" / "reports"


def test_ensure_workspace_creates_directories(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)

    paths.ensure_workspace()

    assert paths.db_path.parent.is_dir()
    assert paths.media_inbox.is_dir()
    assert paths.media_processing.is_dir()
    assert paths.media_processed.is_dir()
    assert paths.media_failed.is_dir()
    assert paths.media_archived.is_dir()
    assert paths.exports_transcripts.is_dir()
    assert paths.exports_anki.is_dir()
    assert paths.exports_reports.is_dir()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_paths.py
```

Expected: FAIL with `ModuleNotFoundError` or import errors for `self_talk_coach.paths`.

- [ ] **Step 3: Add domain enums**

Create `src/self_talk_coach/domain.py`:

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
```

- [ ] **Step 4: Add workspace path helper**

Create `src/self_talk_coach/paths.py`:

```python
"""Filesystem paths for the local self-talk-coach workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Resolved paths under the application data root."""

    data_root: Path

    @classmethod
    def from_data_root(cls, data_root: Path | str = "data") -> "AppPaths":
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
        ):
            directory.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Update smoke test imports**

Modify `tests/test_smoke.py` so `test_import_stubs` imports the new modules:

```python
def test_import_stubs() -> None:
    from self_talk_coach import anki, cli, db, domain, enrich, ingest, mine, paths, transcribe  # noqa: F401
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_paths.py tests/test_smoke.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/self_talk_coach/domain.py src/self_talk_coach/paths.py tests/test_paths.py tests/test_smoke.py
git commit -m "feat: add local workspace paths"
```

---

## Task 2: SQLite Schema And Media Repository

**Files:**
- Create: `src/self_talk_coach/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing DB tests**

Create `tests/test_db.py`:

```python
from pathlib import Path

from self_talk_coach.db import connect, get_media_file_by_hash, init_db, insert_media_file
from self_talk_coach.domain import DateConfidence, MediaStatus


def test_init_db_creates_schema_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        init_db(conn)

        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
        }

    assert user_version == 1
    assert {
        "media_files",
        "transcripts",
        "transcript_segments",
        "learning_candidates",
        "practice_items",
        "review_events",
    } <= table_names


def test_insert_and_get_media_file_by_hash(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="random-video.mp4",
            original_path="data/media/inbox/random-video.mp4",
            managed_path="data/media/processed/2026/05/2026-05-31_2130_ab12cd34.mp4",
            content_hash="ab12cd34ef",
            size_bytes=128,
            duration_seconds=None,
            inferred_session_at="2026-05-31T21:30:00+00:00",
            date_confidence=DateConfidence.MEDIUM,
            status=MediaStatus.IMPORTED,
        )

        row = get_media_file_by_hash(conn, "ab12cd34ef")

    assert media_id > 0
    assert row is not None
    assert row["original_filename"] == "random-video.mp4"
    assert row["content_hash"] == "ab12cd34ef"
    assert row["date_confidence"] == "medium"
    assert row["status"] == "imported"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_db.py
```

Expected: FAIL because `self_talk_coach.db` does not exist.

- [ ] **Step 3: Implement DB module**

Create `src/self_talk_coach/db.py`:

```python
"""SQLite persistence for local self-talk-coach state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from self_talk_coach.domain import DateConfidence, MediaStatus

SCHEMA_VERSION = 1


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY,
            original_filename TEXT NOT NULL,
            original_path TEXT NOT NULL,
            managed_path TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL,
            duration_seconds REAL,
            inferred_session_at TEXT NOT NULL,
            date_confidence TEXT NOT NULL CHECK (date_confidence IN ('high', 'medium', 'low')),
            status TEXT NOT NULL CHECK (status IN ('imported', 'transcribed', 'analyzed', 'failed', 'archived')),
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_media_files_status
            ON media_files(status);

        CREATE INDEX IF NOT EXISTS idx_media_files_inferred_session_at
            ON media_files(inferred_session_at);

        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY,
            media_file_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
            language TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_seconds REAL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS transcript_segments (
            id INTEGER PRIMARY KEY,
            transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learning_candidates (
            id INTEGER PRIMARY KEY,
            candidate_type TEXT NOT NULL,
            transcript_segment_id INTEGER REFERENCES transcript_segments(id) ON DELETE SET NULL,
            original_text TEXT NOT NULL,
            suggested_text TEXT,
            explanation TEXT NOT NULL,
            severity INTEGER NOT NULL DEFAULT 1,
            usefulness INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            producer TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS practice_items (
            id INTEGER PRIMARY KEY,
            learning_candidate_id INTEGER NOT NULL REFERENCES learning_candidates(id) ON DELETE CASCADE,
            practice_type TEXT NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            notes TEXT,
            export_status TEXT NOT NULL DEFAULT 'not_exported',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS review_events (
            id INTEGER PRIMARY KEY,
            learning_candidate_id INTEGER REFERENCES learning_candidates(id) ON DELETE SET NULL,
            practice_item_id INTEGER REFERENCES practice_items(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def insert_media_file(
    conn: sqlite3.Connection,
    *,
    original_filename: str,
    original_path: str,
    managed_path: str,
    content_hash: str,
    size_bytes: int,
    duration_seconds: float | None,
    inferred_session_at: str,
    date_confidence: DateConfidence,
    status: MediaStatus,
    error_message: str | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO media_files (
            original_filename,
            original_path,
            managed_path,
            content_hash,
            size_bytes,
            duration_seconds,
            inferred_session_at,
            date_confidence,
            status,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            original_filename,
            original_path,
            managed_path,
            content_hash,
            size_bytes,
            duration_seconds,
            inferred_session_at,
            date_confidence.value,
            status.value,
            error_message,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_media_file_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM media_files WHERE content_hash = ?",
        (content_hash,),
    ).fetchone()
```

- [ ] **Step 4: Run DB tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_db.py
```

Expected: PASS.

- [ ] **Step 5: Run smoke tests**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_smoke.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/db.py tests/test_db.py
git commit -m "feat: add sqlite media schema"
```

---

## Task 3: Media Hashing, Date Inference, And Managed Names

**Files:**
- Replace: `src/self_talk_coach/ingest.py`
- Test: `tests/test_ingest_media_library.py`

- [ ] **Step 1: Write failing tests for media helpers**

Create `tests/test_ingest_media_library.py`:

```python
from datetime import UTC, datetime
from pathlib import Path

from self_talk_coach.domain import DateConfidence
from self_talk_coach.ingest import (
    SUPPORTED_MEDIA_EXTENSIONS,
    build_managed_filename,
    hash_file,
    infer_session_datetime,
    iter_media_files,
)


def test_iter_media_files_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "one.mp4").write_bytes(b"video")
    (tmp_path / "two.MOV").write_bytes(b"video")
    (tmp_path / "notes.txt").write_text("not media", encoding="utf-8")

    found = [path.name for path in iter_media_files(tmp_path)]

    assert found == ["one.mp4", "two.MOV"]
    assert ".mp4" in SUPPORTED_MEDIA_EXTENSIONS


def test_hash_file_returns_sha256_hex(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"abc")

    assert hash_file(media) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_infer_session_datetime_uses_modified_time(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"abc")
    expected = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)
    timestamp = expected.timestamp()
    media.touch()
    import os

    os.utime(media, (timestamp, timestamp))

    inferred, confidence = infer_session_datetime(media)

    assert inferred == expected
    assert confidence == DateConfidence.MEDIUM


def test_build_managed_filename_uses_timestamp_and_short_hash() -> None:
    session_at = datetime(2026, 5, 31, 21, 30, tzinfo=UTC)

    name = build_managed_filename(
        original_path=Path("random name.MP4"),
        session_at=session_at,
        content_hash="ab12cd34ef56",
    )

    assert name == "2026-05-31_2130_ab12cd34.mp4"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_ingest_media_library.py
```

Expected: FAIL because the helper functions do not exist.

- [ ] **Step 3: Implement media helper functions**

Replace `src/self_talk_coach/ingest.py` with:

```python
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
```

- [ ] **Step 4: Run helper tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_ingest_media_library.py
```

Expected: PASS for helper tests.

- [ ] **Step 5: Run existing tests**

Run:

```bash
.venv/Scripts/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/ingest.py tests/test_ingest_media_library.py
git commit -m "feat: add media import helpers"
```

---

## Task 4: Inbox Import Service

**Files:**
- Modify: `src/self_talk_coach/ingest.py`
- Modify: `tests/test_ingest_media_library.py`

- [ ] **Step 1: Add failing tests for inbox import**

Append to `tests/test_ingest_media_library.py`:

```python
from self_talk_coach.db import connect, get_media_file_by_hash, init_db
from self_talk_coach.domain import ImportOutcome
from self_talk_coach.ingest import import_inbox
from self_talk_coach.paths import AppPaths


def test_import_inbox_moves_file_to_processed_and_records_db(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()
    source = paths.media_inbox / "random123.mp4"
    source.write_bytes(b"video bytes")

    with connect(paths.db_path) as conn:
        init_db(conn)
        results = import_inbox(conn, paths)
        row = get_media_file_by_hash(conn, "39cf97c4f3d523af56ab40b61840f2be3579d44fb2b115a89361dca9f33b135c")

    assert len(results) == 1
    assert results[0].outcome == ImportOutcome.IMPORTED
    assert not source.exists()
    assert results[0].managed_path is not None
    assert results[0].managed_path.exists()
    assert row is not None
    assert row["original_filename"] == "random123.mp4"
    assert row["status"] == "imported"


def test_import_inbox_archives_duplicate_without_second_db_row(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    paths.ensure_workspace()

    with connect(paths.db_path) as conn:
        init_db(conn)

        first = paths.media_inbox / "first.mp4"
        first.write_bytes(b"same bytes")
        first_results = import_inbox(conn, paths)

        duplicate = paths.media_inbox / "second.mp4"
        duplicate.write_bytes(b"same bytes")
        duplicate_results = import_inbox(conn, paths)

        count = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]

    assert first_results[0].outcome == ImportOutcome.IMPORTED
    assert duplicate_results[0].outcome == ImportOutcome.DUPLICATE
    assert not duplicate.exists()
    assert duplicate_results[0].managed_path is not None
    assert duplicate_results[0].managed_path.exists()
    assert "archived" in duplicate_results[0].managed_path.parts
    assert count == 1
```

- [ ] **Step 2: Run import tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_ingest_media_library.py::test_import_inbox_moves_file_to_processed_and_records_db tests/test_ingest_media_library.py::test_import_inbox_archives_duplicate_without_second_db_row
```

Expected: FAIL because `import_inbox` is not implemented.

- [ ] **Step 3: Implement `import_inbox`**

Append to `src/self_talk_coach/ingest.py`:

```python
def import_inbox(conn, paths: AppPaths) -> list[ImportedMedia]:
    paths.ensure_workspace()
    results: list[ImportedMedia] = []

    for source_path in iter_media_files(paths.media_inbox):
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
                duplicate_path = archived_dir_for(paths, session_at) / managed_filename
                move_file(source_path, duplicate_path)
                results.append(
                    ImportedMedia(
                        source_path=source_path,
                        outcome=ImportOutcome.DUPLICATE,
                        managed_path=duplicate_path,
                        media_file_id=int(existing["id"]),
                        message="duplicate content hash",
                    )
                )
                continue

            destination = processed_dir_for(paths, session_at) / managed_filename
            move_file(source_path, destination)
            media_file_id = insert_media_file(
                conn,
                original_filename=source_path.name,
                original_path=str(source_path),
                managed_path=str(destination),
                content_hash=content_hash,
                size_bytes=destination.stat().st_size,
                duration_seconds=None,
                inferred_session_at=session_at.isoformat(),
                date_confidence=date_confidence,
                status=MediaStatus.IMPORTED,
            )
            results.append(
                ImportedMedia(
                    source_path=source_path,
                    outcome=ImportOutcome.IMPORTED,
                    managed_path=destination,
                    media_file_id=media_file_id,
                )
            )
        except Exception as exc:
            failed_path = paths.media_failed / source_path.name
            if source_path.exists():
                move_file(source_path, failed_path)
            results.append(
                ImportedMedia(
                    source_path=source_path,
                    outcome=ImportOutcome.FAILED,
                    managed_path=failed_path,
                    message=str(exc),
                )
            )

    return results
```

- [ ] **Step 4: Run import tests and verify they pass**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_ingest_media_library.py
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
git add src/self_talk_coach/ingest.py tests/test_ingest_media_library.py
git commit -m "feat: import inbox media into library"
```

---

## Task 5: CLI Commands For Init And Import

**Files:**
- Modify: `src/self_talk_coach/cli.py`
- Test: `tests/test_cli_media_library.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli_media_library.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from self_talk_coach.cli import app


def test_cli_init_creates_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"

    result = runner.invoke(app, ["init", "--data-root", str(data_root)])

    assert result.exit_code == 0
    assert "Initialized workspace" in result.stdout
    assert (data_root / "db" / "self_talk_coach.sqlite").exists()
    assert (data_root / "media" / "inbox").is_dir()


def test_cli_import_imports_inbox_file(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    inbox = data_root / "media" / "inbox"

    init_result = runner.invoke(app, ["init", "--data-root", str(data_root)])
    assert init_result.exit_code == 0

    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "daily.mp4").write_bytes(b"video bytes")

    result = runner.invoke(app, ["import", "--data-root", str(data_root)])

    assert result.exit_code == 0
    assert "Imported: 1" in result.stdout
    assert "Duplicates: 0" in result.stdout
    assert "Failed: 0" in result.stdout
    assert not (inbox / "daily.mp4").exists()
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
.venv/Scripts/python -m pytest -q tests/test_cli_media_library.py
```

Expected: FAIL because `init` and `import` commands do not exist.

- [ ] **Step 3: Implement CLI commands**

Replace `src/self_talk_coach/cli.py` with:

```python
"""Typer CLI entry point for self-talk-coach."""

from __future__ import annotations

from pathlib import Path

import typer

from self_talk_coach.db import connect, init_db
from self_talk_coach.domain import ImportOutcome
from self_talk_coach.ingest import import_inbox
from self_talk_coach.paths import AppPaths

app = typer.Typer(help="self-talk-coach: German self-talk learning system")


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
git commit -m "feat: add init and import cli"
```

---

## Task 6: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `BACKLOG.md`
- Modify: `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`

- [ ] **Step 1: Update README quickstart for the new local-first flow**

Modify the quickstart commands in `README.md` so the first local workflow is:

```bash
stc init
# Put daily German self-talk videos into data/media/inbox/
stc import
```

Keep the existing dependency setup notes for Python, ffmpeg, and editable install.

- [ ] **Step 2: Update BACKLOG with the milestone direction**

Add an S2 entry under Open for transcription storage:

```markdown
- transcription-storage - Implement ffmpeg/faster-whisper transcription into SQLite transcripts and transcript_segments tables.
```

Add an S3 entry under Open for first analysis:

```markdown
- first-language-analysis - Generate pending correction and upgrade candidates from stored transcript segments.
```

Add an S3 entry under Open for review queue:

```markdown
- review-queue - Add commands to list, show, approve, reject, and defer learning candidates.
```

- [ ] **Step 3: Mark Milestone 1 implemented in the design spec**

In `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`, update the Milestone 1 heading to:

```markdown
### Milestone 1: Local Database And Media Library
```

Then add this line below the heading:

```markdown
Implementation status: planned in `docs/superpowers/plans/2026-05-31-local-db-media-library.md`; completed when `stc init` and `stc import` pass the full test suite.
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
git commit -m "docs: document local media library workflow"
```

---

## Plan Self-Review

- Spec coverage:
  - Local-first SQLite source of truth: Task 2.
  - Managed `data/media/*` folders: Task 1.
  - Inbox import and processed/archive organization: Tasks 3 and 4.
  - Unreliable filenames and hash-based managed names: Task 3.
  - Idempotent commands and duplicate behavior: Task 4.
  - CLI surface for `stc init` and `stc import`: Task 5.
  - Docs and backlog alignment: Task 6.
- Deferred from this plan:
  - Transcription storage begins in Milestone 2.
  - Language analysis begins in Milestone 3.
  - Review queue begins in Milestone 4.
  - Anki export begins in Milestone 5.
- Placeholder scan:
  - This plan contains no open-ended implementation steps.
  - Each code task includes the expected test, implementation, command, and commit.
- Type consistency:
  - `DateConfidence`, `MediaStatus`, and `ImportOutcome` are defined before use.
  - `AppPaths`, `connect`, `init_db`, `insert_media_file`, and `import_inbox` signatures are consistent across tasks.

