# First Language Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Milestone 3: generate pending vocabulary, phrase-upgrade, and basic-correction learning candidates from stored transcript segments, with every candidate linked to a transcript segment.

**Architecture:** Add candidate enums and SQLite repository functions first, then create a local deterministic analysis module with small rule-based analyzers. The CLI remains thin: `stc analyze` initializes the workspace, runs the analyzer over completed transcript segments, stores idempotent pending candidates, and updates analyzed media status. No cards, review decisions, cloud calls, or LLM analysis are introduced in this milestone.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, stdlib `re`, stdlib `dataclasses`, Typer, pytest, existing `resources/baseline-de-b1.txt`.

---

## File Structure

- Modify `src/self_talk_coach/domain.py`
  - Adds candidate type/status enums and analysis run outcome enum.
- Modify `src/self_talk_coach/db.py`
  - Adds candidate indexes, transcript-segment query functions, and idempotent learning-candidate insertion.
- Create `src/self_talk_coach/analyze.py`
  - Owns deterministic candidate generators and analysis orchestration.
- Modify `src/self_talk_coach/cli.py`
  - Adds `stc analyze`.
- Create `tests/test_analyze.py`
  - Verifies tokenizer/baseline behavior, deterministic candidate generation, idempotent storage, retry behavior, and media status updates.
- Modify `tests/test_db.py`
  - Verifies learning-candidate repository functions and duplicate prevention.
- Modify `tests/test_cli_media_library.py`
  - Adds CLI coverage for `stc analyze`.
- Modify `tests/test_smoke.py`
  - Keeps import smoke coverage aligned.
- Modify `README.md`
  - Adds `stc analyze` to the local workflow.
- Modify `BACKLOG.md`
  - Moves `first-language-analysis` from Open to Done this session.
- Modify `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`
  - Marks Milestone 3 as planned in this file and completed when `stc analyze` and analysis tests pass.

---

## Analysis Scope Decisions

- This milestone is local-first and deterministic. It does not call Anthropic, OpenAI, or any network service.
- Vocabulary candidates use `resources/baseline-de-b1.txt` as the known-word baseline and surface words not in that baseline.
- Phrase upgrades and basic corrections use a small checked-in rule catalog. The first rule set is intentionally tiny and testable:
  - Correction: `ich habe gegangen/gefahren/gelaufen` -> `ich bin ...`
  - Correction: `weil ich habe` -> `weil ich ... habe`
  - Upgrade: `sehr gut` -> `richtig gut`
  - Upgrade: `ein bisschen` -> `etwas`
- The analyzer creates `learning_candidates` only. It does not create `practice_items`.
- Idempotence is enforced in storage so rerunning `stc analyze` does not duplicate candidates.

---

## Task 1: Candidate Domain And Repository

**Files:**
- Modify: `src/self_talk_coach/domain.py`
- Modify: `src/self_talk_coach/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing candidate repository tests**

Append to `tests/test_db.py`:

```python
from self_talk_coach.domain import CandidateStatus, CandidateType
from self_talk_coach.db import (
    insert_learning_candidate,
    list_completed_transcript_segments_for_analysis,
)


def create_completed_segment(conn: sqlite3.Connection) -> tuple[int, int, int]:
    media_id = insert_test_media(
        conn,
        content_hash="analysis-media-hash",
        status=MediaStatus.TRANSCRIBED,
        inferred_session_at="2026-06-02T08:00:00+00:00",
    )
    transcript_id = replace_transcript(
        conn,
        media_file_id=media_id,
        language="de",
        model="fake-whisper",
        duration_seconds=2.0,
        status=TranscriptStatus.COMPLETED,
        error_message=None,
        segments=[
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "Ich habe gegangen."},
        ],
    )
    segment_id = conn.execute(
        "SELECT id FROM transcript_segments WHERE transcript_id = ?",
        (transcript_id,),
    ).fetchone()["id"]
    return media_id, transcript_id, segment_id


