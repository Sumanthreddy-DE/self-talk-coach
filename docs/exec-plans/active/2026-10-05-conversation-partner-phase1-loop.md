# Conversation Partner — Phase 1 (Storage + Live Loop) Implementation Plan

**Status:** active
**Last verified:** 2026-10-05

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `stc talk` runs a real spoken German conversation in the terminal: the partner speaks (text hidden), the learner answers by toggle key, the help ladder fires on silence, listening aids work, and every turn is stored in SQLite with Opus audio.

**Architecture:** New package `src/self_talk_coach/conversation/` with one module per job (ladder, question bank, partner LLM, STT, TTS, audio store, hardware I/O, session orchestrator). Every external dependency sits behind a small interface and is injected into `ConversationSession`, so the whole loop is tested with fakes and a fake clock. Real hardware/API wiring lives only in `audio_io.py` and the `talk` CLI command.

**Tech Stack:** Python 3.12, SQLite (existing `db.py`), Deepgram Nova-3 via `requests`, OpenAI SDK against the gateway (DeepSeek V4 Pro → Claude Sonnet 5 fallback), `edge-tts` (Seraphina), `sounddevice` + `soundfile`, ffmpeg (libopus), Typer, pytest.

**Spec:** `docs/exec-plans/active/2026-10-04-conversation-partner-design.md` (stack per § Stack and § Spike results).

## Global Constraints

- Windows 11; keys via `msvcrt` in Windows PowerShell; run Python as `.venv/Scripts/python`.
- Deepgram requests always send `model=nova-3`, `language=de`, `punctuate=true`, `smart_format=false`, `mip_opt_out=true`.
- Partner model `deepseek-v4-pro`, fallback `claude-sonnet-5`, fallback trigger: error, unparseable JSON, or > 15 s. OpenAI client with `max_retries=0`.
- TTS voice `de-DE-SeraphinaMultilingualNeural`; "slower" = `rate="-25%"`.
- Help ladder defaults 4 / 8 / 12 s (`STC_LADDER_SECONDS=4,8,12`).
- Partner text is never printed unless the learner presses `t`. Helper phrases are never printed.
- Recast is a second-person echo ("Ah, du hast gestern gearbeitet?"), never a first-person repeat of the learner's sentence.
- A conversation has exactly two voices: learner + AI partner.
- Nothing under `data/` is committed. Learner profile lives at `data/learner-profile.md` (gitignored). Question banks are read in place via `STC_QUESTION_BANKS`.
- Each turn is written to the DB before the next step starts.
- Keep ≥2 Typer commands registered (STATE.md landmine).
- `bash scripts/lint-arch.sh` and full `pytest -q` before every commit. Max 800 lines per file.
- Phase 1 simplification: no `--scenario` = all bank sections (spec's free-talk subset of daily-life/office sections is Phase 2).
- Out of scope (Phase 2): session report, comprehension checks, `learning_candidates.turn_id`, Piper fallback, local-whisper STT fallback, cross-conversation seed memory / freeze boost, B1 out-of-baseline metric, interview-questionnaire model answers.

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Promote `sounddevice`, `soundfile`, `openai`, `edge-tts` to runtime deps |
| `src/self_talk_coach/domain.py` | + `ConversationStatus`, `TurnSpeaker` enums |
| `src/self_talk_coach/paths.py` | + `conversations_root`, `conversation_dir()`, `learner_profile_path` |
| `src/self_talk_coach/db.py` | Schema v2: `conversations`, `turns` tables + repo functions |
| `src/self_talk_coach/conversation/__init__.py` | Package marker |
| `src/self_talk_coach/conversation/help_ladder.py` | Pure ladder timing logic + nudge phrases |
| `src/self_talk_coach/conversation/question_bank.py` | Parse Markdown banks, scenario filter, no-repeat picker |
| `src/self_talk_coach/conversation/partner.py` | Prompt, `PartnerTurn` parsing, LLM client with fallback, history |
| `src/self_talk_coach/conversation/stt.py` | Deepgram learner transcription |
| `src/self_talk_coach/conversation/tts.py` | edge-tts voice → MP3 bytes |
| `src/self_talk_coach/conversation/audio_store.py` | WAV encoding, Opus files via ffmpeg |
| `src/self_talk_coach/conversation/audio_io.py` | Real keys, mic recorder, speaker playback, real clock (hardware only) |
| `src/self_talk_coach/conversation/session.py` | Orchestrates one conversation |
| `src/self_talk_coach/conversation/config.py` | Reads `.env` into `TalkConfig` |
| `src/self_talk_coach/cli.py` | + `stc talk` |
| `tests/conversation/…` | One test file per module + session integration test |

---

### Task 1: Schema v2 — conversations and turns

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Modify: `src/self_talk_coach/domain.py` (append)
- Modify: `src/self_talk_coach/paths.py`
- Modify: `src/self_talk_coach/db.py` (`SCHEMA_VERSION`, `init_db` script, new functions at end)
- Modify: `tests/test_db.py:54` (`user_version == 1` → `2`)
- Modify: `tests/test_paths.py`
- Create: `tests/conversation/__init__.py` (empty), `tests/conversation/test_conversation_db.py`

**Interfaces:**
- Produces:
  - `domain.ConversationStatus` (`ACTIVE="active"`, `COMPLETED="completed"`, `ABORTED="aborted"`), `domain.TurnSpeaker` (`LEARNER="learner"`, `PARTNER="partner"`)
  - `AppPaths.conversations_root -> Path` (`data_root/"conversations"`), `AppPaths.conversation_dir(conversation_id: int) -> Path`, `AppPaths.learner_profile_path -> Path` (`data_root/"learner-profile.md"`)
  - `db.insert_conversation(conn, *, started_at: str, scenario: str | None, stt_model: str, llm_model: str, tts_voice: str) -> int`
  - `db.finish_conversation(conn, conversation_id: int, *, ended_at: str, status: ConversationStatus) -> None`
  - `db.insert_turn(conn, *, conversation_id: int, turn_index: int, speaker: TurnSpeaker, text: str, audio_path: str | None = None, words_json: str | None = None, seed: str | None = None, partner_turn_json: str | None = None, llm_model: str | None = None, freeze_seconds: float | None = None) -> int`
  - `db.update_turn_listening(conn, turn_id: int, *, ladder_step_reached: int, replay_count: int, slower_count: int, show_text_count: int) -> None`
  - `db.list_turns(conn, conversation_id: int) -> list[sqlite3.Row]` (ordered by `turn_index`)
  - `db.get_conversation(conn, conversation_id: int) -> sqlite3.Row | None`

- [ ] **Step 1: Promote runtime deps**

In `pyproject.toml` `dependencies`, after `"pydantic>=2.6",` add:

```toml
    "sounddevice>=0.4.6",
    "soundfile>=0.12",
    "openai>=1.40",
    "edge-tts>=7.0",
```

Run: `.venv/Scripts/python -m pip install -q -e ".[dev,spike]"`
Expected: no errors.

- [ ] **Step 2: Write the failing tests**

`tests/conversation/__init__.py`: empty file.

`tests/conversation/test_conversation_db.py`:

```python
from pathlib import Path

from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_turns,
    update_turn_listening,
)
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.paths import AppPaths


def _conn(tmp_path: Path):
    conn = connect(tmp_path / "t.sqlite")
    init_db(conn)
    return conn


def test_conversation_lifecycle(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = insert_conversation(
        conn,
        started_at="2026-10-05T20:00:00+00:00",
        scenario=None,
        stt_model="deepgram:nova-3:de",
        llm_model="deepseek-v4-pro",
        tts_voice="de-DE-SeraphinaMultilingualNeural",
    )
    row = get_conversation(conn, cid)
    assert row["status"] == "active"
    assert row["report_status"] == "pending"

    finish_conversation(conn, cid, ended_at="2026-10-05T20:10:00+00:00", status=ConversationStatus.COMPLETED)
    row = get_conversation(conn, cid)
    assert row["status"] == "completed"
    assert row["ended_at"] == "2026-10-05T20:10:00+00:00"


def test_turns_insert_update_and_order(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = insert_conversation(
        conn, started_at="x", scenario="Interview: Core", stt_model="s", llm_model="l", tts_voice="v"
    )
    learner_id = insert_turn(
        conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
        text="Ich habe einen Frage.", audio_path="a.opus", words_json="[]", freeze_seconds=5.2,
    )
    partner_id = insert_turn(
        conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER,
        text="Was machst du?", seed="Arbeit", partner_turn_json="{}", llm_model="deepseek-v4-pro",
    )
    update_turn_listening(conn, partner_id, ladder_step_reached=2, replay_count=1, slower_count=0, show_text_count=3)

    turns = list_turns(conn, cid)
    assert [t["turn_index"] for t in turns] == [0, 1]
    assert turns[0]["id"] == partner_id
    assert turns[0]["ladder_step_reached"] == 2
    assert turns[0]["show_text_count"] == 3
    assert turns[1]["id"] == learner_id
    assert turns[1]["freeze_seconds"] == 5.2
    assert turns[1]["speaker"] == "learner"


def test_conversation_paths(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)
    assert paths.conversations_root == tmp_path / "conversations"
    assert paths.conversation_dir(7) == tmp_path / "conversations" / "0007"
    assert paths.learner_profile_path == tmp_path / "learner-profile.md"
    paths.ensure_workspace()
    assert paths.conversations_root.is_dir()
```

Also in `tests/test_db.py` change line 54 `assert user_version == 1` to `assert user_version == 2`, and add `"conversations", "turns",` to the expected table set in that test.

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_conversation_db.py tests/test_db.py -q`
Expected: FAIL — `ImportError: cannot import name 'finish_conversation'`.

- [ ] **Step 4: Implement**

Append to `src/self_talk_coach/domain.py`:

```python


class ConversationStatus(StrEnum):
    """Lifecycle state of one live conversation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TurnSpeaker(StrEnum):
    """Who produced a conversation turn."""

    LEARNER = "learner"
    PARTNER = "partner"
```

In `src/self_talk_coach/paths.py`, add before `ensure_workspace`:

```python
    @property
    def conversations_root(self) -> Path:
        return self.data_root / "conversations"

    def conversation_dir(self, conversation_id: int) -> Path:
        return self.conversations_root / f"{conversation_id:04d}"

    @property
    def learner_profile_path(self) -> Path:
        return self.data_root / "learner-profile.md"
```

and add `self.conversations_root,` to the tuple in `ensure_workspace`.

In `src/self_talk_coach/db.py`: set `SCHEMA_VERSION = 2`; change the import line to
`from self_talk_coach.domain import ConversationStatus, DateConfidence, MediaStatus, TranscriptStatus, TurnSpeaker`;
inside the `init_db` script, after the `review_events` table, add:

```sql
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            scenario TEXT,
            stt_model TEXT NOT NULL,
            llm_model TEXT NOT NULL,
            tts_voice TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'aborted')),
            report_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (report_status IN ('pending', 'done', 'failed'))
        );

        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            turn_index INTEGER NOT NULL,
            speaker TEXT NOT NULL CHECK (speaker IN ('learner', 'partner')),
            text TEXT NOT NULL,
            audio_path TEXT,
            words_json TEXT,
            seed TEXT,
            partner_turn_json TEXT,
            llm_model TEXT,
            freeze_seconds REAL,
            ladder_step_reached INTEGER NOT NULL DEFAULT 0,
            replay_count INTEGER NOT NULL DEFAULT 0,
            slower_count INTEGER NOT NULL DEFAULT 0,
            show_text_count INTEGER NOT NULL DEFAULT 0,
            comprehension_check INTEGER NOT NULL DEFAULT 0,
            out_of_baseline_ratio REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (conversation_id, turn_index)
        );
```

Append to the end of `db.py`:

```python


def insert_conversation(
    conn: sqlite3.Connection,
    *,
    started_at: str,
    scenario: str | None,
    stt_model: str,
    llm_model: str,
    tts_voice: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO conversations (started_at, scenario, stt_model, llm_model, tts_voice, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (started_at, scenario, stt_model, llm_model, tts_voice, ConversationStatus.ACTIVE.value),
    )
    conn.commit()
    return int(cursor.lastrowid)


def finish_conversation(
    conn: sqlite3.Connection, conversation_id: int, *, ended_at: str, status: ConversationStatus
) -> None:
    conn.execute(
        "UPDATE conversations SET ended_at = ?, status = ? WHERE id = ?",
        (ended_at, status.value, conversation_id),
    )
    conn.commit()


def get_conversation(conn: sqlite3.Connection, conversation_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()


def insert_turn(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
    turn_index: int,
    speaker: TurnSpeaker,
    text: str,
    audio_path: str | None = None,
    words_json: str | None = None,
    seed: str | None = None,
    partner_turn_json: str | None = None,
    llm_model: str | None = None,
    freeze_seconds: float | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO turns (
            conversation_id, turn_index, speaker, text, audio_path, words_json,
            seed, partner_turn_json, llm_model, freeze_seconds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id, turn_index, speaker.value, text, audio_path, words_json,
            seed, partner_turn_json, llm_model, freeze_seconds,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_turn_listening(
    conn: sqlite3.Connection,
    turn_id: int,
    *,
    ladder_step_reached: int,
    replay_count: int,
    slower_count: int,
    show_text_count: int,
) -> None:
    conn.execute(
        """
        UPDATE turns
        SET ladder_step_reached = ?, replay_count = ?, slower_count = ?, show_text_count = ?
        WHERE id = ?
        """,
        (ladder_step_reached, replay_count, slower_count, show_text_count, turn_id),
    )
    conn.commit()


def list_turns(conn: sqlite3.Connection, conversation_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM turns WHERE conversation_id = ? ORDER BY turn_index", (conversation_id,)
    ).fetchall()
```

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all pass (43 existing + 3 new = 46).

- [ ] **Step 6: Commit**

```bash
bash scripts/lint-arch.sh && git add pyproject.toml src/self_talk_coach/domain.py src/self_talk_coach/paths.py src/self_talk_coach/db.py tests/test_db.py tests/conversation/__init__.py tests/conversation/test_conversation_db.py && git commit -m "feat(conversation): schema v2 with conversations and turns"
```

---

### Task 2: Help ladder

**Files:**
- Create: `src/self_talk_coach/conversation/__init__.py` (docstring only: `"""Live conversation partner."""`)
- Create: `src/self_talk_coach/conversation/help_ladder.py`
- Test: `tests/conversation/test_help_ladder.py`

**Interfaces:**
- Produces:
  - `LadderStep(IntEnum)`: `NONE=0, NUDGE=1, STARTER=2, REPHRASE=3`
  - `LadderTimings(nudge: float = 4.0, starter: float = 8.0, rephrase: float = 12.0)`, frozen dataclass; `LadderTimings.from_csv(value: str) -> LadderTimings`
  - `step_for(elapsed: float, timings: LadderTimings) -> LadderStep`
  - `NUDGE_PHRASES: tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from self_talk_coach.conversation.help_ladder import (
    NUDGE_PHRASES,
    LadderStep,
    LadderTimings,
    step_for,
)


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (0.0, LadderStep.NONE),
        (3.99, LadderStep.NONE),
        (4.0, LadderStep.NUDGE),
        (7.9, LadderStep.NUDGE),
        (8.0, LadderStep.STARTER),
        (12.0, LadderStep.REPHRASE),
        (60.0, LadderStep.REPHRASE),
    ],
)
def test_step_for_default_timings(elapsed: float, expected: LadderStep) -> None:
    assert step_for(elapsed, LadderTimings()) == expected


def test_from_csv_parses_and_validates() -> None:
    assert LadderTimings.from_csv("3,6,9") == LadderTimings(3.0, 6.0, 9.0)
    with pytest.raises(ValueError):
        LadderTimings.from_csv("8,4,12")
    with pytest.raises(ValueError):
        LadderTimings.from_csv("4,8")


def test_nudges_are_neutral_and_present() -> None:
    assert NUDGE_PHRASES
    assert not any("super" in p.lower() or "toll" in p.lower() for p in NUDGE_PHRASES)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_help_ladder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'self_talk_coach.conversation'`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/__init__.py`:

```python
"""Live conversation partner."""
```

`src/self_talk_coach/conversation/help_ladder.py`:

```python
"""Help ladder: escalating help while the learner is silent after a partner question."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

NUDGE_PHRASES: tuple[str, ...] = (
    "Lass dir ruhig Zeit.",
    "Kein Stress, denk kurz nach.",
    "Ganz in Ruhe.",
)


class LadderStep(IntEnum):
    NONE = 0
    NUDGE = 1
    STARTER = 2
    REPHRASE = 3


@dataclass(frozen=True)
class LadderTimings:
    nudge: float = 4.0
    starter: float = 8.0
    rephrase: float = 12.0

    @classmethod
    def from_csv(cls, value: str) -> LadderTimings:
        parts = [float(p) for p in value.split(",")]
        if len(parts) != 3 or not (0 < parts[0] < parts[1] < parts[2]):
            raise ValueError(f"Ladder seconds must be three increasing numbers, got {value!r}")
        return cls(*parts)


def step_for(elapsed: float, timings: LadderTimings) -> LadderStep:
    if elapsed >= timings.rephrase:
        return LadderStep.REPHRASE
    if elapsed >= timings.starter:
        return LadderStep.STARTER
    if elapsed >= timings.nudge:
        return LadderStep.NUDGE
    return LadderStep.NONE
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_help_ladder.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/__init__.py src/self_talk_coach/conversation/help_ladder.py tests/conversation/test_help_ladder.py && git commit -m "feat(conversation): help ladder timing"
```

---

### Task 3: Question bank

**Files:**
- Create: `src/self_talk_coach/conversation/question_bank.py`
- Test: `tests/conversation/test_question_bank.py`

**Interfaces:**
- Produces:
  - `Seed(section: str, text: str)` frozen dataclass
  - `parse_bank(markdown: str) -> list[Seed]` — numbered items (`1. …`) under `## ` headings; items before any `##` are ignored
  - `load_banks(paths: Sequence[Path]) -> list[Seed]` — raises `FileNotFoundError` naming the missing path
  - `filter_scenario(seeds: Sequence[Seed], scenario: str | None) -> list[Seed]` — `None` → all; else case-insensitive substring match on `section`; no match → `ValueError` listing available sections
  - `SeedPicker(seeds: Sequence[Seed], rng: random.Random)` with `.next() -> Seed` — no repeat until all used, then reshuffles

- [ ] **Step 1: Write the failing test**

```python
import random
from pathlib import Path

import pytest

from self_talk_coach.conversation.question_bank import (
    Seed,
    SeedPicker,
    filter_scenario,
    load_banks,
    parse_bank,
)

BANK = """# German Question Bank

1. ignored, no section yet

## Interview: Core

1. Erzählen Sie mir bitte etwas über sich.
2. Was sind Ihre Stärken?

## Daily Life In Germany

1. Wie kommst du zur Arbeit?
10. Was kochst du gern?
- not numbered, ignored
"""


def test_parse_bank_reads_numbered_items_per_section() -> None:
    seeds = parse_bank(BANK)
    assert seeds == [
        Seed("Interview: Core", "Erzählen Sie mir bitte etwas über sich."),
        Seed("Interview: Core", "Was sind Ihre Stärken?"),
        Seed("Daily Life In Germany", "Wie kommst du zur Arbeit?"),
        Seed("Daily Life In Germany", "Was kochst du gern?"),
    ]


def test_load_banks_reads_files_and_names_missing(tmp_path: Path) -> None:
    bank = tmp_path / "bank.md"
    bank.write_text(BANK, encoding="utf-8")
    assert len(load_banks([bank])) == 4
    with pytest.raises(FileNotFoundError, match="nope.md"):
        load_banks([tmp_path / "nope.md"])


def test_filter_scenario() -> None:
    seeds = parse_bank(BANK)
    assert filter_scenario(seeds, None) == seeds
    assert [s.text for s in filter_scenario(seeds, "interview")] == [
        "Erzählen Sie mir bitte etwas über sich.",
        "Was sind Ihre Stärken?",
    ]
    with pytest.raises(ValueError, match="Daily Life In Germany"):
        filter_scenario(seeds, "Behörde")


def test_picker_never_repeats_until_exhausted() -> None:
    seeds = parse_bank(BANK)
    picker = SeedPicker(seeds, random.Random(1))
    first_round = [picker.next() for _ in range(4)]
    assert sorted(s.text for s in first_round) == sorted(s.text for s in seeds)
    assert picker.next() in seeds
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_question_bank.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/question_bank.py`:

```python
"""Question banks: Markdown files of numbered questions grouped under '## ' sections."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_ITEM = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")


@dataclass(frozen=True)
class Seed:
    section: str
    text: str


def parse_bank(markdown: str) -> list[Seed]:
    seeds: list[Seed] = []
    section: str | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section is None:
            continue
        match = _ITEM.match(line)
        if match:
            seeds.append(Seed(section, match.group(1)))
    return seeds


def load_banks(paths: Sequence[Path]) -> list[Seed]:
    seeds: list[Seed] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Question bank not found: {path}")
        seeds.extend(parse_bank(path.read_text(encoding="utf-8")))
    return seeds


def filter_scenario(seeds: Sequence[Seed], scenario: str | None) -> list[Seed]:
    if scenario is None:
        return list(seeds)
    wanted = scenario.lower()
    chosen = [s for s in seeds if wanted in s.section.lower()]
    if not chosen:
        sections = sorted({s.section for s in seeds})
        raise ValueError(f"No section matches {scenario!r}. Available: {', '.join(sections)}")
    return chosen


class SeedPicker:
    def __init__(self, seeds: Sequence[Seed], rng: random.Random) -> None:
        if not seeds:
            raise ValueError("SeedPicker needs at least one seed")
        self._seeds = list(seeds)
        self._rng = rng
        self._queue: list[Seed] = []

    def next(self) -> Seed:
        if not self._queue:
            self._queue = self._seeds[:]
            self._rng.shuffle(self._queue)
        return self._queue.pop()
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_question_bank.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/question_bank.py tests/conversation/test_question_bank.py && git commit -m "feat(conversation): question bank parser and picker"
```

---

### Task 4: Partner LLM with fallback

**Files:**
- Create: `src/self_talk_coach/conversation/partner.py`
- Test: `tests/conversation/test_partner.py`

**Interfaces:**
- Produces:
  - `PartnerTurn` (pydantic): `reply: str`, `recast: str | None`, `starter_phrase: str`, `simpler_rephrase: str`, `topic_jump: bool`; method `spoken_text() -> str` (recast + " " + reply, stripped)
  - `build_system_prompt(profile: str | None) -> str`
  - `parse_partner_turn(raw: str) -> PartnerTurn` — strips code fences, takes the outermost `{…}`; raises `PartnerFormatError`
  - `ChatClient` protocol: `complete(model: str, messages: list[dict[str, str]], timeout: float) -> str`
  - `OpenAIChatClient(base_url: str, api_key: str)` implementing `ChatClient`
  - `PartnerReply(turn: PartnerTurn, model: str, raw: str)` frozen dataclass
  - `PartnerUnavailable(Exception)`, `PartnerFormatError(ValueError)`
  - `Partner(client: ChatClient, primary: str, fallback: str, system_prompt: str, timeout: float = 15.0, max_history: int = 12)` with `opening(seed: str) -> PartnerReply` and `respond(learner_text: str, seed: str) -> PartnerReply`
  - `fallback_reply(seed: str) -> PartnerReply` — used when both models fail (model = `"none"`)

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest

from self_talk_coach.conversation.partner import (
    Partner,
    PartnerFormatError,
    PartnerUnavailable,
    build_system_prompt,
    fallback_reply,
    parse_partner_turn,
)

GOOD = {
    "reply": "Wann schläfst du dann?",
    "recast": "Ah, du hast gestern bis Mitternacht gearbeitet?",
    "starter_phrase": "Normalerweise gehe ich um …",
    "simpler_rephrase": "Wann gehst du schlafen?",
    "topic_jump": False,
}


class FakeClient:
    def __init__(self, script: dict[str, list]) -> None:
        self.script = script
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, model, messages, timeout):
        self.calls.append((model, [dict(m) for m in messages]))
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_parse_handles_fences_and_prose() -> None:
    raw = "Hier:\n```json\n" + json.dumps(GOOD) + "\n```"
    turn = parse_partner_turn(raw)
    assert turn.reply == GOOD["reply"]
    assert turn.spoken_text() == GOOD["recast"] + " " + GOOD["reply"]