def test_list_completed_transcript_segments_for_analysis(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        media_id, transcript_id, segment_id = create_completed_segment(conn)
        rows = list_completed_transcript_segments_for_analysis(conn)

    assert [row["segment_id"] for row in rows] == [segment_id]
    assert rows[0]["media_file_id"] == media_id
    assert rows[0]["transcript_id"] == transcript_id
    assert rows[0]["text"] == "Ich habe gegangen."
    assert rows[0]["inferred_session_at"] == "2026-06-02T08:00:00+00:00"


def test_insert_learning_candidate_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "self_talk_coach.sqlite"

    with connect(db_path) as conn:
        init_db(conn)
        _, _, segment_id = create_completed_segment(conn)
        first_id = insert_learning_candidate(
            conn,
            candidate_type=CandidateType.GRAMMAR_CORRECTION,
            transcript_segment_id=segment_id,
            original_text="ich habe gegangen",
            suggested_text="ich bin gegangen",
            explanation="Use sein with movement verbs in Perfekt.",
            severity=3,
            usefulness=5,
            status=CandidateStatus.PENDING,
            producer="rule:movement-perfect",
        )
        second_id = insert_learning_candidate(
            conn,
            candidate_type=CandidateType.GRAMMAR_CORRECTION,
            transcript_segment_id=segment_id,
            original_text="ich habe gegangen",
            suggested_text="ich bin gegangen",
            explanation="Use sein with movement verbs in Perfekt.",
            severity=3,
            usefulness=5,
            status=CandidateStatus.PENDING,
            producer="rule:movement-perfect",
        )
        rows = conn.execute("SELECT * FROM learning_candidates").fetchall()

    assert first_id == second_id
    assert len(rows) == 1
    assert rows[0]["candidate_type"] == "grammar_correction"
    assert rows[0]["status"] == "pending"
```

- [ ] **Step 2: Run DB tests and verify they fail**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_db.py
```

Expected: FAIL with import errors for `CandidateStatus`, `CandidateType`, `insert_learning_candidate`, and `list_completed_transcript_segments_for_analysis`.

- [ ] **Step 3: Add candidate enums**

Modify `src/self_talk_coach/domain.py` by appending:

```python
class CandidateType(StrEnum):
    """Learning-candidate categories created before review."""

    GRAMMAR_CORRECTION = "grammar_correction"
    PHRASE_UPGRADE = "phrase_upgrade"
    VOCAB_CANDIDATE = "vocab_candidate"
    COLLOCATION = "collocation"
    ARTICLE_GENDER = "article_gender"
    SENTENCE_REWRITE = "sentence_rewrite"
    FILLER_PATTERN = "filler_pattern"
    RECURRING_PATTERN = "recurring_pattern"


class CandidateStatus(StrEnum):
    """Review lifecycle state for a learning candidate."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class AnalysisOutcome(StrEnum):
    """Outcome category for one analysis run item."""

    ANALYZED = "analyzed"
    SKIPPED = "skipped"
    FAILED = "failed"
```

- [ ] **Step 4: Add candidate repository functions and indexes**

Update the domain import in `src/self_talk_coach/db.py`:

```python
from self_talk_coach.domain import (
    CandidateStatus,
    CandidateType,
    DateConfidence,
    MediaStatus,
    TranscriptStatus,
)
```

In `init_db`, after the `CREATE TABLE IF NOT EXISTS learning_candidates` block and before `practice_items`, add:

```sql
        CREATE INDEX IF NOT EXISTS idx_learning_candidates_status
            ON learning_candidates(status);

        CREATE INDEX IF NOT EXISTS idx_learning_candidates_segment
            ON learning_candidates(transcript_segment_id);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_candidates_identity
            ON learning_candidates(
                producer,
                candidate_type,
                transcript_segment_id,
                original_text,
                COALESCE(suggested_text, '')
            );
```

Append these functions to `src/self_talk_coach/db.py`:

```python
def list_completed_transcript_segments_for_analysis(
    conn: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            media_files.id AS media_file_id,
            media_files.inferred_session_at AS inferred_session_at,
            transcripts.id AS transcript_id,
            transcript_segments.id AS segment_id,
            transcript_segments.start_seconds AS start_seconds,
            transcript_segments.end_seconds AS end_seconds,
            transcript_segments.text AS text
        FROM transcript_segments
        JOIN transcripts ON transcripts.id = transcript_segments.transcript_id
        JOIN media_files ON media_files.id = transcripts.media_file_id
        WHERE transcripts.status = 'completed'
          AND media_files.status = 'transcribed'
        ORDER BY media_files.inferred_session_at, transcript_segments.start_seconds, transcript_segments.id
        """
    ).fetchall()


def insert_learning_candidate(
    conn: sqlite3.Connection,
    *,
    candidate_type: CandidateType,
    transcript_segment_id: int,
    original_text: str,
    suggested_text: str | None,
    explanation: str,
    severity: int,
    usefulness: int,
    status: CandidateStatus,
    producer: str,
) -> int:
    conn.execute(
        """
        INSERT OR IGNORE INTO learning_candidates (
            candidate_type,
            transcript_segment_id,
            original_text,
            suggested_text,
            explanation,
            severity,
            usefulness,
            status,
            producer
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_type.value,
            transcript_segment_id,
            original_text,
            suggested_text,
            explanation,
            severity,
            usefulness,
            status.value,
            producer,
        ),
    )
    row = conn.execute(
        """
        SELECT id
        FROM learning_candidates
        WHERE producer = ?
          AND candidate_type = ?
          AND transcript_segment_id = ?
          AND original_text = ?
          AND COALESCE(suggested_text, '') = COALESCE(?, '')
        """,
        (
            producer,
            candidate_type.value,
            transcript_segment_id,
            original_text,
            suggested_text,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("learning candidate insert could not be read back")
    return int(row["id"])
```

- [ ] **Step 5: Run DB tests and verify they pass**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_db.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/domain.py src/self_talk_coach/db.py tests/test_db.py
git commit -m "feat: add learning candidate repository"
```

---

## Task 2: Deterministic Analysis Rules

**Files:**
- Create: `src/self_talk_coach/analyze.py`
- Create: `tests/test_analyze.py`
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Write failing analyzer unit tests**

Create `tests/test_analyze.py`:

```python
from pathlib import Path

from self_talk_coach.analyze import (
    CandidateDraft,
    analyze_segment_text,
    load_baseline_words,
    tokenize_german_words,
)
from self_talk_coach.domain import CandidateType


def test_load_baseline_words_normalizes_lowercase(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("Hallo\ngehen\nÜber\n", encoding="utf-8")

    assert load_baseline_words(baseline) == {"hallo", "gehen", "über"}


def test_tokenize_german_words_keeps_umlauts_and_ss() -> None:
    assert tokenize_german_words("Ich übe Fußball, außerdem B2-Wörter!") == [
        "Ich",
        "übe",
        "Fußball",
        "außerdem",
        "B",
        "Wörter",
    ]


def test_analyze_segment_text_creates_vocab_upgrade_and_correction_candidates() -> None:
    baseline_words = {"ich", "habe", "bin", "das", "ist", "sehr", "gut", "weil"}

    drafts = analyze_segment_text(
        segment_id=42,
        text="Ich habe gegangen, weil ich habe ein bisschen Sehnsucht. Das ist sehr gut.",
        baseline_words=baseline_words,
    )

    assert drafts == [
        CandidateDraft(
            candidate_type=CandidateType.VOCAB_CANDIDATE,
            transcript_segment_id=42,
            original_text="gegangen",
            suggested_text=None,
            explanation="Word is not in the configured B1 baseline.",
            severity=1,
            usefulness=3,
            producer="vocab:baseline-de-b1",
        ),
        CandidateDraft(
            candidate_type=CandidateType.VOCAB_CANDIDATE,
            transcript_segment_id=42,
            original_text="ein",
            suggested_text=None,
            explanation="Word is not in the configured B1 baseline.",
            severity=1,
            usefulness=3,
            producer="vocab:baseline-de-b1",
        ),
        CandidateDraft(
            candidate_type=CandidateType.VOCAB_CANDIDATE,
            transcript_segment_id=42,
            original_text="bisschen",
            suggested_text=None,
            explanation="Word is not in the configured B1 baseline.",
            severity=1,
            usefulness=3,
            producer="vocab:baseline-de-b1",
        ),
        CandidateDraft(
            candidate_type=CandidateType.VOCAB_CANDIDATE,
            transcript_segment_id=42,
            original_text="Sehnsucht",
            suggested_text=None,
            explanation="Word is not in the configured B1 baseline.",
            severity=1,
            usefulness=3,
            producer="vocab:baseline-de-b1",
        ),
        CandidateDraft(
            candidate_type=CandidateType.GRAMMAR_CORRECTION,
            transcript_segment_id=42,
            original_text="Ich habe gegangen",
            suggested_text="Ich bin gegangen",
            explanation="Use sein, not haben, with common movement verbs in Perfekt.",
            severity=3,
            usefulness=5,
            producer="rule:movement-perfect",
        ),
        CandidateDraft(
            candidate_type=CandidateType.GRAMMAR_CORRECTION,
            transcript_segment_id=42,
            original_text="weil ich habe",
            suggested_text="weil ich ... habe",
            explanation="In subordinate clauses with weil, the conjugated verb moves to the end.",
            severity=3,
            usefulness=5,
            producer="rule:weil-verb-final",
        ),
        CandidateDraft(
            candidate_type=CandidateType.PHRASE_UPGRADE,
            transcript_segment_id=42,
            original_text="ein bisschen",
            suggested_text="etwas",
            explanation="Etwas is often a cleaner, more compact alternative to ein bisschen.",
            severity=1,
            usefulness=3,
            producer="rule:ein-bisschen-etwas",
        ),
        CandidateDraft(
            candidate_type=CandidateType.PHRASE_UPGRADE,
            transcript_segment_id=42,
            original_text="sehr gut",
            suggested_text="richtig gut",
            explanation="Richtig gut sounds more conversational in many self-talk contexts.",
            severity=1,
            usefulness=3,
            producer="rule:sehr-gut-richtig-gut",
        ),
    ]
```

- [ ] **Step 2: Run analyzer tests and verify they fail**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_analyze.py
```

Expected: FAIL because `self_talk_coach.analyze` does not define these functions.

- [ ] **Step 3: Implement deterministic analysis module**

Create `src/self_talk_coach/analyze.py`:

```python
"""Local-first language analysis for transcript segments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from self_talk_coach.domain import CandidateType

WORD_PATTERN = re.compile(r"[A-Za-zÄÖÜäöüß]+")


@dataclass(frozen=True)
class CandidateDraft:
    candidate_type: CandidateType
    transcript_segment_id: int
    original_text: str
    suggested_text: str | None
    explanation: str
    severity: int
    usefulness: int
    producer: str


@dataclass(frozen=True)
class PhraseRule:
    candidate_type: CandidateType
    pattern: re.Pattern[str]
    suggested_text: str
    explanation: str
    severity: int
    usefulness: int
    producer: str


PHRASE_RULES = (
    PhraseRule(
        candidate_type=CandidateType.GRAMMAR_CORRECTION,
        pattern=re.compile(r"\b(?P<subject>[Ii]ch) habe (?P<verb>gegangen|gefahren|gelaufen)\b"),
        suggested_text="{subject} bin {verb}",
        explanation="Use sein, not haben, with common movement verbs in Perfekt.",
        severity=3,
        usefulness=5,
        producer="rule:movement-perfect",
    ),
    PhraseRule(
        candidate_type=CandidateType.GRAMMAR_CORRECTION,
        pattern=re.compile(r"\bweil ich habe\b", re.IGNORECASE),
        suggested_text="weil ich ... habe",
        explanation="In subordinate clauses with weil, the conjugated verb moves to the end.",
        severity=3,
        usefulness=5,
        producer="rule:weil-verb-final",
    ),
    PhraseRule(
        candidate_type=CandidateType.PHRASE_UPGRADE,
        pattern=re.compile(r"\bein bisschen\b", re.IGNORECASE),
        suggested_text="etwas",
        explanation="Etwas is often a cleaner, more compact alternative to ein bisschen.",
        severity=1,
        usefulness=3,
        producer="rule:ein-bisschen-etwas",
    ),
    PhraseRule(
        candidate_type=CandidateType.PHRASE_UPGRADE,
        pattern=re.compile(r"\bsehr gut\b", re.IGNORECASE),
        suggested_text="richtig gut",
        explanation="Richtig gut sounds more conversational in many self-talk contexts.",
        severity=1,
        usefulness=3,
        producer="rule:sehr-gut-richtig-gut",
    ),
)


def load_baseline_words(path: Path) -> set[str]:
    return {
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def tokenize_german_words(text: str) -> list[str]:
    return WORD_PATTERN.findall(text)


def vocab_candidates(
    *,
    segment_id: int,
    text: str,
    baseline_words: set[str],
) -> list[CandidateDraft]:
    seen: set[str] = set()
    drafts: list[CandidateDraft] = []
    for token in tokenize_german_words(text):
        normalized = token.lower()
        if normalized in baseline_words or normalized in seen:
            continue
        seen.add(normalized)
        drafts.append(
            CandidateDraft(
                candidate_type=CandidateType.VOCAB_CANDIDATE,
                transcript_segment_id=segment_id,
                original_text=token,
                suggested_text=None,
                explanation="Word is not in the configured B1 baseline.",
                severity=1,
                usefulness=3,
                producer="vocab:baseline-de-b1",
            )
        )
    return drafts


def phrase_rule_candidates(*, segment_id: int, text: str) -> list[CandidateDraft]:
    drafts: list[CandidateDraft] = []
    for rule in PHRASE_RULES:
        for match in rule.pattern.finditer(text):
            suggested_text = rule.suggested_text.format(**match.groupdict())
            drafts.append(
                CandidateDraft(
                    candidate_type=rule.candidate_type,
                    transcript_segment_id=segment_id,
                    original_text=match.group(0),
                    suggested_text=suggested_text,
                    explanation=rule.explanation,
                    severity=rule.severity,
                    usefulness=rule.usefulness,
                    producer=rule.producer,
                )
            )
    return drafts


def analyze_segment_text(
    *,
    segment_id: int,
    text: str,
    baseline_words: set[str],
) -> list[CandidateDraft]:
    return [
        *vocab_candidates(
            segment_id=segment_id,
            text=text,
            baseline_words=baseline_words,
        ),
        *phrase_rule_candidates(segment_id=segment_id, text=text),
    ]
```

- [ ] **Step 4: Update smoke imports**

Modify `tests/test_smoke.py`:

```python
def test_import_stubs() -> None:
    from self_talk_coach import (  # noqa: F401
        analyze,
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

- [ ] **Step 5: Run analyzer and smoke tests**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_analyze.py tests\test_smoke.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/self_talk_coach/analyze.py tests/test_analyze.py tests/test_smoke.py
git commit -m "feat: add deterministic analysis rules"
```

---

## Task 3: Analysis Storage Orchestration

**Files:**
- Modify: `src/self_talk_coach/analyze.py`
- Modify: `tests/test_analyze.py`

- [ ] **Step 1: Add failing orchestration tests**

Append to `tests/test_analyze.py`:

```python
import sqlite3

from self_talk_coach.analyze import AnalysisRunResult, analyze_pending
from self_talk_coach.db import (
    connect,
    get_transcript_by_media_file_id,
    init_db,
    insert_media_file,
    replace_transcript,
)
from self_talk_coach.domain import (
    AnalysisOutcome,
    DateConfidence,
    MediaStatus,
    TranscriptStatus,
)
from self_talk_coach.paths import AppPaths


def create_transcribed_media_with_segment(
    conn: sqlite3.Connection,
    *,
    content_hash: str,
    text: str,
) -> int:
    media_id = insert_media_file(
        conn,
        original_filename=f"{content_hash}.mp4",
        original_path=f"data/media/inbox/{content_hash}.mp4",
        managed_path=f"data/media/processed/2026/06/{content_hash}.mp4",
        content_hash=content_hash,
        size_bytes=128,
        duration_seconds=None,
        inferred_session_at="2026-06-02T08:00:00+00:00",
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
        segments=[{"start_seconds": 0.0, "end_seconds": 2.0, "text": text}],
    )
    return media_id


def test_analyze_pending_stores_pending_candidates_and_marks_media_analyzed(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    baseline_path = tmp_path / "baseline.txt"
    baseline_path.write_text("ich\nhabe\nbin\n", encoding="utf-8")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = create_transcribed_media_with_segment(
            conn,
            content_hash="analysis-hash",
            text="Ich habe gegangen.",
        )
        conn.commit()

        results = analyze_pending(conn, paths, baseline_path=baseline_path)
        rows = conn.execute(
            "SELECT candidate_type, original_text, suggested_text, status FROM learning_candidates ORDER BY id"
        ).fetchall()
        media = conn.execute(
            "SELECT status, error_message FROM media_files WHERE id = ?",
            (media_id,),
        ).fetchone()

    assert results == [
        AnalysisRunResult(
            media_file_id=media_id,
            outcome=AnalysisOutcome.ANALYZED,
            candidates_created=2,
            error_message=None,
        )
    ]
    assert [dict(row) for row in rows] == [
        {
            "candidate_type": "vocab_candidate",
            "original_text": "gegangen",
            "suggested_text": None,
            "status": "pending",
        },
        {
            "candidate_type": "grammar_correction",
            "original_text": "Ich habe gegangen",
            "suggested_text": "Ich bin gegangen",
            "status": "pending",
        },
    ]
    assert dict(media) == {"status": "analyzed", "error_message": None}


def test_analyze_pending_is_idempotent_on_rerun(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path / "data")
    baseline_path = tmp_path / "baseline.txt"
    baseline_path.write_text("ich\nhabe\nbin\n", encoding="utf-8")

    with connect(paths.db_path) as conn:
        init_db(conn)
        media_id = create_transcribed_media_with_segment(
            conn,
            content_hash="rerun-analysis-hash",
            text="Ich habe gegangen.",
        )
        conn.commit()

        first = analyze_pending(conn, paths, baseline_path=baseline_path)
        second = analyze_pending(conn, paths, baseline_path=baseline_path)
        count = conn.execute("SELECT COUNT(*) FROM learning_candidates").fetchone()[0]

    assert [result.outcome for result in first] == [AnalysisOutcome.ANALYZED]
    assert second == []
    assert count == 2
```

- [ ] **Step 2: Run orchestration tests and verify they fail**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_analyze.py
```

Expected: FAIL because `AnalysisRunResult` and `analyze_pending` do not exist.

- [ ] **Step 3: Implement analysis orchestration**

Append to `src/self_talk_coach/analyze.py`:

```python
from collections import defaultdict
import sqlite3

from self_talk_coach.db import (
    insert_learning_candidate,
    list_completed_transcript_segments_for_analysis,
    update_media_file_status,
)
from self_talk_coach.domain import AnalysisOutcome, CandidateStatus, MediaStatus
from self_talk_coach.paths import AppPaths

DEFAULT_BASELINE_PATH = Path("resources/baseline-de-b1.txt")


@dataclass(frozen=True)
class AnalysisRunResult:
    media_file_id: int
    outcome: AnalysisOutcome
    candidates_created: int = 0
    error_message: str | None = None


def store_candidate_draft(conn: sqlite3.Connection, draft: CandidateDraft) -> int:
    return insert_learning_candidate(
        conn,
        candidate_type=draft.candidate_type,
        transcript_segment_id=draft.transcript_segment_id,
        original_text=draft.original_text,
        suggested_text=draft.suggested_text,
        explanation=draft.explanation,
        severity=draft.severity,
        usefulness=draft.usefulness,
        status=CandidateStatus.PENDING,
        producer=draft.producer,
    )


def analyze_pending(
    conn: sqlite3.Connection,
    paths: AppPaths,
    *,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
) -> list[AnalysisRunResult]:
    paths.ensure_workspace()
    baseline_words = load_baseline_words(baseline_path)
    rows_by_media: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in list_completed_transcript_segments_for_analysis(conn):
        rows_by_media[int(row["media_file_id"])].append(row)

    results: list[AnalysisRunResult] = []
    for media_file_id, rows in rows_by_media.items():
        try:
            before_count = conn.execute(
                "SELECT COUNT(*) FROM learning_candidates"
            ).fetchone()[0]
            for row in rows:
                drafts = analyze_segment_text(
                    segment_id=int(row["segment_id"]),
                    text=str(row["text"]),
                    baseline_words=baseline_words,
                )
                for draft in drafts:
                    store_candidate_draft(conn, draft)
            after_count = conn.execute(
                "SELECT COUNT(*) FROM learning_candidates"
            ).fetchone()[0]
            update_media_file_status(
                conn,
                media_file_id=media_file_id,
                status=MediaStatus.ANALYZED,
                error_message=None,
            )
            conn.commit()
            results.append(
                AnalysisRunResult(
                    media_file_id=media_file_id,
                    outcome=AnalysisOutcome.ANALYZED,
                    candidates_created=int(after_count - before_count),
                    error_message=None,
                )
            )
        except Exception as exc:
            conn.rollback()
            update_media_file_status(
                conn,
                media_file_id=media_file_id,
                status=MediaStatus.FAILED,
                error_message=str(exc),
            )
            conn.commit()
            results.append(
                AnalysisRunResult(
                    media_file_id=media_file_id,
                    outcome=AnalysisOutcome.FAILED,
                    candidates_created=0,
                    error_message=str(exc),
                )
            )
    return results
```

- [ ] **Step 4: Run analysis tests and verify they pass**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_analyze.py tests\test_db.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/self_talk_coach/analyze.py tests/test_analyze.py
git commit -m "feat: analyze transcript segments"
```

---

## Task 4: Analysis CLI

**Files:**
- Modify: `src/self_talk_coach/cli.py`
- Modify: `tests/test_cli_media_library.py`

- [ ] **Step 1: Add failing CLI analysis test**

Append to `tests/test_cli_media_library.py`:

```python
from self_talk_coach.db import connect, init_db, insert_media_file, replace_transcript
from self_talk_coach.domain import DateConfidence, MediaStatus, TranscriptStatus


def test_cli_analyze_creates_pending_candidates(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    baseline_path = tmp_path / "baseline.txt"
    baseline_path.write_text("ich\nhabe\nbin\n", encoding="utf-8")
    media_path = data_root / "media" / "processed" / "2026" / "06" / "daily.mp4"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"video")

    init_result = runner.invoke(app, ["init", "--data-root", str(data_root)])
    assert init_result.exit_code == 0

    with connect(data_root / "db" / "self_talk_coach.sqlite") as conn:
        init_db(conn)
        media_id = insert_media_file(
            conn,
            original_filename="daily.mp4",
            original_path="data/media/inbox/daily.mp4",
            managed_path=str(media_path),
            content_hash="analysis-cli-hash",
            size_bytes=media_path.stat().st_size,
            duration_seconds=None,
            inferred_session_at="2026-06-02T08:00:00+00:00",
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
                {"start_seconds": 0.0, "end_seconds": 2.0, "text": "Ich habe gegangen."},
            ],
        )
        conn.commit()

    result = runner.invoke(
        app,
        [
            "analyze",
            "--data-root",
            str(data_root),
            "--baseline",
            str(baseline_path),
        ],
    )

    assert result.exit_code == 0
    assert "Analyzed: 1" in result.stdout
    assert "Failed: 0" in result.stdout
    with connect(data_root / "db" / "self_talk_coach.sqlite") as conn:
        count = conn.execute("SELECT COUNT(*) FROM learning_candidates").fetchone()[0]
    assert count == 2
```

- [ ] **Step 2: Run CLI test and verify it fails**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_cli_media_library.py::test_cli_analyze_creates_pending_candidates
```

Expected: FAIL because `analyze` command does not exist.

- [ ] **Step 3: Add `stc analyze` command**

Update imports in `src/self_talk_coach/cli.py`:

```python
from self_talk_coach.analyze import analyze_pending
from self_talk_coach.domain import AnalysisOutcome, ImportOutcome, TranscriptionOutcome
```

Add this command before `transcribe_command`:

```python
@app.command("analyze")
def analyze_command(
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
    baseline_path: Annotated[
        Path,
        typer.Option("--baseline", help="Known-word baseline file."),
    ] = Path("resources/baseline-de-b1.txt"),
) -> None:
    """Analyze stored transcript segments into pending learning candidates."""
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        results = analyze_pending(conn, paths, baseline_path=baseline_path)

    analyzed = sum(1 for result in results if result.outcome == AnalysisOutcome.ANALYZED)
    failed = sum(1 for result in results if result.outcome == AnalysisOutcome.FAILED)
    created = sum(result.candidates_created for result in results)

    typer.echo(f"Analyzed: {analyzed}")
    typer.echo(f"Candidates: {created}")
    typer.echo(f"Failed: {failed}")
```

- [ ] **Step 4: Run CLI tests and verify they pass**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest tests\test_cli_media_library.py tests\test_analyze.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/self_talk_coach/cli.py tests/test_cli_media_library.py
git commit -m "feat: add analysis cli"
```

---

## Task 5: Documentation And Milestone Tracking

**Files:**
- Modify: `README.md`
- Modify: `BACKLOG.md`
- Modify: `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`
- Modify: `docs/superpowers/plans/2026-06-02-first-language-analysis.md`

- [ ] **Step 1: Update README workflow**

In `README.md`, update the local workflow block:

```bash
# Lokale Mediathek initialisieren und eigene Videos importieren
stc init
# Put daily German self-talk videos into data/media/inbox/
stc import
stc transcribe
stc analyze
stc export transcripts --format json
stc export transcripts --format markdown
```

- [ ] **Step 2: Update BACKLOG**

Move this line from `Open - S2`:

```markdown
- first-language-analysis - Generate pending correction and upgrade candidates from stored transcript segments.
```

To `Done this session (2026-06-02)` as:

```markdown
- first-language-analysis - Planned and implemented deterministic pending candidate generation from stored transcript segments.
```

Leave `review-queue` open.

- [ ] **Step 3: Mark Milestone 3 planned in the design spec**

In `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`, under `### Milestone 3: First Language Analysis`, add:

```markdown
Implementation status: planned in `docs/superpowers/plans/2026-06-02-first-language-analysis.md`; completed when `stc analyze`, candidate repository tests, and analysis tests pass the full test suite.
```

- [ ] **Step 4: Run final verification**

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m pytest -q -p no:cacheprovider --basetemp=.test-tmp\pytest
```

Expected: all tests pass.

Run:

```bash
$env:PYTHONPATH='src;.venv\Lib\site-packages'; python -m ruff check src tests
```

Expected: all checks pass.

- [ ] **Step 5: Commit docs**

```bash
git add README.md BACKLOG.md docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md docs/superpowers/plans/2026-06-02-first-language-analysis.md
git commit -m "docs: document first language analysis workflow"
```

---

## Plan Self-Review

- Spec coverage:
  - Create vocabulary candidates: Task 2.
  - Create phrase upgrades: Task 2.
  - Create basic correction candidates: Task 2.
  - Link every candidate to a transcript segment: Tasks 1 and 3.
  - Store candidates as pending review items: Tasks 1 and 3.
  - Add `stc analyze`: Task 4.
  - Preserve review gate/no automatic practice generation: no task writes `practice_items`.
  - Local-first/no cloud dependency: Tasks 2 and 3 use deterministic rules and the local baseline file.
- Deferred from this plan:
  - Review queue list/show/approve/reject/defer begins in Milestone 4.
  - Practice item creation begins after review approval in Milestone 4.
  - Anki export remains Milestone 5.
  - LLM-backed corrections/upgrades are intentionally deferred until the local-first candidate pipeline is stable.
- Placeholder scan:
  - This plan contains no open-ended implementation steps.
  - Each code task includes failing tests, implementation code, verification commands, and commit commands.
- Type consistency:
  - `CandidateType`, `CandidateStatus`, and `AnalysisOutcome` are defined before use.
  - `CandidateDraft`, `AnalysisRunResult`, `analyze_segment_text`, and `analyze_pending` names are consistent across tests, implementation, and CLI.