def test_parse_rejects_garbage() -> None:
    with pytest.raises(PartnerFormatError):
        parse_partner_turn("Biryani ist lecker – gute Wahl.")


def test_spoken_text_without_recast() -> None:
    turn = parse_partner_turn(json.dumps({**GOOD, "recast": None}))
    assert turn.spoken_text() == GOOD["reply"]


def test_system_prompt_rules_and_profile() -> None:
    prompt = build_system_prompt("Wohnort: Reutlingen")
    assert "Wohnort: Reutlingen" in prompt
    assert "du hast" in prompt          # second-person recast example
    assert "Kein Lob" in prompt
    assert build_system_prompt(None)


def test_primary_success_records_history() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD), json.dumps(GOOD)]})
    partner = Partner(client, "primary", "fallback", "SYS")
    first = partner.opening("Arbeit")
    assert first.model == "primary"
    partner.respond("Ich habe gestern gearbeitet.", "Schlaf")
    _, messages = client.calls[-1]
    assert messages[0] == {"role": "system", "content": "SYS"}
    assert messages[-1]["role"] == "user"
    assert "Ich habe gestern gearbeitet." in messages[-1]["content"]
    assert "Schlaf" in messages[-1]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]


def test_falls_back_on_error_and_on_bad_json() -> None:
    client = FakeClient({
        "primary": [TimeoutError("slow"), "kein json"],
        "fallback": [json.dumps(GOOD), json.dumps(GOOD)],
    })
    partner = Partner(client, "primary", "fallback", "SYS")
    assert partner.opening("Arbeit").model == "fallback"
    assert partner.respond("Hallo", "Essen").model == "fallback"


def test_both_fail_raises_unavailable_and_history_stays_clean() -> None:
    client = FakeClient({"primary": [RuntimeError("x")], "fallback": [RuntimeError("y")]})
    partner = Partner(client, "primary", "fallback", "SYS")
    with pytest.raises(PartnerUnavailable):
        partner.opening("Arbeit")
    assert partner.history == []


def test_history_is_capped() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD)] * 10})
    partner = Partner(client, "primary", "fallback", "SYS", max_history=4)
    for i in range(10):
        partner.respond(f"Satz {i}", "Thema")
    assert len(partner.history) == 4
    assert "Satz 9" in partner.history[-2]["content"]


def test_fallback_reply_uses_seed() -> None:
    reply = fallback_reply("Was kochst du gern?")
    assert reply.turn.reply == "Was kochst du gern?"
    assert reply.model == "none"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_partner.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/partner.py`:

```python
"""Conversation partner: prompt, structured reply parsing, primary/fallback LLM calls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

_SYSTEM_TEMPLATE = """Du bist ein Gesprächspartner aus Baden-Württemberg. Du sprichst mit einem Deutschlerner (Niveau B1).
Regeln:
- Kurze Antworten: 1–2 Sätze. Umgangssprachlich, natürlich, Sprachniveau B1.
- Kein Lob, keine Floskeln wie "Super!", "Toll gemacht!" oder "Gute Wahl".
- "recast": Wenn der Lerner einen Fehler gemacht hat, greif seine Aussage korrigiert in der Du-Form auf, wie ein Muttersprachler nachfragt.
  Beispiel: Lerner "Gestern ich habe bis Mitternacht gearbeitet." → recast "Ah, du hast gestern bis Mitternacht gearbeitet?"
  Keine Erklärung. Kein Fehler → null. "reply" wiederholt den recast nicht.
- "reply": danach eine Frage zum vorgegebenen Thema, als natürliche Folgefrage oder als plötzlicher Themenwechsel.
- "starter_phrase": ein Satzanfang, mit dem der Lerner antworten könnte.
- "simpler_rephrase": dieselbe Frage einfacher formuliert.
- "topic_jump": true, wenn du das Thema plötzlich gewechselt hast.
Antworte NUR mit JSON: {{"reply": str, "recast": str|null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": bool}}
{profile_block}"""

_FENCE = re.compile(r"`{3}(?:json)?")
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class PartnerFormatError(ValueError):
    """The model's output could not be parsed into a PartnerTurn."""


class PartnerUnavailable(Exception):
    """Both primary and fallback models failed for one turn."""


class PartnerTurn(BaseModel):
    reply: str
    recast: str | None
    starter_phrase: str
    simpler_rephrase: str
    topic_jump: bool

    def spoken_text(self) -> str:
        return f"{self.recast or ''} {self.reply}".strip()


@dataclass(frozen=True)
class PartnerReply:
    turn: PartnerTurn
    model: str
    raw: str


class ChatClient(Protocol):
    def complete(self, model: str, messages: list[dict[str, str]], timeout: float) -> str: ...


class OpenAIChatClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def complete(self, model: str, messages: list[dict[str, str]], timeout: float) -> str:
        resp = self._client.chat.completions.create(
            model=model, messages=messages, temperature=0.8, max_tokens=400, timeout=timeout
        )
        if not getattr(resp, "choices", None):
            raise PartnerFormatError(f"{model}: response without choices")
        return resp.choices[0].message.content or ""


def build_system_prompt(profile: str | None) -> str:
    block = f"\nÜber den Lerner:\n{profile.strip()}" if profile and profile.strip() else ""
    return _SYSTEM_TEMPLATE.format(profile_block=block)


def parse_partner_turn(raw: str) -> PartnerTurn:
    match = _OBJECT.search(_FENCE.sub("", raw))
    if not match:
        raise PartnerFormatError(f"No JSON object in: {raw[:80]!r}")
    try:
        return PartnerTurn.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise PartnerFormatError(str(exc)) from exc


def fallback_reply(seed: str) -> PartnerReply:
    turn = PartnerTurn(reply=seed, recast=None, starter_phrase="", simpler_rephrase=seed, topic_jump=True)
    return PartnerReply(turn=turn, model="none", raw="")


class Partner:
    def __init__(
        self,
        client: ChatClient,
        primary: str,
        fallback: str,
        system_prompt: str,
        timeout: float = 15.0,
        max_history: int = 12,
    ) -> None:
        self._client = client
        self._models = (primary, fallback)
        self._system = {"role": "system", "content": system_prompt}
        self._timeout = timeout
        self._max_history = max_history
        self.history: list[dict[str, str]] = []

    def opening(self, seed: str) -> PartnerReply:
        return self._turn(f"Beginne das Gespräch mit einer kurzen Begrüßung und einer Frage. Thema: {seed}")

    def respond(self, learner_text: str, seed: str) -> PartnerReply:
        return self._turn(f"Lerner: {learner_text}\nNächstes Thema: {seed}")

    def _turn(self, user_content: str) -> PartnerReply:
        user = {"role": "user", "content": user_content}
        messages = [self._system, *self.history, user]
        errors: list[str] = []
        for model in self._models:
            try:
                raw = self._client.complete(model, messages, self._timeout)
                turn = parse_partner_turn(raw)
            except Exception as exc:  # noqa: BLE001 — any failure moves to the next model
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                continue
            self.history.extend([user, {"role": "assistant", "content": raw}])
            self.history = self.history[-self._max_history:]
            return PartnerReply(turn=turn, model=model, raw=raw)
        raise PartnerUnavailable("; ".join(errors))
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_partner.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/partner.py tests/conversation/test_partner.py && git commit -m "feat(conversation): partner LLM with fallback and second-person recast"
```

---

### Task 5: Deepgram STT

**Files:**
- Create: `src/self_talk_coach/conversation/stt.py`
- Test: `tests/conversation/test_stt.py`

**Interfaces:**
- Produces:
  - `Word(word: str, start: float, end: float, confidence: float)` frozen dataclass
  - `LearnerTranscript(text: str, words: tuple[Word, ...], model: str)` frozen dataclass with `words_json() -> str`
  - `LearnerTranscriber` protocol: attribute `model_name: str`; `transcribe(wav_bytes: bytes) -> LearnerTranscript`
  - `DeepgramTranscriber(api_key: str, post: Callable[..., Any] = requests.post, timeout: float = 30.0)`; `model_name == "deepgram:nova-3:de"`
  - `DEEPGRAM_PARAMS: dict[str, str]`

- [ ] **Step 1: Write the failing test**

```python
import json

from self_talk_coach.conversation.stt import DEEPGRAM_PARAMS, DeepgramTranscriber

RESPONSE = {
    "results": {"channels": [{"alternatives": [{
        "transcript": "Ich habe einen Frage.",
        "words": [
            {"word": "ich", "punctuated_word": "Ich", "start": 0.1, "end": 0.3, "confidence": 0.99},
            {"word": "habe", "start": 0.3, "end": 0.5, "confidence": 0.98},
            {"word": "einen", "start": 0.5, "end": 0.8, "confidence": 0.91},
            {"word": "frage", "punctuated_word": "Frage.", "start": 0.8, "end": 1.2, "confidence": 0.97},
        ],
    }]}]}
}


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return RESPONSE


def test_deepgram_request_and_parse() -> None:
    seen = {}

    def fake_post(url, params, headers, data, timeout):
        seen.update(url=url, params=params, headers=headers, data=data, timeout=timeout)
        return FakeResponse()

    stt = DeepgramTranscriber("KEY", post=fake_post)
    result = stt.transcribe(b"RIFFfake")

    assert seen["url"] == "https://api.deepgram.com/v1/listen"
    assert seen["params"] == DEEPGRAM_PARAMS
    assert DEEPGRAM_PARAMS["mip_opt_out"] == "true"
    assert DEEPGRAM_PARAMS["smart_format"] == "false"
    assert seen["headers"]["Authorization"] == "Token KEY"
    assert seen["data"] == b"RIFFfake"
    assert result.text == "Ich habe einen Frage."
    assert [w.word for w in result.words] == ["Ich", "habe", "einen", "Frage."]
    assert result.model == "deepgram:nova-3:de"
    assert json.loads(result.words_json())[2] == {"word": "einen", "start": 0.5, "end": 0.8, "confidence": 0.91}
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_stt.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/stt.py`:

```python
"""Learner speech-to-text via Deepgram Nova-3 (ADR 0005). Keeps learner errors verbatim."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import requests

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PARAMS: dict[str, str] = {
    "model": "nova-3",
    "language": "de",
    "punctuate": "true",
    "smart_format": "false",
    "mip_opt_out": "true",
}


@dataclass(frozen=True)
class Word:
    word: str
    start: float
    end: float
    confidence: float


@dataclass(frozen=True)
class LearnerTranscript:
    text: str
    words: tuple[Word, ...]
    model: str

    def words_json(self) -> str:
        return json.dumps([asdict(w) for w in self.words], ensure_ascii=False)


class LearnerTranscriber(Protocol):
    model_name: str

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript: ...


class DeepgramTranscriber:
    model_name = "deepgram:nova-3:de"

    def __init__(self, api_key: str, post: Callable[..., Any] = requests.post, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._post = post
        self._timeout = timeout

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript:
        resp = self._post(
            DEEPGRAM_URL,
            params=DEEPGRAM_PARAMS,
            headers={"Authorization": f"Token {self._api_key}", "Content-Type": "audio/wav"},
            data=wav_bytes,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        alt = resp.json()["results"]["channels"][0]["alternatives"][0]
        words = tuple(
            Word(
                word=w.get("punctuated_word") or w["word"],
                start=float(w["start"]),
                end=float(w["end"]),
                confidence=float(w["confidence"]),
            )
            for w in alt.get("words", [])
        )
        return LearnerTranscript(text=alt.get("transcript", ""), words=words, model=self.model_name)
```

Note: `words_json()` stores `punctuated_word` when present; the test's third word has none, so `"einen"`.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_stt.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/stt.py tests/conversation/test_stt.py && git commit -m "feat(conversation): Deepgram learner transcription with MIP opt-out"
```

---

### Task 6: TTS voice and audio store

**Files:**
- Create: `src/self_talk_coach/conversation/tts.py`
- Create: `src/self_talk_coach/conversation/audio_store.py`
- Test: `tests/conversation/test_tts.py`, `tests/conversation/test_audio_store.py`

**Interfaces:**
- Produces:
  - `Voice` protocol: attribute `name: str`; `synthesize(text: str, slower: bool = False) -> bytes` (MP3)
  - `EdgeVoice(voice_name: str, slower_rate: str = "-25%", communicate: Callable[..., Any] = edge_tts.Communicate)`
  - `SAMPLE_RATE = 16000`
  - `wav_bytes(samples: numpy.ndarray, samplerate: int = SAMPLE_RATE) -> bytes`
  - `encode_opus(audio: bytes, dest: Path, run: Callable[..., Any] = subprocess.run) -> None` — raises `RuntimeError` on ffmpeg failure

- [ ] **Step 1: Write the failing tests**

`tests/conversation/test_tts.py`:

```python
from self_talk_coach.conversation.tts import EdgeVoice


class FakeCommunicate:
    calls: list[tuple[str, str, str]] = []

    def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
        FakeCommunicate.calls.append((text, voice, rate))

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"ID3a"}
        yield {"type": "audio", "data": b"bc"}


def test_edge_voice_collects_audio_and_sets_rate() -> None:
    FakeCommunicate.calls.clear()
    voice = EdgeVoice("de-DE-SeraphinaMultilingualNeural", communicate=FakeCommunicate)
    assert voice.synthesize("Hallo") == b"ID3abc"
    assert voice.synthesize("Hallo", slower=True) == b"ID3abc"
    assert FakeCommunicate.calls == [
        ("Hallo", "de-DE-SeraphinaMultilingualNeural", "+0%"),
        ("Hallo", "de-DE-SeraphinaMultilingualNeural", "-25%"),
    ]
    assert voice.name == "de-DE-SeraphinaMultilingualNeural"
```

`tests/conversation/test_audio_store.py`:

```python
import io
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from self_talk_coach.conversation.audio_store import encode_opus, wav_bytes


def test_wav_bytes_roundtrip() -> None:
    samples = np.zeros(1600, dtype="float32")
    data = wav_bytes(samples)
    decoded, sr = sf.read(io.BytesIO(data))
    assert data[:4] == b"RIFF"
    assert sr == 16000
    assert len(decoded) == 1600


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_encode_opus_writes_file(tmp_path: Path) -> None:
    tone = (0.1 * np.sin(np.linspace(0, 2000, 16000))).astype("float32")
    dest = tmp_path / "sub" / "turn-001.opus"
    encode_opus(wav_bytes(tone), dest)
    assert dest.is_file()
    assert dest.stat().st_size > 100


def test_encode_opus_raises_on_failure(tmp_path: Path) -> None:
    class Failed:
        returncode = 1
        stderr = b"boom"

    with pytest.raises(RuntimeError, match="boom"):
        encode_opus(b"x", tmp_path / "a.opus", run=lambda *a, **k: Failed())
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_tts.py tests/conversation/test_audio_store.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/tts.py`:

```python
"""Partner voice via edge-tts (Microsoft neural voices, unofficial endpoint). Returns MP3 bytes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

import edge_tts


class Voice(Protocol):
    name: str

    def synthesize(self, text: str, slower: bool = False) -> bytes: ...


class EdgeVoice:
    def __init__(
        self,
        voice_name: str,
        slower_rate: str = "-25%",
        communicate: Callable[..., Any] = edge_tts.Communicate,
    ) -> None:
        self.name = voice_name
        self._slower_rate = slower_rate
        self._communicate = communicate

    def synthesize(self, text: str, slower: bool = False) -> bytes:
        rate = self._slower_rate if slower else "+0%"
        return asyncio.run(self._collect(text, rate))

    async def _collect(self, text: str, rate: str) -> bytes:
        chunks: list[bytes] = []
        async for chunk in self._communicate(text, self.name, rate=rate).stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
```

`src/self_talk_coach/conversation/audio_store.py`:

```python
"""Audio encoding helpers: in-memory WAV for STT, Opus files for storage."""

from __future__ import annotations

import io
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def wav_bytes(samples: np.ndarray, samplerate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples, samplerate, format="WAV")
    return buffer.getvalue()


def encode_opus(audio: bytes, dest: Path, run: Callable[..., Any] = subprocess.run) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", str(dest)],
        input=audio,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg opus encoding failed: {result.stderr.decode(errors='replace')}")
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_tts.py tests/conversation/test_audio_store.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/tts.py src/self_talk_coach/conversation/audio_store.py tests/conversation/test_tts.py tests/conversation/test_audio_store.py && git commit -m "feat(conversation): edge-tts voice and opus audio store"
```

---

### Task 7: Session orchestrator

**Files:**
- Create: `src/self_talk_coach/conversation/session.py`
- Test: `tests/conversation/test_session.py`

**Interfaces:**
- Consumes: `LadderTimings`, `LadderStep`, `step_for`, `NUDGE_PHRASES` (Task 2); `SeedPicker`, `Seed` (Task 3); `Partner`-like object with `opening(seed: str) -> PartnerReply`, `respond(learner_text: str, seed: str) -> PartnerReply`, `PartnerUnavailable`, `fallback_reply` (Task 4); `LearnerTranscriber` (Task 5); `Voice`, `wav_bytes`, `encode_opus` (Task 6); db functions + enums (Task 1); `AppPaths.conversation_dir` (Task 1).
- Produces:
  - Protocols `Clock` (`now() -> float`, `sleep(seconds: float) -> None`), `KeyInput` (`poll() -> str | None`), `Recorder` (`start() -> None`, `stop() -> numpy.ndarray`), `Player` (`play(audio: bytes) -> None`)
  - `SessionDeps` dataclass: `partner, transcriber, voice, player, recorder, keys, clock, picker, conn, paths, ladder: LadderTimings, rng: random.Random, store_audio: Callable[[bytes, Path], None] = encode_opus, out: Callable[[str], None] = print, now_iso: Callable[[], str]`
  - `ConversationSession(deps: SessionDeps, scenario: str | None, llm_label: str)` with `run() -> int` (conversation id)
  - Keys: SPACE start/stop speaking, `r` replay, `s` slower, `t` show partner text, `q` quit (only while waiting to speak)
  - `PARDON = "Wie bitte? Kannst du das nochmal sagen?"`; `MIN_SPEECH_SECONDS = 0.4`

- [ ] **Step 1: Write the failing test**

`tests/conversation/test_session.py`:

```python
import json
import random
from pathlib import Path

import numpy as np

from self_talk_coach.conversation.help_ladder import NUDGE_PHRASES, LadderTimings
from self_talk_coach.conversation.partner import PartnerReply, PartnerTurn, PartnerUnavailable
from self_talk_coach.conversation.question_bank import Seed, SeedPicker
from self_talk_coach.conversation.session import PARDON, ConversationSession, SessionDeps
from self_talk_coach.conversation.stt import LearnerTranscript
from self_talk_coach.db import connect, get_conversation, init_db, list_turns
from self_talk_coach.paths import AppPaths


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t = round(self.t + seconds, 6)


class FakeKeys:
    """Returns each scripted key once the fake clock reaches its time."""

    def __init__(self, clock: FakeClock, script: list[tuple[float, str]]) -> None:
        self.clock = clock
        self.script = list(script)

    def poll(self):
        if self.script and self.clock.now() >= self.script[0][0]:
            return self.script.pop(0)[1]
        return None


class FakeRecorder:
    def __init__(self, seconds: list[float]) -> None:
        self.seconds = list(seconds)

    def start(self) -> None:
        pass

    def stop(self):
        return np.zeros(int(16000 * self.seconds.pop(0)), dtype="float32")


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    def play(self, audio: bytes) -> None:
        self.played.append(audio)


class FakeVoice:
    name = "fake-voice"

    def synthesize(self, text: str, slower: bool = False) -> bytes:
        return f"{'SLOW:' if slower else ''}{text}".encode()


class FakeTranscriber:
    model_name = "fake-stt"

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript:
        return LearnerTranscript(text=self.texts.pop(0), words=(), model=self.model_name)


def _reply(reply: str, recast: str | None = None) -> PartnerReply:
    turn = PartnerTurn(reply=reply, recast=recast, starter_phrase=f"START {reply}",
                       simpler_rephrase=f"SIMPLE {reply}", topic_jump=False)
    return PartnerReply(turn=turn, model="deepseek-v4-pro", raw=turn.model_dump_json())


class FakePartner:
    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.learner_texts: list[str] = []

    def opening(self, seed: str) -> PartnerReply:
        return self._next()

    def respond(self, learner_text: str, seed: str) -> PartnerReply:
        self.learner_texts.append(learner_text)
        return self._next()

    def _next(self) -> PartnerReply:
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _deps(tmp_path: Path, keys_script, recordings, texts, replies):
    clock = FakeClock()
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    stored: list[Path] = []
    out: list[str] = []
    player = FakePlayer()
    deps = SessionDeps(
        partner=FakePartner(replies),
        transcriber=FakeTranscriber(texts),
        voice=FakeVoice(),
        player=player,
        recorder=FakeRecorder(recordings),
        keys=FakeKeys(clock, keys_script),
        clock=clock,
        picker=SeedPicker([Seed("S", "Arbeit"), Seed("S", "Essen"), Seed("S", "Wohnung")], random.Random(0)),
        conn=conn,
        paths=AppPaths.from_data_root(tmp_path),
        ladder=LadderTimings(),
        rng=random.Random(0),
        store_audio=lambda audio, dest: stored.append(dest),
        out=out.append,
        now_iso=lambda: "2026-10-05T20:00:00+00:00",
    )
    return deps, conn, player, stored, out


def test_full_exchange_with_ladder_aids_and_quit(tmp_path: Path) -> None:
    deps, conn, player, stored, out = _deps(
        tmp_path,
        keys_script=[(1.0, "r"), (2.0, "t"), (3.0, "s"), (5.0, " "), (7.0, " "), (9.0, "q")],
        recordings=[2.0],
        texts=["Gestern ich habe gearbeitet."],
        replies=[_reply("Was machst du beruflich?"),
                 _reply("Bis wann?", recast="Ah, du hast gestern gearbeitet?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="deepseek-v4-pro").run()

    turns = list_turns(conn, cid)
    assert [t["speaker"] for t in turns] == ["partner", "learner", "partner"]
    first, learner, second = turns
    assert first["text"] == "Was machst du beruflich?"
    assert first["replay_count"] == 1 and first["show_text_count"] == 1 and first["slower_count"] == 1
    assert first["ladder_step_reached"] == 1                     # nudge at 4 s, spoke at 5 s
    assert learner["freeze_seconds"] == 5.0
    assert learner["text"] == "Gestern ich habe gearbeitet."
    assert second["text"] == "Ah, du hast gestern gearbeitet? Bis wann?"
    assert second["seed"] is not None
    assert json.loads(second["partner_turn_json"])["recast"] == "Ah, du hast gestern gearbeitet?"
    assert get_conversation(conn, cid)["status"] == "completed"
    assert deps.partner.learner_texts == ["Gestern ich habe gearbeitet."]

    assert b"SLOW:Was machst du beruflich?" in player.played
    assert any(p.decode() in NUDGE_PHRASES for p in player.played)
    # partner text only on 't', helpers never printed; learner sees own transcript to spot mishearing
    assert out == ["Partner: Was machst du beruflich?", "(du) Gestern ich habe gearbeitet."]
    assert len(stored) == 3
    assert all(str(p).endswith(".opus") for p in stored)


def test_ladder_reaches_rephrase_and_speaks_helpers(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _deps(
        tmp_path, keys_script=[(13.0, "q")], recordings=[], texts=[],
        replies=[_reply("Was kochst du gern?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert list_turns(conn, cid)[0]["ladder_step_reached"] == 3
    assert b"START Was kochst du gern?" in player.played
    assert b"SIMPLE Was kochst du gern?" in player.played


def test_too_short_recording_gets_pardon_and_no_llm_call(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (1.1, " "), (2.0, " "), (4.0, " "), (6.0, "q")],
        recordings=[0.1, 2.0],
        texts=["Ich koche gern Biryani."],
        replies=[_reply("Was kochst du gern?"), _reply("Mit Hähnchen?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert PARDON.encode() in player.played
    assert deps.partner.learner_texts == ["Ich koche gern Biryani."]
    assert [t["speaker"] for t in list_turns(conn, cid)] == ["partner", "learner", "partner"]


def test_partner_unavailable_falls_back_to_seed_question(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (3.0, " "), (5.0, "q")],
        recordings=[2.0],
        texts=["Ich wohne in Reutlingen."],
        replies=[_reply("Wo wohnst du?"), PartnerUnavailable("both down")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    last = list_turns(conn, cid)[-1]
    assert last["speaker"] == "partner"
    assert last["llm_model"] == "none"
    assert last["seed"] == last["text"]


def test_keyboard_interrupt_marks_aborted(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(tmp_path, keys_script=[], recordings=[], texts=[],
                                replies=[_reply("Hallo?")])

    def boom() -> None:
        raise KeyboardInterrupt

    deps.keys.poll = boom
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert get_conversation(conn, cid)["status"] == "aborted"
    assert len(list_turns(conn, cid)) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_session.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'self_talk_coach.conversation.session'`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/session.py`:

```python
"""One live conversation: partner speaks, learner answers, help ladder and listening aids, per-turn storage."""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from self_talk_coach.conversation.audio_store import SAMPLE_RATE, encode_opus, wav_bytes
from self_talk_coach.conversation.help_ladder import NUDGE_PHRASES, LadderStep, LadderTimings, step_for
from self_talk_coach.conversation.partner import PartnerReply, PartnerUnavailable, fallback_reply
from self_talk_coach.conversation.question_bank import SeedPicker
from self_talk_coach.conversation.stt import LearnerTranscriber, LearnerTranscript
from self_talk_coach.conversation.tts import Voice
from self_talk_coach.db import finish_conversation, insert_conversation, insert_turn, update_turn_listening
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.paths import AppPaths

PARDON = "Wie bitte? Kannst du das nochmal sagen?"
MIN_SPEECH_SECONDS = 0.4
POLL_SECONDS = 0.05


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class KeyInput(Protocol):
    def poll(self) -> str | None: ...


class Recorder(Protocol):
    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...


class Player(Protocol):
    def play(self, audio: bytes) -> None: ...


@dataclass
class SessionDeps:
    partner: Any
    transcriber: LearnerTranscriber
    voice: Voice
    player: Player
    recorder: Recorder
    keys: KeyInput
    clock: Clock
    picker: SeedPicker
    conn: sqlite3.Connection
    paths: AppPaths
    ladder: LadderTimings
    rng: random.Random
    now_iso: Callable[[], str]
    store_audio: Callable[[bytes, Path], None] = encode_opus
    out: Callable[[str], None] = print


@dataclass
class _Window:
    quit: bool = False
    freeze_seconds: float | None = None
    ladder_step: int = 0
    replay: int = 0
    slower: int = 0
    show_text: int = 0


@dataclass
class _State:
    conversation_id: int = 0
    turn_index: int = 0
    seed_text: str = ""
    reply: PartnerReply | None = None
    audio: bytes = b""


class ConversationSession:
    def __init__(self, deps: SessionDeps, scenario: str | None, llm_label: str) -> None:
        self._d = deps
        self._scenario = scenario
        self._llm_label = llm_label
        self._s = _State()

    def run(self) -> int:
        d = self._d
        self._s.conversation_id = insert_conversation(
            d.conn,
            started_at=d.now_iso(),
            scenario=self._scenario,
            stt_model=d.transcriber.model_name,
            llm_model=self._llm_label,
            tts_voice=d.voice.name,
        )
        status = ConversationStatus.COMPLETED
        try:
            self._partner_turn(opening=True, learner_text="")
            while True:
                partner_turn_id = self._speak_and_store_partner()
                window = _Window()
                transcript: LearnerTranscript | None = None
                while transcript is None and not window.quit:
                    self._wait_for_learner(window)  # after a pardon: same partner turn, fresh timer
                    if not window.quit:
                        transcript = self._record_and_transcribe(window.freeze_seconds)
                update_turn_listening(
                    d.conn, partner_turn_id,
                    ladder_step_reached=window.ladder_step, replay_count=window.replay,
                    slower_count=window.slower, show_text_count=window.show_text,
                )
                if transcript is None:
                    break
                self._partner_turn(opening=False, learner_text=transcript.text)
        except KeyboardInterrupt:
            status = ConversationStatus.ABORTED
        finish_conversation(d.conn, self._s.conversation_id, ended_at=d.now_iso(), status=status)
        return self._s.conversation_id

    # --- partner side -------------------------------------------------------

    def _partner_turn(self, *, opening: bool, learner_text: str) -> None:
        seed = self._d.picker.next().text
        try:
            reply = self._d.partner.opening(seed) if opening else self._d.partner.respond(learner_text, seed)
        except PartnerUnavailable:
            reply = fallback_reply(seed)
        self._s.seed_text = seed
        self._s.reply = reply
        self._s.audio = self._d.voice.synthesize(reply.turn.spoken_text())

    def _speak_and_store_partner(self) -> int:
        d, s = self._d, self._s
        assert s.reply is not None
        d.player.play(s.audio)
        index = self._next_index()
        audio_path = self._store(s.audio, index, "partner")
        return insert_turn(
            d.conn,
            conversation_id=s.conversation_id,
            turn_index=index,
            speaker=TurnSpeaker.PARTNER,
            text=s.reply.turn.spoken_text(),
            audio_path=str(audio_path),
            seed=s.seed_text,
            partner_turn_json=s.reply.turn.model_dump_json(),
            llm_model=s.reply.model,
        )

    # --- waiting for the learner -------------------------------------------

    def _wait_for_learner(self, window: _Window) -> None:
        """Wait for SPACE (or q); counts aids and fires the ladder into `window`."""
        d, s = self._d, self._s
        assert s.reply is not None
        spoken = s.reply.turn.spoken_text()
        started = d.clock.now()
        while True:
            key = d.keys.poll()
            if key == " ":
                window.freeze_seconds = round(d.clock.now() - started, 2)
                return
            if key == "q":
                window.quit = True
                return
            if key == "r":
                window.replay += 1
                d.player.play(s.audio)
            elif key == "s":
                window.slower += 1
                d.player.play(d.voice.synthesize(spoken, slower=True))
            elif key == "t":
                window.show_text += 1
                d.out(f"Partner: {spoken}")
            target = step_for(d.clock.now() - started, d.ladder)
            if target > window.ladder_step:
                window.ladder_step = int(target)
                helper = self._helper_text(target)
                if helper:
                    d.player.play(d.voice.synthesize(helper))
            d.clock.sleep(POLL_SECONDS)

    def _helper_text(self, step: LadderStep) -> str:
        turn = self._s.reply.turn  # type: ignore[union-attr]
        if step == LadderStep.NUDGE:
            return self._d.rng.choice(NUDGE_PHRASES)
        if step == LadderStep.STARTER:
            return turn.starter_phrase
        if step == LadderStep.REPHRASE:
            return turn.simpler_rephrase
        return ""

    # --- learner side --------------------------------------------------------

    def _record_and_transcribe(self, freeze_seconds: float | None) -> LearnerTranscript | None:
        d, s = self._d, self._s
        d.recorder.start()
        while d.keys.poll() != " ":
            d.clock.sleep(POLL_SECONDS)
        samples = d.recorder.stop()
        if len(samples) < MIN_SPEECH_SECONDS * SAMPLE_RATE:
            d.player.play(d.voice.synthesize(PARDON))
            return None
        audio = wav_bytes(samples)
        transcript = self._transcribe_with_retry(audio)
        if transcript is None or not transcript.text.strip():
            d.player.play(d.voice.synthesize(PARDON))
            return None
        index = self._next_index()
        audio_path = self._store(audio, index, "learner")
        insert_turn(
            d.conn,
            conversation_id=s.conversation_id,
            turn_index=index,
            speaker=TurnSpeaker.LEARNER,
            text=transcript.text,
            audio_path=str(audio_path),
            words_json=transcript.words_json(),
            freeze_seconds=freeze_seconds,
        )
        d.out(f"(du) {transcript.text}")
        return transcript

    def _transcribe_with_retry(self, audio: bytes) -> LearnerTranscript | None:
        for _ in range(2):
            try:
                return self._d.transcriber.transcribe(audio)
            except Exception:  # noqa: BLE001 — network/API failure: retry once, then pardon
                continue
        return None

    # --- helpers -------------------------------------------------------------

    def _next_index(self) -> int:
        index = self._s.turn_index
        self._s.turn_index += 1
        return index

    def _store(self, audio: bytes, index: int, speaker: str) -> Path:
        dest = self._d.paths.conversation_dir(self._s.conversation_id) / f"turn-{index:03d}-{speaker}.opus"
        self._d.store_audio(audio, dest)
        return dest
```

After a too-short recording or empty transcript the partner says `PARDON` and the learner answers the *same* partner turn again (no duplicate partner row, listening-aid counts keep accumulating, ladder steps already fired do not repeat).

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_session.py -q`
Expected: 5 passed. If `test_full_exchange…` fails on `ladder_step_reached`, check that the ladder check runs after key handling on every poll (nudge fires at 4.0 s, before SPACE at 5.0 s).

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q && git add src/self_talk_coach/conversation/session.py tests/conversation/test_session.py && git commit -m "feat(conversation): session loop with help ladder, listening aids, per-turn storage"
```

---

### Task 8: Hardware I/O, config, `stc talk`, first real conversation

**Files:**
- Create: `src/self_talk_coach/conversation/audio_io.py`
- Create: `src/self_talk_coach/conversation/config.py`
- Modify: `src/self_talk_coach/cli.py` (new `talk` command)
- Modify: `.env.example` (new `STC_*` names)
- Test: `tests/conversation/test_config.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces:
  - `audio_io.ConsoleKeys` (`poll`), `audio_io.MicRecorder` (`start`, `stop`), `audio_io.SpeakerPlayer` (`play`), `audio_io.RealClock` (`now`, `sleep`)
  - `config.ConfigError(Exception)`; `config.TalkConfig` frozen dataclass: `deepgram_api_key, gateway_base_url, gateway_api_key, partner_model, fallback_model, tts_voice, question_banks: tuple[Path, ...], ladder: LadderTimings`; `TalkConfig.from_env(env: Mapping[str, str]) -> TalkConfig`
  - CLI: `stc talk [--scenario TEXT] [--data-root PATH]`

- [ ] **Step 1: Write the failing config test**

`tests/conversation/test_config.py`:

```python
from pathlib import Path

import pytest

from self_talk_coach.conversation.config import ConfigError, TalkConfig
from self_talk_coach.conversation.help_ladder import LadderTimings

BASE = {
    "DEEPGRAM_API_KEY": "dg",
    "GATEWAY_BASE_URL": "https://gw.example/v1",
    "GATEWAY_API_KEY": "gw",
    "STC_QUESTION_BANKS": "C:/a/bank1.md;C:/b/bank2.md",
}


def test_defaults_and_parsing() -> None:
    cfg = TalkConfig.from_env(BASE)
    assert cfg.partner_model == "deepseek-v4-pro"
    assert cfg.fallback_model == "claude-sonnet-5"
    assert cfg.tts_voice == "de-DE-SeraphinaMultilingualNeural"
    assert cfg.question_banks == (Path("C:/a/bank1.md"), Path("C:/b/bank2.md"))
    assert cfg.ladder == LadderTimings()


def test_overrides() -> None:
    cfg = TalkConfig.from_env({**BASE, "STC_PARTNER_MODEL": "m", "STC_LADDER_SECONDS": "3,6,9"})
    assert cfg.partner_model == "m"
    assert cfg.ladder == LadderTimings(3, 6, 9)


@pytest.mark.parametrize("missing", ["DEEPGRAM_API_KEY", "GATEWAY_BASE_URL", "GATEWAY_API_KEY", "STC_QUESTION_BANKS"])
def test_missing_required_names_the_variable(missing: str) -> None:
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        TalkConfig.from_env(env)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/conversation/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement config, hardware I/O, CLI**

`src/self_talk_coach/conversation/config.py`:

```python
"""Conversation settings from environment (.env)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from self_talk_coach.conversation.help_ladder import LadderTimings

_REQUIRED = ("DEEPGRAM_API_KEY", "GATEWAY_BASE_URL", "GATEWAY_API_KEY", "STC_QUESTION_BANKS")


class ConfigError(Exception):
    """A required setting is missing or invalid."""


@dataclass(frozen=True)
class TalkConfig:
    deepgram_api_key: str
    gateway_base_url: str
    gateway_api_key: str
    partner_model: str
    fallback_model: str
    tts_voice: str
    question_banks: tuple[Path, ...]
    ladder: LadderTimings

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> TalkConfig:
        missing = [name for name in _REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ConfigError(f"Missing in .env: {', '.join(missing)}")
        try:
            ladder = LadderTimings.from_csv(env.get("STC_LADDER_SECONDS", "4,8,12"))
        except ValueError as exc:
            raise ConfigError(f"STC_LADDER_SECONDS: {exc}") from exc
        return cls(
            deepgram_api_key=env["DEEPGRAM_API_KEY"].strip(),
            gateway_base_url=env["GATEWAY_BASE_URL"].strip(),
            gateway_api_key=env["GATEWAY_API_KEY"].strip(),
            partner_model=env.get("STC_PARTNER_MODEL", "deepseek-v4-pro"),
            fallback_model=env.get("STC_FALLBACK_MODEL", "claude-sonnet-5"),
            tts_voice=env.get("STC_TTS_VOICE", "de-DE-SeraphinaMultilingualNeural"),
            question_banks=tuple(Path(p.strip()) for p in env["STC_QUESTION_BANKS"].split(";") if p.strip()),
            ladder=ladder,
        )
```

`src/self_talk_coach/conversation/audio_io.py`:

```python
"""Real hardware: Windows console keys, microphone, speakers, wall clock. Not unit-tested."""

from __future__ import annotations

import io
import msvcrt
import queue
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from self_talk_coach.conversation.audio_store import SAMPLE_RATE


class ConsoleKeys:
    def poll(self) -> str | None:
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
        return None


class MicRecorder:
    def __init__(self) -> None:
        self._chunks: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._chunks = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=lambda indata, frames, t, status: self._chunks.put(indata.copy()),
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        parts = []
        while not self._chunks.empty():
            parts.append(self._chunks.get())
        return np.concatenate(parts)[:, 0] if parts else np.zeros(0, dtype="float32")


class SpeakerPlayer:
    def play(self, audio: bytes) -> None:
        samples, samplerate = sf.read(io.BytesIO(audio), dtype="float32")
        sd.play(samples, samplerate)
        sd.wait()


class RealClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
```

In `src/self_talk_coach/cli.py`, add after the existing commands (keep all existing commands):

```python
@app.command("talk")
def talk_command(
    scenario: Annotated[
        str | None, typer.Option("--scenario", help="Section name (substring) from the question banks.")
    ] = None,
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
) -> None:
    """Start a spoken German conversation with the AI partner."""
    import os
    import random
    from datetime import UTC, datetime

    from dotenv import load_dotenv

    from self_talk_coach.conversation.audio_io import ConsoleKeys, MicRecorder, RealClock, SpeakerPlayer
    from self_talk_coach.conversation.config import ConfigError, TalkConfig
    from self_talk_coach.conversation.partner import OpenAIChatClient, Partner, build_system_prompt
    from self_talk_coach.conversation.question_bank import SeedPicker, filter_scenario, load_banks
    from self_talk_coach.conversation.session import ConversationSession, SessionDeps
    from self_talk_coach.conversation.stt import DeepgramTranscriber
    from self_talk_coach.conversation.tts import EdgeVoice
    from self_talk_coach.db import list_turns

    load_dotenv()
    try:
        cfg = TalkConfig.from_env(os.environ)
        seeds = filter_scenario(load_banks(cfg.question_banks), scenario)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    profile = paths.learner_profile_path.read_text(encoding="utf-8") if paths.learner_profile_path.is_file() else None
    rng = random.Random()
    partner = Partner(
        OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key),
        cfg.partner_model, cfg.fallback_model, build_system_prompt(profile),
    )
    typer.echo("SPACE = sprechen/stoppen · r = nochmal · s = langsamer · t = Text zeigen · q = Ende")
    with connect(paths.db_path) as conn:
        init_db(conn)
        deps = SessionDeps(
            partner=partner,
            transcriber=DeepgramTranscriber(cfg.deepgram_api_key),
            voice=EdgeVoice(cfg.tts_voice),
            player=SpeakerPlayer(),
            recorder=MicRecorder(),
            keys=ConsoleKeys(),
            clock=RealClock(),
            picker=SeedPicker(seeds, rng),
            conn=conn,
            paths=paths,
            ladder=cfg.ladder,
            rng=rng,
            now_iso=lambda: datetime.now(UTC).isoformat(timespec="seconds"),
        )
        cid = ConversationSession(deps, scenario=scenario, llm_label=cfg.partner_model).run()
        turns = list_turns(conn, cid)
    freezes = sorted(t["freeze_seconds"] for t in turns if t["freeze_seconds"] is not None)
    median = freezes[len(freezes) // 2] if freezes else None
    typer.echo(f"Gespräch {cid} gespeichert: {len(turns)} Turns, Median-Freeze {median} s")
```

Append to `.env.example`:

```bash
# Conversation partner (v1) — required for `stc talk`
# STC_QUESTION_BANKS=C:/path/to/question-bank.md   (';'-separated, read in place, never copied)
STC_QUESTION_BANKS=
# Optional overrides (defaults shown)
# STC_PARTNER_MODEL=deepseek-v4-pro
# STC_FALLBACK_MODEL=claude-sonnet-5
# STC_TTS_VOICE=de-DE-SeraphinaMultilingualNeural
# STC_LADDER_SECONDS=4,8,12
```

- [ ] **Step 4: Run tests and CLI help**

Run: `.venv/Scripts/python -m pytest -q && .venv/Scripts/stc talk --help`
Expected: all tests pass (46 + 9 + 4 + 9 + 1 + 4 + 5 + 6 = 84); help text lists `--scenario` and `--data-root`.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && git add src/self_talk_coach/conversation/audio_io.py src/self_talk_coach/conversation/config.py src/self_talk_coach/cli.py .env.example tests/conversation/test_config.py && git commit -m "feat(conversation): stc talk command with real audio, config and keys"
```

- [ ] **Step 6: Learner setup (user action, not committed)**

1. In `.env` set `STC_QUESTION_BANKS=C:/Users/suman/Desktop/Docs/Job/Projects/Myself/German-Learning/question-bank.md`.
2. Create `data/learner-profile.md` (gitignored) with a few plain lines, e.g. level, city, job/shift pattern, current goal. The learner writes the content.
3. Headset plugged in and set as Windows default input/output.

- [ ] **Step 7: First real conversation (user, Windows PowerShell)**

Run: `& "C:\Users\suman\Desktop\Docs\Job\Projects\self-talk-coach\.venv\Scripts\stc.exe" talk`
Exercise once each: answer normally; stay silent ≥ 13 s (hear nudge, starter, simpler question); press `r`, `s`, `t`; make a deliberate error (expect a second-person recast); quit with `q`.
Expected: final line `Gespräch <id> gespeichert: <n> Turns, Median-Freeze <x> s`; `data/conversations/<id>/turn-*.opus` files exist.

Verify storage: `.venv/Scripts/python -c "import sqlite3;c=sqlite3.connect('data/db/self_talk_coach.sqlite');print(c.execute('select speaker,freeze_seconds,ladder_step_reached,replay_count,slower_count,show_text_count,llm_model,substr(text,1,50) from turns order by id desc limit 8').fetchall())"`
Expected: alternating partner/learner rows, counts matching what was pressed.

- [ ] **Step 8: Record outcome**

Append to the spec's `## Spike results` section a `Phase 1 first conversation (date)` line: what worked, latency feel, any bug found. Bugs → BACKLOG with severity. Set this plan `**Status:** done`. Commit:

```bash
git add docs/exec-plans/active/2026-10-04-conversation-partner-design.md docs/exec-plans/active/2026-10-05-conversation-partner-phase1-loop.md BACKLOG.md && git commit -m "docs: phase 1 first conversation results"
```
