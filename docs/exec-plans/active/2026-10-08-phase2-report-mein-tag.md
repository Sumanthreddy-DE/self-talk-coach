# Phase 2 — Session report, comprehension check, "Mein Tag" mode — Implementation Plan

**Status:** active
**Last verified:** 2026-10-08
**Spec:** `docs/exec-plans/active/2026-10-04-conversation-partner-design.md` § Session report, § Data flow 5, § Metrics
**Approved by user:** 2026-10-09 (execution in a separate session).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every `stc talk` conversation the learner gets a session report: top mistakes with corrections, better phrasings, English→German, freeze trend, listening aids, rescue phrases, comprehension checks and new words. Every 4th partner turn checks listening comprehension, and the new "Mein Tag" mode lets the learner narrate the day while the partner only asks short follow-up questions.

**Architecture:** The numbers (freeze, listening aids, missed rescue chances) are plain code over the stored `turns` rows. Mistakes, phrasings, English parts, rescue phrases and retell scores come from **one report-LLM call per conversation** (Sonnet 5 via the gateway, JSON). Code verifies every quoted learner fragment against the stored transcript and drops anything the learner did not say (ADR 0005 spirit, ADR 0006 new). New words come from the existing baseline plus spaCy `de_core_news_lg` (ADR 0002). The report is written to `data/conversations/<id>/report.md`, printed, and its findings land in `learning_candidates` with `turn_id`. Mein Tag reuses the conversation loop with its own partner prompt, a fixed-seed deck, a 15/25/35 s help ladder, 180 s recordings, no recast and no comprehension check.

**Tech Stack:** Python 3.12, SQLite, pydantic 2, OpenAI-compatible gateway client (existing), spaCy 3.8 + `de_core_news_lg`, Typer, pytest with fakes.

## Global Constraints

- STT stays Deepgram Nova-3 `language=de` (s6 spike 2026-10-08: `multi` fixed 7/10 learner errors). Do not touch `stt.py`.
- Learner errors are never invented: every report finding that quotes the learner must be a substring of that learner turn's stored text (after lower-casing and punctuation stripping), or it is dropped and the drop is shown as a status line.
- Fallbacks are never silent (Working Rule 13): report-LLM failure and missing spaCy model each print a `[Hinweis] … Grund: …` status line, and a test asserts the line.
- Repo is public: no bank contents, learner profile, audio or transcripts in the repo or in tests. Test fixtures use invented sentences.
- `stc` must keep ≥ 2 Typer commands (STATE landmine). `stc talk` runs from the repo root in a real Windows console.
- Report model default `claude-sonnet-5` (`STC_REPORT_MODEL`). Mein Tag ladder default `15,25,35` (`STC_MEIN_TAG_LADDER_SECONDS`).
- Report text is German (headings, corrections); the one-line grammar explanation is English, at most 12 words.
- Tests: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=8` (the timeout catches fake-clock hangs). Lint: `bash scripts/lint-arch.sh` and `.venv/Scripts/ruff.exe check src tests` before every commit.
- Scripted edits on Windows keep the file's line endings; compare `git diff --stat` with `git diff --ignore-cr-at-eol --stat` before committing.
- No `Co-Authored-By` or AI attribution in commits. Do not push; the user pushes.

## Decisions made with the user (2026-10-08)

- Keep `language=de` (closed `mixed-language-stt`, fead0b8).
- Mein Tag: help ladder starts at about 15 s; no corrections during the talk; the partner takes the learner's English word up in German in its follow-up question; English→German also listed in the report.
- Not in this plan: double-click launcher (`talk-launcher`), web UI (`web-ui`), "what you could have said" from the interview questionnaire (needs `interview-questionnaire-format` parser first).

## Prerequisite (user, laptop PowerShell, once)

The vocab miner needs the spaCy model `de_core_news_lg` (~570 MB, ADR 0002). It is not installed in `.venv` (checked 2026-10-08). Installing software is the user's call, so the user runs it:

```
cd C:\Users\suman\Desktop\Docs\Job\Projects\self-talk-coach
.\.venv\Scripts\python.exe -m spacy download de_core_news_lg
```

Without it everything works except the "Neue Wörter" section, which then prints the skip reason.

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/self_talk_coach/domain.py` | modify | `CandidateType`, `ReportStatus`, `CONVERSATION_PRODUCER`, `NewCandidate` |
| `src/self_talk_coach/db.py` | modify | `learning_candidates.turn_id` migration; `comprehension_check` on insert; report helpers |
| `src/self_talk_coach/conversation/config.py` | modify | `report_model`, `mein_tag_ladder` |
| `src/self_talk_coach/conversation/partner.py` | modify | client `max_tokens`/`temperature`; comprehension impulse; `drop_recast`; Mein Tag prompt |
| `src/self_talk_coach/conversation/report_metrics.py` | create | freeze median/trend, per-question freeze, listening summary, missed rescue chances |
| `src/self_talk_coach/conversation/report_llm.py` | create | report prompt, findings models, parse, verify against transcript, top errors |
| `src/self_talk_coach/mine.py` | rewrite stub | vocab miner + out-of-baseline ratio, spaCy lemmatizer |
| `src/self_talk_coach/conversation/report_render.py` | create | `ReportData` → Markdown |
| `src/self_talk_coach/conversation/report.py` | create | assemble report, persist candidates + status + `report.md` |
| `src/self_talk_coach/conversation/mein_tag.py` | create | `MEIN_TAG`, `MeinTagDeck`, record limit |
| `src/self_talk_coach/conversation/question_bank.py` | modify | `Deck` protocol |
| `src/self_talk_coach/conversation/session.py` | modify | comprehension check every 4th partner turn; configurable record limit |
| `src/self_talk_coach/cli.py` | modify | `stc report <id>`, auto-report after `talk`, `--mein-tag`, start-menu `m` |
| tests under `tests/conversation/` and `tests/test_mine.py` | create/modify | one test file per new module |
| docs | modify | ADR 0006, spec, CONTEXT.md, BACKLOG.md, `.env.example` |

---

### Task 1: Config + chat client knobs

**Files:**
- Modify: `src/self_talk_coach/conversation/config.py`
- Modify: `src/self_talk_coach/conversation/partner.py` (`OpenAIChatClient`)
- Test: `tests/conversation/test_config.py`, `tests/conversation/test_partner.py`

**Interfaces:**
- Produces: `TalkConfig.report_model: str`, `TalkConfig.mein_tag_ladder: LadderTimings`; `OpenAIChatClient(base_url, api_key, *, max_tokens=400, temperature=0.8)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/conversation/test_config.py`:

```python
def test_report_model_and_mein_tag_ladder_defaults() -> None:
    cfg = TalkConfig.from_env(BASE)
    assert cfg.report_model == "claude-sonnet-5"
    assert cfg.mein_tag_ladder == LadderTimings(15.0, 25.0, 35.0)


def test_mein_tag_ladder_from_env_and_invalid() -> None:
    cfg = TalkConfig.from_env({**BASE, "STC_MEIN_TAG_LADDER_SECONDS": "10,20,30", "STC_REPORT_MODEL": "m"})
    assert cfg.mein_tag_ladder == LadderTimings(10.0, 20.0, 30.0)
    assert cfg.report_model == "m"
    with pytest.raises(ConfigError, match="STC_MEIN_TAG_LADDER_SECONDS"):
        TalkConfig.from_env({**BASE, "STC_MEIN_TAG_LADDER_SECONDS": "30,20,10"})
```

Append to `tests/conversation/test_partner.py`:

```python
def test_openai_client_passes_max_tokens_and_temperature() -> None:
    from types import SimpleNamespace

    from self_talk_coach.conversation.partner import OpenAIChatClient

    seen: dict = {}

    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    client = OpenAIChatClient("https://gw.example/v1", "k", max_tokens=3000, temperature=0.2)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert client.complete("m", [{"role": "user", "content": "x"}], 5.0) == "{}"
    assert seen["max_tokens"] == 3000 and seen["temperature"] == 0.2
```

- [ ] **Step 2: Run, expect FAIL**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=8 tests/conversation/test_config.py tests/conversation/test_partner.py`
Expected: FAIL — `AttributeError: 'TalkConfig' object has no attribute 'report_model'` and `TypeError: ... unexpected keyword argument 'max_tokens'`.

- [ ] **Step 3: Implement**

In `config.py`, add fields after `phrase_sections` and parse them in `from_env`:

```python
    report_model: str
    mein_tag_ladder: LadderTimings
```

```python
        try:
            ladder = LadderTimings.from_csv(env.get("STC_LADDER_SECONDS", "4,8,12"))
        except ValueError as exc:
            raise ConfigError(f"STC_LADDER_SECONDS: {exc}") from exc
        try:
            mein_tag_ladder = LadderTimings.from_csv(env.get("STC_MEIN_TAG_LADDER_SECONDS", "15,25,35"))
        except ValueError as exc:
            raise ConfigError(f"STC_MEIN_TAG_LADDER_SECONDS: {exc}") from exc
```

and in the `cls(...)` call:

```python
            report_model=env.get("STC_REPORT_MODEL", "claude-sonnet-5"),
            mein_tag_ladder=mein_tag_ladder,
```

In `partner.py`, `OpenAIChatClient`:

```python
    def __init__(self, base_url: str, api_key: str, *, max_tokens: int = 400, temperature: float = 0.8) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0)
        self._max_tokens = max_tokens
        self._temperature = temperature

    def complete(self, model: str, messages: list[dict[str, str]], timeout: float) -> str:
        resp = self._client.chat.completions.create(
            model=model, messages=messages, temperature=self._temperature,
            max_tokens=self._max_tokens, timeout=timeout,
        )
```

(rest of `complete` unchanged).

- [ ] **Step 4: Run, expect PASS**

Same command. Expected: all pass.

- [ ] **Step 5: Lint + commit**

```bash
bash scripts/lint-arch.sh && .venv/Scripts/ruff.exe check src tests
git add src/self_talk_coach/conversation/config.py src/self_talk_coach/conversation/partner.py tests/conversation/test_config.py tests/conversation/test_partner.py
git commit -m "feat(config): report model, Mein Tag ladder, client token/temperature knobs"
```

---

### Task 2: Domain types + DB support for the report

**Files:**
- Modify: `src/self_talk_coach/domain.py`, `src/self_talk_coach/db.py`
- Test: `tests/conversation/test_report_db.py` (create)

**Interfaces:**
- Produces (domain): `CandidateType` (`GRAMMAR_CORRECTION="grammar_correction"`, `PHRASE_UPGRADE="phrase_upgrade"`, `VOCABULARY="vocabulary"` — same values as the paused M3 plan), `ReportStatus` (`pending/done/failed`), `CONVERSATION_PRODUCER = "conversation"`, `NewCandidate(turn_id: int, candidate_type: CandidateType, original_text: str, suggested_text: str, explanation: str)`.
- Produces (db): `insert_turn(..., comprehension_check: bool = False)`, `set_report_status(conn, conversation_id, status: ReportStatus) -> None`, `update_turn_out_of_baseline(conn, turn_id, ratio: float | None) -> None`, `replace_conversation_candidates(conn, conversation_id, candidates: Iterable[NewCandidate]) -> None`, `list_conversation_candidates(conn, conversation_id) -> list[sqlite3.Row]`, `previous_conversations(conn, before_id, *, limit=5, exclude_scenario=None) -> list[sqlite3.Row]`. `SCHEMA_VERSION = 3`.

- [ ] **Step 1: Write the failing tests** — `tests/conversation/test_report_db.py`:

```python
import sqlite3
from pathlib import Path

from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_conversation_candidates,
    list_turns,
    previous_conversations,
    replace_conversation_candidates,
    set_report_status,
    update_turn_out_of_baseline,
)
from self_talk_coach.domain import (
    CandidateType,
    ConversationStatus,
    NewCandidate,
    ReportStatus,
    TurnSpeaker,
)


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "t.sqlite")
    init_db(conn)
    return conn


def _conversation(conn, scenario=None, status=ConversationStatus.COMPLETED) -> int:
    cid = insert_conversation(conn, started_at="2026-10-08T10:00:00+00:00", scenario=scenario,
                              stt_model="s", llm_model="l", tts_voice="v")
    finish_conversation(conn, cid, ended_at="2026-10-08T10:05:00+00:00", status=status)
    return cid


def test_old_db_gets_turn_id_column(tmp_path: Path) -> None:
    conn = connect(tmp_path / "old.sqlite")
    conn.execute("CREATE TABLE learning_candidates (id INTEGER PRIMARY KEY, candidate_type TEXT NOT NULL, "
                 "transcript_segment_id INTEGER, original_text TEXT NOT NULL, suggested_text TEXT, "
                 "explanation TEXT NOT NULL, severity INTEGER NOT NULL DEFAULT 1, usefulness INTEGER NOT NULL DEFAULT 1, "
                 "status TEXT NOT NULL DEFAULT 'pending', producer TEXT NOT NULL, "
                 "created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    init_db(conn)
    init_db(conn)  # idempotent
    columns = [r[1] for r in conn.execute("PRAGMA table_info(learning_candidates)")]
    assert columns.count("turn_id") == 1


def test_comprehension_flag_status_ratio_and_candidates(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = _conversation(conn)
    partner = insert_turn(conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER,
                          text="Erzähl kurz nach.", comprehension_check=True)
    learner = insert_turn(conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
                          text="Ich habe einen Frage.")
    update_turn_out_of_baseline(conn, partner, 0.25)
    set_report_status(conn, cid, ReportStatus.DONE)
    first = NewCandidate(learner, CandidateType.GRAMMAR_CORRECTION, "einen Frage", "eine Frage", "Kasus/Artikel: Frage is feminine")
    replace_conversation_candidates(conn, cid, [first])
    replace_conversation_candidates(conn, cid, [first])  # rerun replaces, never duplicates

    turns = list_turns(conn, cid)
    assert turns[0]["comprehension_check"] == 1 and turns[1]["comprehension_check"] == 0
    assert turns[0]["out_of_baseline_ratio"] == 0.25
    assert get_conversation(conn, cid)["report_status"] == "done"
    rows = list_conversation_candidates(conn, cid)
    assert len(rows) == 1
    assert rows[0]["turn_id"] == learner and rows[0]["producer"] == "conversation"
    assert rows[0]["candidate_type"] == "grammar_correction" and rows[0]["suggested_text"] == "eine Frage"


def test_previous_conversations_completed_only_excluding_scenario(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    a = _conversation(conn)
    _conversation(conn, status=ConversationStatus.ABORTED)
    _conversation(conn, scenario="Mein Tag")
    b = _conversation(conn, scenario="McDonald's")
    current = _conversation(conn)
    ids = [r["id"] for r in previous_conversations(conn, current, exclude_scenario="Mein Tag")]
    assert ids == [b, a]
```

- [ ] **Step 2: Run, expect FAIL** — `pytest ... tests/conversation/test_report_db.py` → `ImportError` (names missing).

- [ ] **Step 3: Implement**

`domain.py` — add at the end (and `from dataclasses import dataclass` at the top):

```python
CONVERSATION_PRODUCER = "conversation"


class CandidateType(StrEnum):
    """Kind of learning candidate; values shared with the M3 first-language-analysis plan."""

    GRAMMAR_CORRECTION = "grammar_correction"
    PHRASE_UPGRADE = "phrase_upgrade"
    VOCABULARY = "vocabulary"


class ReportStatus(StrEnum):
    """Session-report state of one conversation."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class NewCandidate:
    """A learning candidate found in one conversation turn."""

    turn_id: int
    candidate_type: CandidateType
    original_text: str
    suggested_text: str
    explanation: str
```

`db.py`:
- `SCHEMA_VERSION = 3`; import `CONVERSATION_PRODUCER, NewCandidate, ReportStatus` from domain; `Iterable` is already imported.
- In `init_db`, after `executescript(...)` and before `PRAGMA user_version`:

```python
    columns = [r[1] for r in conn.execute("PRAGMA table_info(learning_candidates)")]
    if "turn_id" not in columns:
        conn.execute(
            "ALTER TABLE learning_candidates ADD COLUMN turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL"
        )
```

- `insert_turn`: add keyword `comprehension_check: bool = False`, add the column to the INSERT column list and `int(comprehension_check)` to the values tuple (11 placeholders).
- New functions (end of file):

```python
def set_report_status(conn: sqlite3.Connection, conversation_id: int, status: ReportStatus) -> None:
    conn.execute("UPDATE conversations SET report_status = ? WHERE id = ?", (status.value, conversation_id))
    conn.commit()


def update_turn_out_of_baseline(conn: sqlite3.Connection, turn_id: int, ratio: float | None) -> None:
    conn.execute("UPDATE turns SET out_of_baseline_ratio = ? WHERE id = ?", (ratio, turn_id))
    conn.commit()


def replace_conversation_candidates(
    conn: sqlite3.Connection, conversation_id: int, candidates: Iterable[NewCandidate]
) -> None:
    """Swap this conversation's report candidates for a fresh set: `stc report` reruns never duplicate."""
    conn.execute(
        "DELETE FROM learning_candidates WHERE producer = ? "
        "AND turn_id IN (SELECT id FROM turns WHERE conversation_id = ?)",
        (CONVERSATION_PRODUCER, conversation_id),
    )
    conn.executemany(
        """
        INSERT INTO learning_candidates
            (candidate_type, turn_id, original_text, suggested_text, explanation, producer)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (c.candidate_type.value, c.turn_id, c.original_text, c.suggested_text, c.explanation,
             CONVERSATION_PRODUCER)
            for c in candidates
        ],
    )
    conn.commit()


def list_conversation_candidates(conn: sqlite3.Connection, conversation_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT lc.* FROM learning_candidates lc JOIN turns t ON t.id = lc.turn_id "
        "WHERE t.conversation_id = ? ORDER BY lc.id",
        (conversation_id,),
    ).fetchall()


def previous_conversations(
    conn: sqlite3.Connection, before_id: int, *, limit: int = 5, exclude_scenario: str | None = None
) -> list[sqlite3.Row]:
    """Completed conversations before `before_id`, newest first (freeze-trend comparison set)."""
    return conn.execute(
        "SELECT * FROM conversations WHERE id < ? AND status = ? "
        "AND (scenario IS NULL OR scenario != ?) ORDER BY id DESC LIMIT ?",
        (before_id, ConversationStatus.COMPLETED.value, exclude_scenario or "", limit),
    ).fetchall()
```

- [ ] **Step 4: Run, expect PASS** — new file plus the whole suite (migration touches every DB test): `pytest -q ...` → all green.

- [ ] **Step 5: Lint + commit**

```bash
git add src/self_talk_coach/domain.py src/self_talk_coach/db.py tests/conversation/test_report_db.py
git commit -m "feat(db): report status, candidates per turn, comprehension flag, schema v3"
```

---

### Task 3: Report metrics (no LLM)

**Files:**
- Create: `src/self_talk_coach/conversation/report_metrics.py`
- Modify: `src/self_talk_coach/cli.py` (import `median_freeze` from the new module, delete the local copy and the `statistics` import if unused)
- Test: `tests/conversation/test_report_metrics.py` (create); `tests/conversation/test_talk_summary.py` keeps importing `median_freeze` from `cli` and must stay green.

**Interfaces:**
- Produces: `median_freeze(turns) -> float | None`; `FreezeTrend(current, previous, compared)` with `.delta`; `freeze_trend(current_turns, previous: Sequence[Sequence[Turn]]) -> FreezeTrend`; `answer_pairs(turns) -> list[tuple[Turn, Turn]]`; `freeze_per_question(turns) -> list[tuple[str, float]]`; `ListeningSummary(partner_turns, aids, hard)` with `.per_turn`; `listening_summary(turns)`; `missed_rescue(turns, rescue_turns: set[int]) -> list[str]`. `Turn = Mapping[str, Any]` (sqlite rows and dicts both work).

- [ ] **Step 1: Write the failing tests** — `tests/conversation/test_report_metrics.py`:

```python
from self_talk_coach.conversation.report_metrics import (
    answer_pairs,
    freeze_per_question,
    freeze_trend,
    listening_summary,
    missed_rescue,
)


def _p(i, text, ladder=0, replay=0, slower=0, shown=0):
    return {"turn_index": i, "speaker": "partner", "text": text, "freeze_seconds": None,
            "ladder_step_reached": ladder, "replay_count": replay, "slower_count": slower, "show_text_count": shown}


def _l(i, text, freeze):
    return {"turn_index": i, "speaker": "learner", "text": text, "freeze_seconds": freeze,
            "ladder_step_reached": 0, "replay_count": 0, "slower_count": 0, "show_text_count": 0}


TURNS = [
    _p(0, "Wo arbeitest du?", replay=1),
    _l(1, "Bei McDonald's.", 2.0),
    _p(2, "Seit wann?", ladder=2),
    _l(3, "Seit zwei Jahre.", 9.0),
    _p(4, "Und wie ist der Chef?", ladder=3, slower=1, shown=1),
    _l(5, "Kannst du das nochmal sagen?", 13.0),
    _p(6, "Ich frage, wie dein Chef ist."),
]


def test_answer_pairs_and_freeze_per_question() -> None:
    assert [(p["turn_index"], l["turn_index"]) for p, l in answer_pairs(TURNS)] == [(0, 1), (2, 3), (4, 5)]
    assert freeze_per_question(TURNS) == [("Wo arbeitest du?", 2.0), ("Seit wann?", 9.0), ("Und wie ist der Chef?", 13.0)]


def test_freeze_trend_against_previous_medians() -> None:
    previous = [[_l(1, "a", 10.0), _l(3, "b", 12.0)], [_l(1, "c", 14.0)], [_p(0, "nur Partner")]]
    trend = freeze_trend(TURNS, previous)
    assert trend.current == 9.0
    assert trend.previous == 12.5  # median of 11.0 and 14.0; conversation without freezes skipped
    assert trend.compared == 2
    assert trend.delta == -3.5
    assert freeze_trend(TURNS, []).delta is None


def test_listening_summary_counts_aids_and_lists_hard_sentences() -> None:
    summary = listening_summary(TURNS)
    assert summary.partner_turns == 4 and summary.aids == 3 and summary.per_turn == 0.75
    assert summary.hard == ["Wo arbeitest du?", "Und wie ist der Chef?"]


def test_missed_rescue_when_help_came_and_no_rescue_phrase() -> None:
    # turn 5 used a rescue phrase, so only "Seit wann?" (ladder 2, answer turn 3) is a missed chance
    assert missed_rescue(TURNS, rescue_turns={5}) == ["Seit wann?"]
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError: ...report_metrics`.

- [ ] **Step 3: Implement** — `src/self_talk_coach/conversation/report_metrics.py`:

```python
"""Session-report numbers derived from stored turns, without any LLM (spec § Metrics)."""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

Turn = Mapping[str, Any]
AID_COLUMNS = ("replay_count", "slower_count", "show_text_count")
# Ladder step from which the learner had help long enough that a rescue phrase was the better move.
RESCUE_LADDER_STEP = 2


def median_freeze(turns: Sequence[Turn]) -> float | None:
    """Median of the recorded learner freezes; None when no turn has one."""
    freezes = [t["freeze_seconds"] for t in turns if t["freeze_seconds"] is not None]
    return statistics.median(freezes) if freezes else None


@dataclass(frozen=True)
class FreezeTrend:
    current: float | None
    previous: float | None  # median of the earlier conversations' medians
    compared: int  # earlier conversations that had at least one freeze

    @property
    def delta(self) -> float | None:
        if self.current is None or self.previous is None:
            return None
        return round(self.current - self.previous, 2)


def freeze_trend(current_turns: Sequence[Turn], previous: Sequence[Sequence[Turn]]) -> FreezeTrend:
    medians = [m for m in (median_freeze(turns) for turns in previous) if m is not None]
    return FreezeTrend(
        current=median_freeze(current_turns),
        previous=statistics.median(medians) if medians else None,
        compared=len(medians),
    )


def answer_pairs(turns: Sequence[Turn]) -> list[tuple[Turn, Turn]]:
    """(partner turn, learner turn that answered it), in conversation order."""
    pairs: list[tuple[Turn, Turn]] = []
    asked: Turn | None = None
    for turn in turns:
        if turn["speaker"] == "partner":
            asked = turn
        elif asked is not None:
            pairs.append((asked, turn))
            asked = None
    return pairs


def freeze_per_question(turns: Sequence[Turn]) -> list[tuple[str, float]]:
    return [(p["text"], a["freeze_seconds"]) for p, a in answer_pairs(turns) if a["freeze_seconds"] is not None]


@dataclass(frozen=True)
class ListeningSummary:
    partner_turns: int
    aids: int
    hard: list[str]  # partner sentences the learner replayed, slowed down or read

    @property
    def per_turn(self) -> float:
        return round(self.aids / self.partner_turns, 2) if self.partner_turns else 0.0


def listening_summary(turns: Sequence[Turn]) -> ListeningSummary:
    partner = [t for t in turns if t["speaker"] == "partner"]
    return ListeningSummary(
        partner_turns=len(partner),
        aids=sum(t[c] for t in partner for c in AID_COLUMNS),
        hard=[t["text"] for t in partner if any(t[c] for c in AID_COLUMNS)],
    )


def missed_rescue(turns: Sequence[Turn], rescue_turns: set[int]) -> list[str]:
    """Partner questions where the ladder reached the starter phrase and the answer had no rescue phrase."""
    return [
        p["text"]
        for p, a in answer_pairs(turns)
        if p["ladder_step_reached"] >= RESCUE_LADDER_STEP and a["turn_index"] not in rescue_turns
    ]
```

In `cli.py`: delete `def median_freeze` and add `from self_talk_coach.conversation.report_metrics import median_freeze` at module top (keeps `from self_talk_coach.cli import median_freeze` working for the existing test). Remove `import statistics` if nothing else uses it.

- [ ] **Step 4: Run, expect PASS** — new tests + `tests/conversation/test_talk_summary.py`.

- [ ] **Step 5: Lint + commit**

```bash
git add src/self_talk_coach/conversation/report_metrics.py src/self_talk_coach/cli.py tests/conversation/test_report_metrics.py
git commit -m "feat(report): freeze trend, listening aids, missed rescue chances from turns"
```

---

### Task 4: Report-LLM analysis with transcript verification

**Files:**
- Create: `src/self_talk_coach/conversation/report_llm.py`
- Test: `tests/conversation/test_report_llm.py` (create)

**Interfaces:**
- Consumes: `ChatClient` protocol from `partner.py` (`complete(model, messages, timeout) -> str`).
- Produces: `CATEGORIES`; pydantic `ErrorFinding(turn, original, corrected, category, explanation)`, `PhrasingFinding(turn, original, better)`, `EnglishFinding(turn, english, german)`, `RescueFinding(turn, phrase)`, `ComprehensionFinding(turn, score, missed)`, `ReportFindings(errors, phrasings, english, rescue_phrases, comprehension)`; `ReportFormatError`; `transcript_lines(turns) -> str`; `build_messages(turns) -> list[dict[str, str]]`; `parse_findings(raw) -> ReportFindings`; `verify_findings(findings, turns) -> tuple[ReportFindings, int]` (int = dropped count); `analyze(client, model, turns, timeout=90.0) -> ReportFindings`; `top_errors(errors, n=3) -> list[tuple[str, list[ErrorFinding]]]`. `turn` everywhere = `turns.turn_index`.

- [ ] **Step 1: Write the failing tests** — `tests/conversation/test_report_llm.py`:

```python
import json

import pytest

from self_talk_coach.conversation.report_llm import (
    ErrorFinding,
    ReportFindings,
    ReportFormatError,
    analyze,
    parse_findings,
    top_errors,
    transcript_lines,
    verify_findings,
)

TURNS = [
    {"turn_index": 0, "speaker": "partner", "text": "Wie war die Schicht?", "comprehension_check": 0},
    {"turn_index": 1, "speaker": "learner", "text": "Ich habe einen Frage, es war really stressful.", "comprehension_check": 0},
    {"turn_index": 2, "speaker": "partner", "text": "Ich war um acht im Laden. Erzähl kurz nach.", "comprehension_check": 1},
    {"turn_index": 3, "speaker": "learner", "text": "Du warst im Laden. Kannst du das nochmal sagen?", "comprehension_check": 0},
]

FINDINGS = {
    "errors": [
        {"turn": 1, "original": "einen Frage", "corrected": "eine Frage", "category": "Kasus/Artikel", "explanation": "Frage is feminine"},
        {"turn": 1, "original": "einen Antwort", "corrected": "eine Antwort", "category": "Kasus/Artikel", "explanation": "invented"},
        {"turn": 0, "original": "Wie war", "corrected": "x", "category": "Verbposition", "explanation": "partner turn"},
        {"turn": 3, "original": "Du warst im Laden", "corrected": "Du warst im Laden", "category": "Tippfehler", "explanation": "odd"},
    ],
    "phrasings": [],
    "english": [{"turn": 1, "english": "really stressful", "german": "echt stressig"}],
    "rescue_phrases": [{"turn": 3, "phrase": "Kannst du das nochmal sagen"}],
    "comprehension": [{"turn": 3, "score": 1, "missed": "um acht"}, {"turn": 3, "score": 7, "missed": ""}],
}


class FakeClient:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls: list = []

    def complete(self, model, messages, timeout):
        self.calls.append((model, messages, timeout))
        return self.raw


def test_transcript_lines_mark_speaker_turn_and_check() -> None:
    lines = transcript_lines(TURNS).splitlines()
    assert lines[0] == "[P0] Wie war die Schicht?"
    assert lines[2] == "[P2] (CHECK) Ich war um acht im Laden. Erzähl kurz nach."
    assert lines[3].startswith("[L3] ")


def test_parse_handles_fences_and_unknown_category() -> None:
    findings = parse_findings("Hier:\n```json\n" + json.dumps(FINDINGS) + "\n```")
    assert findings.errors[3].category == "Sonstiges"
    with pytest.raises(ReportFormatError):
        parse_findings("kein JSON")


def test_verify_drops_quotes_the_learner_never_said() -> None:
    kept, dropped = verify_findings(parse_findings(json.dumps(FINDINGS)), TURNS)
    assert [e.original for e in kept.errors] == ["einen Frage", "Du warst im Laden"]
    assert kept.english[0].german == "echt stressig"
    assert kept.rescue_phrases[0].turn == 3
    assert [c.score for c in kept.comprehension] == [1]
    assert dropped == 3  # invented quote, partner turn, score out of range


def test_analyze_sends_transcript_to_report_model() -> None:
    client = FakeClient(json.dumps(FINDINGS))
    findings = analyze(client, "claude-sonnet-5", TURNS)
    model, messages, timeout = client.calls[0]
    assert model == "claude-sonnet-5" and timeout == 90.0
    assert "[L1] Ich habe einen Frage" in messages[1]["content"]
    assert isinstance(findings, ReportFindings)


def test_top_errors_groups_by_category_most_frequent_first() -> None:
    errors = [
        ErrorFinding(turn=1, original="a", corrected="b", category="Verbposition"),
        ErrorFinding(turn=3, original="c", corrected="d", category="Kasus/Artikel"),
        ErrorFinding(turn=5, original="e", corrected="f", category="Kasus/Artikel"),
    ]
    assert [(cat, len(items)) for cat, items in top_errors(errors)] == [("Kasus/Artikel", 2), ("Verbposition", 1)]
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `src/self_talk_coach/conversation/report_llm.py`:

```python
"""Session-report analysis: one report-LLM call per conversation, every quote checked (ADR 0006)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from self_talk_coach.conversation.partner import ChatClient

Turn = Mapping[str, Any]
CATEGORIES = ("Verbposition", "Kasus/Artikel", "Verbform", "Präposition", "Wortwahl", "Sonstiges")
CHECK_MARK = "(CHECK)"

_SYSTEM = f"""You analyse one spoken German practice conversation of a B1 learner.
Learner turns are speech-to-text output that keeps the learner's errors exactly as spoken.
Lines look like "[L4] text" (learner, turn 4) or "[P3] text" (partner, turn 3). "{CHECK_MARK}" marks a partner turn
that asked the learner to retell what the partner just said.
Return ONLY a JSON object with these keys:
- "errors": real grammar or word errors in LEARNER turns:
  {{"turn": int, "original": str, "corrected": str, "category": one of {list(CATEGORIES)}, "explanation": str}}
  "explanation": English, max 12 words. Skip filler (äh, okay), errors the learner corrected himself, and
  unclear words that may be speech-to-text noise.
- "phrasings": correct but unnatural learner sentences: {{"turn": int, "original": str, "better": str}}
- "english": English words or phrases the learner used: {{"turn": int, "english": str, "german": str}}
- "rescue_phrases": phrases the learner used to buy time or ask for repetition or clarification
  ("Kannst du das nochmal sagen?", "Ich habe das nicht verstanden", "Moment, ich überlege"):
  {{"turn": int, "phrase": str}}. These are a good strategy, never a listening failure.
- "comprehension": for each learner turn directly after a {CHECK_MARK} partner turn:
  {{"turn": int, "score": 0|1|2, "missed": str}} (0 = main point missed, 1 = main point only,
  2 = main point and a detail; "missed": what was left out, short German).
"original", "english" and "phrase" must be copied character for character from that learner turn.
Use empty lists when there is nothing to report."""

_FENCE = re.compile(r"`{3}(?:json)?")
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_NOT_WORD = re.compile(r"[^\wäöüß ]")


class ReportFormatError(ValueError):
    """The report model's output could not be parsed into ReportFindings."""


class ErrorFinding(BaseModel):
    turn: int
    original: str
    corrected: str
    category: str
    explanation: str = ""

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        return value if value in CATEGORIES else "Sonstiges"


class PhrasingFinding(BaseModel):
    turn: int
    original: str
    better: str


class EnglishFinding(BaseModel):
    turn: int
    english: str
    german: str


class RescueFinding(BaseModel):
    turn: int
    phrase: str


class ComprehensionFinding(BaseModel):
    turn: int
    score: int
    missed: str = ""


class ReportFindings(BaseModel):
    errors: list[ErrorFinding] = Field(default_factory=list)
    phrasings: list[PhrasingFinding] = Field(default_factory=list)
    english: list[EnglishFinding] = Field(default_factory=list)
    rescue_phrases: list[RescueFinding] = Field(default_factory=list)
    comprehension: list[ComprehensionFinding] = Field(default_factory=list)

    def count(self) -> int:
        return sum(len(getattr(self, name)) for name in type(self).model_fields)


def transcript_lines(turns: Sequence[Turn]) -> str:
    lines = []
    for t in turns:
        tag = "L" if t["speaker"] == "learner" else "P"
        mark = f" {CHECK_MARK}" if t["comprehension_check"] else ""
        lines.append(f"[{tag}{t['turn_index']}]{mark} {t['text']}")
    return "\n".join(lines)


def build_messages(turns: Sequence[Turn]) -> list[dict[str, str]]:
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": transcript_lines(turns)}]


def parse_findings(raw: str) -> ReportFindings:
    match = _OBJECT.search(_FENCE.sub("", raw))
    if not match:
        raise ReportFormatError(f"No JSON object in: {raw[:80]!r}")
    try:
        return ReportFindings.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise ReportFormatError(str(exc)) from exc


def _norm(text: str) -> str:
    return " ".join(_NOT_WORD.sub(" ", text.lower()).split())


def verify_findings(findings: ReportFindings, turns: Sequence[Turn]) -> tuple[ReportFindings, int]:
    """Keep only findings whose quote is in that learner turn: the report never claims words he did not say."""
    learner = {t["turn_index"]: _norm(t["text"]) for t in turns if t["speaker"] == "learner"}

    def said(turn: int, quote: str) -> bool:
        return turn in learner and bool(_norm(quote)) and _norm(quote) in learner[turn]

    kept = ReportFindings(
        errors=[f for f in findings.errors if said(f.turn, f.original)],
        phrasings=[f for f in findings.phrasings if said(f.turn, f.original)],
        english=[f for f in findings.english if said(f.turn, f.english)],
        rescue_phrases=[f for f in findings.rescue_phrases if said(f.turn, f.phrase)],
        comprehension=[f for f in findings.comprehension if f.turn in learner and 0 <= f.score <= 2],
    )
    return kept, findings.count() - kept.count()


def analyze(client: ChatClient, model: str, turns: Sequence[Turn], timeout: float = 90.0) -> ReportFindings:
    return parse_findings(client.complete(model, build_messages(turns), timeout))


def top_errors(errors: Sequence[ErrorFinding], n: int = 3) -> list[tuple[str, list[ErrorFinding]]]:
    """Most frequent error categories first; ties keep the order of first appearance."""
    groups: dict[str, list[ErrorFinding]] = {}
    for error in errors:
        groups.setdefault(error.category, []).append(error)
    return sorted(groups.items(), key=lambda item: -len(item[1]))[:n]
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Lint + commit**

```bash
git add src/self_talk_coach/conversation/report_llm.py tests/conversation/test_report_llm.py
git commit -m "feat(report): report-LLM findings with transcript-verified quotes"
```

---

### Task 5: Vocab miner

**Files:**
- Rewrite: `src/self_talk_coach/mine.py` (currently a 4-line stub)
- Test: `tests/test_mine.py` (create)

**Interfaces:**
- Produces: `Token(lemma, pos, is_stop)`; `Lemmatize = Callable[[str], list[Token]]`; `NewWord(lemma, example)`; `MinerUnavailable(Exception)`; `BASELINE_PATH`; `load_baseline(path=BASELINE_PATH) -> frozenset[str]`; `out_of_baseline_ratio(text, baseline, lemmatize) -> float | None`; `mine_new_words(sources, baseline, known, lemmatize, limit=10) -> list[NewWord]`; `spacy_lemmatizer() -> Lemmatize` (raises `MinerUnavailable`).

- [ ] **Step 1: Write the failing tests** — `tests/test_mine.py`:

```python
import re
from pathlib import Path

from self_talk_coach.mine import Token, load_baseline, mine_new_words, out_of_baseline_ratio

STOP = {"ich", "die", "der", "eine", "und", "in"}


def fake_lemmatize(text: str) -> list[Token]:
    """Every word is a NOUN with itself as lemma; 'Reutlingen' is a proper noun."""
    return [
        Token(w, "PROPN" if w == "Reutlingen" else "NOUN", w.lower() in STOP)
        for w in re.findall(r"\w+", text)
    ]


def test_load_baseline_lowercases_and_skips_blank(tmp_path: Path) -> None:
    path = tmp_path / "b.txt"
    path.write_text("Arbeit\n\nschicht\n", encoding="utf-8")
    assert load_baseline(path) == frozenset({"arbeit", "schicht"})


def test_out_of_baseline_ratio_counts_content_words_only() -> None:
    baseline = frozenset({"arbeit"})
    assert out_of_baseline_ratio("Die Arbeit und die Rückerstattung", baseline, fake_lemmatize) == 0.5
    assert out_of_baseline_ratio("und die", baseline, fake_lemmatize) is None


def test_mine_new_words_skips_baseline_known_propn_and_repeats() -> None:
    words = mine_new_words(
        ["Eine Rückerstattung in Reutlingen", "Die Rückerstattung und der Schichtleiter", "Arbeit Quittung"],
        baseline=frozenset({"arbeit"}),
        known={"quittung"},
        lemmatize=fake_lemmatize,
    )
    assert [(w.lemma, w.example) for w in words] == [
        ("Rückerstattung", "Eine Rückerstattung in Reutlingen"),
        ("Schichtleiter", "Die Rückerstattung und der Schichtleiter"),
    ]
    assert len(mine_new_words(["A B C D"], frozenset(), set(), fake_lemmatize, limit=2)) == 2
```

- [ ] **Step 2: Run, expect FAIL** — `ImportError: cannot import name 'Token'`.

- [ ] **Step 3: Implement** — replace `src/self_talk_coach/mine.py`:

```python
"""Vocab miner: lemmas outside the B1 baseline that the learner has not used himself yet."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parents[2] / "resources" / "baseline-de-b1.txt"
CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})
SPACY_MODEL = "de_core_news_lg"  # ADR 0002


@dataclass(frozen=True)
class Token:
    lemma: str
    pos: str
    is_stop: bool


Lemmatize = Callable[[str], list[Token]]


@dataclass(frozen=True)
class NewWord:
    lemma: str
    example: str  # the sentence it first appeared in


class MinerUnavailable(Exception):
    """The lemmatizer cannot run (spaCy model missing)."""


def load_baseline(path: Path = BASELINE_PATH) -> frozenset[str]:
    return frozenset(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _content(tokens: list[Token]) -> list[Token]:
    return [t for t in tokens if t.pos in CONTENT_POS and not t.is_stop and t.lemma.isalpha()]


def out_of_baseline_ratio(text: str, baseline: frozenset[str], lemmatize: Lemmatize) -> float | None:
    """Share of content lemmas outside the baseline (spec § Metrics: partner level check)."""
    words = _content(lemmatize(text))
    if not words:
        return None
    return round(sum(t.lemma.lower() not in baseline for t in words) / len(words), 2)


def mine_new_words(
    sources: Sequence[str],
    baseline: frozenset[str],
    known: set[str],
    lemmatize: Lemmatize,
    limit: int = 10,
) -> list[NewWord]:
    found: dict[str, NewWord] = {}
    for text in sources:
        for token in _content(lemmatize(text)):
            key = token.lemma.lower()
            if key in baseline or key in known or key in found:
                continue
            found[key] = NewWord(token.lemma, text)
            if len(found) == limit:
                return list(found.values())
    return list(found.values())


def spacy_lemmatizer() -> Lemmatize:
    import spacy

    try:
        nlp = spacy.load(SPACY_MODEL, disable=["parser", "ner"])
    except OSError as exc:
        raise MinerUnavailable(
            f"spaCy-Modell {SPACY_MODEL} fehlt: .venv\\Scripts\\python.exe -m spacy download {SPACY_MODEL}"
        ) from exc

    def lemmatize(text: str) -> list[Token]:
        return [Token(t.lemma_, t.pos_, t.is_stop) for t in nlp(text)]

    return lemmatize
```

- [ ] **Step 4: Run, expect PASS.** Then a positive control against the real model (only if the prerequisite was installed):
`.venv/Scripts/python.exe -c "from self_talk_coach.mine import *; l=spacy_lemmatizer(); print(mine_new_words(['Der Kunde wollte eine Rückerstattung.'], load_baseline(), set(), l))"`
Expected: a list containing `Rückerstattung` (if empty, the baseline or POS filter is wrong — stop and check before Task 6).

- [ ] **Step 5: Lint + commit**

```bash
git add src/self_talk_coach/mine.py tests/test_mine.py
git commit -m "feat(mine): vocab miner and out-of-baseline ratio against the B1 baseline

Closes: vocab-miner"
```

---

### Task 6: Report assembly, Markdown, persistence

**Files:**
- Create: `src/self_talk_coach/conversation/report_render.py`, `src/self_talk_coach/conversation/report.py`
- Test: `tests/conversation/test_report.py` (create)

**Interfaces:**
- Consumes: Tasks 2–5. `MEIN_TAG` comes from Task 8; until then `report.py` defines nothing about it — **Task 6 imports `MEIN_TAG` from `self_talk_coach.conversation.mein_tag`, so create that module here with only the constant** (`MEIN_TAG = "Mein Tag"`); Task 8 adds the rest.
- Produces: `ReportData` dataclass; `render_report(data: ReportData) -> str`; `ReportDeps(conn, paths, client, model, lemmatizer: Callable[[], Lemmatize], baseline: frozenset[str], status=print)`; `build_report(deps, conversation_id) -> str` (writes `report.md`, candidates, status; returns the Markdown).

- [ ] **Step 1: Write the failing tests** — `tests/conversation/test_report.py`:

```python
import json
import re
from pathlib import Path

from self_talk_coach.conversation.report import ReportDeps, build_report
from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_conversation_candidates,
    list_turns,
)
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.mine import MinerUnavailable, Token
from self_talk_coach.paths import AppPaths

FINDINGS = {
    "errors": [{"turn": 1, "original": "einen Frage", "corrected": "eine Frage",
                "category": "Kasus/Artikel", "explanation": "Frage is feminine"}],
    "phrasings": [{"turn": 3, "original": "Ich war im Laden", "better": "Ich war gerade im Laden"}],
    "english": [{"turn": 1, "english": "refund", "german": "Rückerstattung"}],
    "rescue_phrases": [{"turn": 3, "phrase": "Kannst du das nochmal sagen"}],
    "comprehension": [{"turn": 3, "score": 1, "missed": "um acht"}],
}


class FakeClient:
    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def complete(self, model, messages, timeout):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fake_lemmatize(text: str) -> list[Token]:
    return [Token(w, "NOUN", False) for w in re.findall(r"\w+", text)]


def _setup(tmp_path: Path, scenario: str | None = "McDonald's"):
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    cid = insert_conversation(conn, started_at="2026-10-08T10:00:00+00:00", scenario=scenario,
                              stt_model="s", llm_model="l", tts_voice="v")
    insert_turn(conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER, text="Was möchtest du?")
    insert_turn(conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
                text="Ich habe einen Frage zum refund.", freeze_seconds=3.0)
    insert_turn(conn, conversation_id=cid, turn_index=2, speaker=TurnSpeaker.PARTNER,
                text="Ich war um acht im Laden. Erzähl kurz nach.", comprehension_check=True)
    insert_turn(conn, conversation_id=cid, turn_index=3, speaker=TurnSpeaker.LEARNER,
                text="Ich war im Laden. Kannst du das nochmal sagen?", freeze_seconds=5.0)
    finish_conversation(conn, cid, ended_at="2026-10-08T10:05:00+00:00", status=ConversationStatus.COMPLETED)
    return conn, cid


def _deps(conn, tmp_path, client, lemmatizer=lambda: fake_lemmatize):
    status: list[str] = []
    deps = ReportDeps(conn=conn, paths=AppPaths.from_data_root(tmp_path), client=client, model="claude-sonnet-5",
                      lemmatizer=lemmatizer, baseline=frozenset({"laden", "ich", "war"}), status=status.append)
    return deps, status


def test_full_report_written_and_candidates_stored(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)))
    text = build_report(deps, cid)

    assert (tmp_path / "conversations" / f"{cid:04d}" / "report.md").read_text(encoding="utf-8") == text
    for heading in ("## Top-Fehler", "## Besser formulieren", "## Englisch → Deutsch", "## Freeze",
                    "## Hörhilfen", "## Rettungssätze", "## Verständnis-Checks", "## Neue Wörter"):
        assert heading in text
    assert "einen Frage → **eine Frage**" in text
    assert "refund → **Rückerstattung**" in text
    assert "1/2" in text and "um acht" in text
    assert "Rückerstattung" in text.split("## Neue Wörter")[1]
    assert get_conversation(conn, cid)["report_status"] == "done"
    types = [r["candidate_type"] for r in list_conversation_candidates(conn, cid)]
    assert types == ["grammar_correction", "phrase_upgrade", "vocabulary"]
    partner = [t for t in list_turns(conn, cid) if t["speaker"] == "partner"]
    assert all(t["out_of_baseline_ratio"] is not None for t in partner)
    assert status == []


def test_llm_failure_gives_metrics_only_report_and_visible_reason(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    deps, status = _deps(conn, tmp_path, FakeClient(RuntimeError("429 plan expired")))
    text = build_report(deps, cid)
    assert any("Fehleranalyse fehlgeschlagen" in s and "429 plan expired" in s for s in status)
    assert f"stc report {cid}" in text and "## Freeze" in text
    assert get_conversation(conn, cid)["report_status"] == "failed"
    assert list_conversation_candidates(conn, cid) == []


def test_missing_spacy_model_skips_new_words_visibly(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)

    def missing():
        raise MinerUnavailable("spaCy-Modell de_core_news_lg fehlt")

    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)), lemmatizer=missing)
    text = build_report(deps, cid)
    assert any("Neue Wörter übersprungen" in s and "de_core_news_lg" in s for s in status)
    assert "übersprungen" in text.split("## Neue Wörter")[1]


def test_dropped_findings_are_reported(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    invented = {**FINDINGS, "errors": [{"turn": 1, "original": "nie gesagt", "corrected": "x",
                                        "category": "Wortwahl", "explanation": "y"}]}
    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(invented)))
    build_report(deps, cid)
    assert any("1 KI-Fund" in s for s in status)


def test_mein_tag_report_has_no_freeze_section(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path, scenario="Mein Tag")
    deps, _ = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)))
    assert "## Freeze" not in build_report(deps, cid)
```

- [ ] **Step 2: Run, expect FAIL** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`src/self_talk_coach/conversation/mein_tag.py` (constant only for now):

```python
"""Mein Tag: the learner narrates the day, the partner only asks short follow-up questions."""

from __future__ import annotations

MEIN_TAG = "Mein Tag"
```

`src/self_talk_coach/conversation/report_render.py`:

```python
"""Session report as Markdown (German headings; spec § Session report)."""

from __future__ import annotations

from dataclasses import dataclass

from self_talk_coach.conversation.report_llm import ComprehensionFinding, ReportFindings, top_errors
from self_talk_coach.conversation.report_metrics import FreezeTrend, ListeningSummary
from self_talk_coach.mine import NewWord


@dataclass(frozen=True)
class ReportData:
    conversation_id: int
    started_at: str
    scenario: str | None
    mein_tag: bool
    learner_turns: int
    findings: ReportFindings | None  # None = report LLM failed
    analysis_error: str | None
    freeze: FreezeTrend
    freeze_per_question: list[tuple[str, float]]
    listening: ListeningSummary
    missed_rescue: list[str]
    checks: list[tuple[str, str, ComprehensionFinding | None]]  # partner text, learner retell, score
    new_words: list[NewWord] | None  # None = miner skipped
    vocab_error: str | None


def _freeze_line(f: FreezeTrend) -> str:
    if f.current is None:
        return "Keine Freeze-Zeit gemessen."
    line = f"Median {f.current:.1f} s"
    if f.previous is None or f.delta is None:
        return line + " (noch kein Vergleich)."
    sign = "+" if f.delta > 0 else ""
    return line + f", vorher {f.previous:.1f} s (letzte {f.compared} Gespräche) → {sign}{f.delta:.1f} s."


def _or_dash(lines: list[str]) -> list[str]:
    return lines or ["–"]


def render_report(d: ReportData) -> str:
    out = [f"# Gespräch {d.conversation_id} — {d.started_at[:10]} — {d.scenario or 'alle Bereiche'}", ""]
    out.append(f"{d.learner_turns} Antworten, {d.listening.partner_turns} Partner-Turns.")

    out += ["", "## Top-Fehler"]
    if d.findings is None:
        out.append(f"Fehleranalyse fehlgeschlagen ({d.analysis_error}). Wiederholen: `stc report {d.conversation_id}`")
    else:
        groups = top_errors(d.findings.errors)
        if not groups:
            out.append("Keine Fehler gefunden.")
        for category, items in groups:
            out.append(f"- **{category}** ({len(items)}×)")
            out += [f"  - {e.original} → **{e.corrected}** — {e.explanation}" for e in items[:2]]
        out += ["", "## Besser formulieren"]
        out += _or_dash([f"- {p.original} → **{p.better}**" for p in d.findings.phrasings])
        out += ["", "## Englisch → Deutsch"]
        out += _or_dash([f"- {x.english} → **{x.german}**" for x in d.findings.english])

    if not d.mein_tag:
        out += ["", "## Freeze", _freeze_line(d.freeze)]
        out += [f"- {seconds:.1f} s — {question}" for question, seconds in d.freeze_per_question]

    out += ["", "## Hörhilfen",
            f"{d.listening.aids} Hörhilfen bei {d.listening.partner_turns} Partner-Turns ({d.listening.per_turn} pro Turn)."]
    out += [f"- schwer: {sentence}" for sentence in d.listening.hard]

    out += ["", "## Rettungssätze"]
    used = [f"- benutzt: {r.phrase}" for r in d.findings.rescue_phrases] if d.findings else []
    missed = [f"- verpasst (Hilfe kam, kein Rettungssatz): {question}" for question in d.missed_rescue]
    out += _or_dash(used + missed)

    if d.checks:
        out += ["", "## Verständnis-Checks"]
        for partner_text, retell, finding in d.checks:
            score = f"{finding.score}/2" if finding else "–"
            gap = f" — fehlte: {finding.missed}" if finding and finding.missed else ""
            out.append(f"- {score} — Partner: {partner_text} / Du: {retell}{gap}")

    out += ["", "## Neue Wörter"]
    if d.new_words is None:
        out.append(f"übersprungen ({d.vocab_error})")
    else:
        out += _or_dash([f"- **{w.lemma}** — {w.example}" for w in d.new_words])
    return "\n".join(out) + "\n"
```

`src/self_talk_coach/conversation/report.py`:

```python
"""Session report: metrics + report-LLM findings + new words -> report.md, learning_candidates, status."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from self_talk_coach.conversation.mein_tag import MEIN_TAG
from self_talk_coach.conversation.partner import ChatClient
from self_talk_coach.conversation.report_llm import ReportFindings, analyze, verify_findings
from self_talk_coach.conversation.report_metrics import (
    answer_pairs,
    freeze_per_question,
    freeze_trend,
    listening_summary,
    missed_rescue,
)
from self_talk_coach.conversation.report_render import ReportData, render_report
from self_talk_coach.db import (
    get_conversation,
    list_turns,
    previous_conversations,
    replace_conversation_candidates,
    set_report_status,
    update_turn_out_of_baseline,
)
from self_talk_coach.domain import CandidateType, NewCandidate, ReportStatus
from self_talk_coach.mine import Lemmatize, MinerUnavailable, NewWord, mine_new_words, out_of_baseline_ratio
from self_talk_coach.paths import AppPaths

Turn = Mapping[str, Any]


@dataclass
class ReportDeps:
    conn: sqlite3.Connection
    paths: AppPaths
    client: ChatClient
    model: str
    lemmatizer: Callable[[], Lemmatize]  # factory: spaCy loads only when a report runs
    baseline: frozenset[str]
    status: Callable[[str], None] = print


def build_report(deps: ReportDeps, conversation_id: int) -> str:
    conv = get_conversation(deps.conn, conversation_id)
    if conv is None:
        raise ValueError(f"Kein Gespräch {conversation_id}")
    turns = list_turns(deps.conn, conversation_id)
    mein_tag = conv["scenario"] == MEIN_TAG

    findings, analysis_error = _findings(deps, turns)
    new_words, vocab_error = _new_words(deps, turns, findings)
    previous = [
        list_turns(deps.conn, c["id"])
        for c in previous_conversations(deps.conn, conversation_id, exclude_scenario=MEIN_TAG)
    ]
    rescue_turns = {r.turn for r in findings.rescue_phrases} if findings else set()
    data = ReportData(
        conversation_id=conversation_id,
        started_at=conv["started_at"],
        scenario=conv["scenario"],
        mein_tag=mein_tag,
        learner_turns=sum(t["speaker"] == "learner" for t in turns),
        findings=findings,
        analysis_error=analysis_error,
        freeze=freeze_trend(turns, previous),
        freeze_per_question=freeze_per_question(turns),
        listening=listening_summary(turns),
        missed_rescue=missed_rescue(turns, rescue_turns),
        checks=_checks(turns, findings),
        new_words=new_words,
        vocab_error=vocab_error,
    )
    if findings is not None:
        replace_conversation_candidates(deps.conn, conversation_id, _candidates(findings, turns))
    text = render_report(data)
    path = deps.paths.conversation_dir(conversation_id) / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    set_report_status(deps.conn, conversation_id, ReportStatus.FAILED if analysis_error else ReportStatus.DONE)
    return text


def _findings(deps: ReportDeps, turns: Sequence[Turn]) -> tuple[ReportFindings | None, str | None]:
    try:
        raw = analyze(deps.client, deps.model, turns)
    except Exception as exc:  # noqa: BLE001 — any failure: numbers-only report with a visible reason
        reason = f"{type(exc).__name__}: {str(exc)[:160]}"
        deps.status(f"[Hinweis] Fehleranalyse fehlgeschlagen, Bericht nur mit Zahlen. Grund: {reason}")
        return None, reason
    findings, dropped = verify_findings(raw, turns)
    if dropped:
        deps.status(f"[Hinweis] {dropped} KI-Fund(e) verworfen: Zitat steht nicht im Transkript.")
    return findings, None


def _new_words(
    deps: ReportDeps, turns: Sequence[Turn], findings: ReportFindings | None
) -> tuple[list[NewWord] | None, str | None]:
    try:
        lemmatize = deps.lemmatizer()
    except MinerUnavailable as exc:
        deps.status(f"[Hinweis] Neue Wörter übersprungen. Grund: {exc}")
        return None, str(exc)
    partner = [t for t in turns if t["speaker"] == "partner"]
    for turn in partner:
        update_turn_out_of_baseline(deps.conn, turn["id"], out_of_baseline_ratio(turn["text"], deps.baseline, lemmatize))
    known = {tok.lemma.lower() for t in turns if t["speaker"] == "learner" for tok in lemmatize(t["text"])}
    english = [x.german for x in findings.english] if findings else []
    return mine_new_words(english + [t["text"] for t in partner], deps.baseline, known, lemmatize), None


def _checks(turns: Sequence[Turn], findings: ReportFindings | None) -> list:
    scores = {c.turn: c for c in findings.comprehension} if findings else {}
    return [
        (p["text"], a["text"], scores.get(a["turn_index"]))
        for p, a in answer_pairs(turns)
        if p["comprehension_check"]
    ]


def _candidates(findings: ReportFindings, turns: Sequence[Turn]) -> list[NewCandidate]:
    ids = {t["turn_index"]: t["id"] for t in turns}
    out = [
        NewCandidate(ids[e.turn], CandidateType.GRAMMAR_CORRECTION, e.original, e.corrected,
                     f"{e.category}: {e.explanation}")
        for e in findings.errors
    ]
    out += [NewCandidate(ids[p.turn], CandidateType.PHRASE_UPGRADE, p.original, p.better, "natürlicher")
            for p in findings.phrasings]
    out += [NewCandidate(ids[x.turn], CandidateType.VOCABULARY, x.english, x.german, "Englisch → Deutsch")
            for x in findings.english]
    return out
```

Note: in the test the learner text "Ich habe einen Frage zum refund." lemmatizes (fake) to words incl. "refund"; "Rückerstattung" comes from `english[].german` and is not in the learner's known words, so it is listed first under "Neue Wörter".

- [ ] **Step 4: Run, expect PASS** — `pytest ... tests/conversation/test_report.py`, then the full suite.

- [ ] **Step 5: Lint + commit**

```bash
git add src/self_talk_coach/conversation/report.py src/self_talk_coach/conversation/report_render.py src/self_talk_coach/conversation/mein_tag.py tests/conversation/test_report.py
git commit -m "feat(report): session report with verified findings, metrics, new words

Closes: report-rescue-phrases"
```

---

### Task 7: `stc report <id>` + auto-report after `stc talk`

**Files:**
- Modify: `src/self_talk_coach/cli.py`
- Test: `tests/conversation/test_talk_summary.py`

**Interfaces:**
- Consumes: `ReportDeps`, `build_report` (Task 6); `TalkConfig.report_model` (Task 1); `load_baseline`, `spacy_lemmatizer` (Task 5).
- Produces: `report_deps(conn, paths, cfg, status=typer.echo) -> ReportDeps`; command `stc report CONVERSATION_ID [--data-root]`; `REPORT_MAX_TOKENS = 3000`.

- [ ] **Step 1: Write the failing test** — append to `tests/conversation/test_talk_summary.py`:

```python
def test_report_command_is_registered_and_reports_unknown_id(tmp_path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from self_talk_coach.cli import app

    for name, value in {"DEEPGRAM_API_KEY": "d", "GATEWAY_BASE_URL": "https://gw.example/v1",
                        "GATEWAY_API_KEY": "g", "STC_QUESTION_BANKS": "x.md"}.items():
        monkeypatch.setenv(name, value)
    result = CliRunner().invoke(app, ["report", "999", "--data-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "Kein Gespräch 999" in result.output
```

- [ ] **Step 2: Run, expect FAIL** — `No such command 'report'`.

- [ ] **Step 3: Implement** — in `cli.py`:

```python
REPORT_MAX_TOKENS = 3000


def report_deps(conn, paths: AppPaths, cfg, status=typer.echo):
    from self_talk_coach.conversation.partner import OpenAIChatClient
    from self_talk_coach.conversation.report import ReportDeps
    from self_talk_coach.mine import load_baseline, spacy_lemmatizer

    return ReportDeps(
        conn=conn,
        paths=paths,
        client=OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key,
                                max_tokens=REPORT_MAX_TOKENS, temperature=0.2),
        model=cfg.report_model,
        lemmatizer=spacy_lemmatizer,
        baseline=load_baseline(),
        status=status,
    )


@app.command("report")
def report_command(
    conversation_id: Annotated[int, typer.Argument(help="Conversation id (printed after stc talk).")],
    data_root: Annotated[
        Path, typer.Option("--data-root", help="Application data root.")
    ] = Path("data"),
) -> None:
    """Build (or rebuild) the session report of one conversation."""
    import os

    from dotenv import load_dotenv

    from self_talk_coach.conversation.config import ConfigError, TalkConfig
    from self_talk_coach.conversation.report import build_report

    load_dotenv()
    try:
        cfg = TalkConfig.from_env(os.environ)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    paths = AppPaths.from_data_root(data_root)
    paths.ensure_workspace()
    with connect(paths.db_path) as conn:
        init_db(conn)
        try:
            typer.echo(build_report(report_deps(conn, paths, cfg), conversation_id))
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
```

At the end of `talk_command`, inside the `with connect(...)` block after `turns = list_turns(conn, cid)` and the summary echo, add:

```python
        if any(t["speaker"] == "learner" for t in turns):
            typer.echo("[Bericht] wird erstellt …")
            typer.echo(build_report(report_deps(conn, paths, cfg), cid))
        else:
            typer.echo("Kein Bericht: keine Antwort aufgenommen.")
```

(move the summary echo into the `with` block and import `build_report` inside `talk_command`). `CliRunner` mixes stderr into `output` by default in the installed Typer; if the assertion fails on that, use `result.stderr`.

- [ ] **Step 4: Run, expect PASS** — the new test and the full suite.

- [ ] **Step 5: Real check against stored data** (gateway call, ~10–20 s, Sonnet 5):

```
.\.venv\Scripts\stc.exe report 10
```

Expected: Markdown printed, `data/conversations/0010/report.md` exists, no `[Hinweis]` line except the spaCy one if the model is not installed. Read the "Top-Fehler" section against the turn texts in the DB (e.g. turn 7 "Deutsch UBEN"): every quoted original must be in the transcript. Paste the report into the session for the user.

- [ ] **Step 6: Lint + commit**

```bash
git add src/self_talk_coach/cli.py tests/conversation/test_talk_summary.py
git commit -m "feat(cli): stc report <id>, report runs after every talk"
```

---

### Task 8: Comprehension check every 4th partner turn

**Files:**
- Modify: `src/self_talk_coach/conversation/partner.py`, `src/self_talk_coach/conversation/session.py`
- Test: `tests/conversation/test_partner.py`, `tests/conversation/test_session.py`

**Interfaces:**
- Produces: `Partner.respond(learner_text, seed, section="", phrase=False, comprehension=False)`; `COMPREHENSION_IMPULSE`; `SessionDeps.comprehension_every: int = 4` (0 = off); `SessionDeps.max_record_seconds: float = MAX_RECORD_SECONDS`. The partner turn row gets `comprehension_check=1`.

- [ ] **Step 1: Write the failing tests**

`test_partner.py`:

```python
def test_comprehension_impulse_replaces_seed() -> None:
    from self_talk_coach.conversation.partner import COMPREHENSION_IMPULSE

    client = FakeClient({"p": [json.dumps(GOOD)], "f": []})
    Partner(client, "p", "f", "SYS").respond("Ich arbeite.", "Hobbys?", section="S", comprehension=True)
    content = client.calls[0][1][-1]["content"]
    assert COMPREHENSION_IMPULSE in content and "Hobbys?" not in content
```

`test_session.py` — first update `FakePartner.respond` to accept and record the flag:

```python
    def respond(self, learner_text: str, seed: str, section: str = "", phrase: bool = False,
                comprehension: bool = False) -> PartnerReply:
        self.learner_texts.append(learner_text)
        self.sections.append(section)
        self.phrases.append(phrase)
        self.checks.append(comprehension)
        return self._next()
```

(and `self.checks: list[bool] = []` in `__init__`). Then add:

```python
def test_every_fourth_partner_turn_is_a_comprehension_check(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (2.0, " "), (3.0, " "), (4.0, " "), (5.0, " "), (6.0, " "), (7.0, "q")],
        recordings=[1.0, 1.0, 1.0],
        texts=["Eins.", "Zwei.", "Drei."],
        replies=[_reply("A?"), _reply("B?"), _reply("C?"), _reply("Ich war um acht da. Erzähl kurz nach.")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert deps.partner.checks == [False, False, True]
    partner_rows = [t for t in list_turns(conn, cid) if t["speaker"] == "partner"]
    assert [t["comprehension_check"] for t in partner_rows] == [0, 0, 0, 1]


def test_comprehension_check_off_when_every_is_zero(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (2.0, " "), (3.0, " "), (4.0, " "), (5.0, " "), (6.0, " "), (7.0, "q")],
        recordings=[1.0, 1.0, 1.0],
        texts=["Eins.", "Zwei.", "Drei."],
        replies=[_reply("A?"), _reply("B?"), _reply("C?"), _reply("D?")],
    )
    deps.comprehension_every = 0
    ConversationSession(deps, scenario=None, llm_label="x").run()
    assert deps.partner.checks == [False, False, False]


def test_record_limit_comes_from_deps(tmp_path: Path) -> None:
    deps, _, _, _, _ = _deps(
        tmp_path, keys_script=[(1.0, " "), (100.0, " "), (101.0, "q")],
        recordings=[99.0], texts=["Heute war viel los."], replies=[_reply("Und?"), _reply("Und dann?")],
    )
    stops: list[float] = []
    original_stop = deps.recorder.stop

    def stop():
        stops.append(deps.clock.now())
        return original_stop()

    deps.recorder.stop = stop
    deps.max_record_seconds = 180.0
    ConversationSession(deps, scenario=None, llm_label="x").run()
    assert stops and stops[0] >= 100.0  # default 60 s would have cut at 61 s
```

- [ ] **Step 2: Run, expect FAIL** — `ImportError: COMPREHENSION_IMPULSE`, `unexpected keyword argument 'comprehension_every'` / no `checks`.

- [ ] **Step 3: Implement**

`partner.py`:

```python
COMPREHENSION_IMPULSE = (
    "Verständnis-Check: Stell jetzt keine neue Frage. Erzähl in 2–3 kurzen Sätzen (B1) etwas aus deiner Rolle "
    "oder zum Thema, mit zwei konkreten Details (z. B. Uhrzeit, Ort, Zahl, Name). "
    "Ende mit: \"Erzähl kurz nach, was ich gerade gesagt habe.\" recast null. "
    "starter_phrase: \"Du hast gesagt, dass …\""
)
```

```python
    def respond(
        self, learner_text: str, seed: str, section: str = "", phrase: bool = False, comprehension: bool = False
    ) -> PartnerReply:
        impulse = COMPREHENSION_IMPULSE if comprehension else _impulse(seed, section, phrase)
        return self._turn(f"Lerner: {learner_text}\n{impulse}")
```

`session.py`:
- Constants: `COMPREHENSION_EVERY = 4` next to `MAX_RECORD_SECONDS`.
- `SessionDeps` (append after `status`): `max_record_seconds: float = MAX_RECORD_SECONDS` and `comprehension_every: int = COMPREHENSION_EVERY`.
- `_State`: add `partner_turns: int = 0` and `check: bool = False`.
- `_partner_turn`:

```python
    def _partner_turn(self, *, opening: bool, learner_text: str) -> None:
        picked = self._d.picker.next()
        seed = picked.text
        every = self._d.comprehension_every
        check = not opening and every > 0 and (self._s.partner_turns + 1) % every == 0
        try:
            if opening:
                reply = self._d.partner.opening(seed, section=picked.section, phrase=picked.phrase)
            else:
                reply = self._d.partner.respond(
                    learner_text, seed, section=picked.section, phrase=picked.phrase, comprehension=check
                )
        except PartnerUnavailable as exc:
            self._d.status(f"[Hinweis] KI-Partner nicht erreichbar, ich lese die Frage aus der Liste vor. Grund: {str(exc)[:160]}")
            reply = fallback_reply(seed)
            check = False
        self._s.partner_turns += 1
        self._s.check = check
        self._s.seed_text = seed
        self._s.reply = reply
        self._s.audio = self._d.voice.synthesize(reply.turn.spoken_text())
```

- `_speak_and_store_partner`: pass `comprehension_check=s.check` to `insert_turn`.
- `_record_and_transcribe`: replace `MAX_RECORD_SECONDS` with `d.max_record_seconds`.

- [ ] **Step 4: Run, expect PASS** — full suite (existing session tests must stay green with the new FakePartner signature).

- [ ] **Step 5: Real-LLM check** — extend `scripts/spikes/s5_partner_prompt.py` only if it has a case table; otherwise one manual probe:
`.venv/Scripts/python.exe -c` script that builds `Partner` from `.env` and calls `respond("Ich arbeite bei McDonald's.", "x", comprehension=True)` 3 times; print `spoken_text()`. Expected: 2–3 sentences with two concrete details, ends with the retell request, no recast. Record the 3 outputs in the commit body.

- [ ] **Step 6: Lint + commit**

```bash
git add src/self_talk_coach/conversation/partner.py src/self_talk_coach/conversation/session.py tests/conversation/test_partner.py tests/conversation/test_session.py
git commit -m "feat(talk): comprehension check every 4th partner turn; record limit per session"
```

---

### Task 9: "Mein Tag" mode

**Files:**
- Modify: `src/self_talk_coach/conversation/mein_tag.py`, `src/self_talk_coach/conversation/partner.py`, `src/self_talk_coach/conversation/question_bank.py`, `src/self_talk_coach/conversation/session.py` (type hint only), `src/self_talk_coach/cli.py`
- Test: `tests/conversation/test_mein_tag.py` (create), `tests/conversation/test_partner.py`, `tests/conversation/test_talk_summary.py`

**Interfaces:**
- Consumes: `SessionDeps.max_record_seconds`, `SessionDeps.comprehension_every` (Task 8); `TalkConfig.mein_tag_ladder` (Task 1).
- Produces: `MeinTagDeck` (`label`, `next()`, `options()`, `current_option`, `choose()`, `switch()`), `MEIN_TAG_MAX_RECORD_SECONDS = 180.0`; `Deck` Protocol in `question_bank.py`; `build_mein_tag_prompt(profile) -> str`; `Partner(..., drop_recast: bool = False)`; `stc talk --mein-tag`; start menu answer `m` returns `MEIN_TAG`.

- [ ] **Step 1: Write the failing tests**

`tests/conversation/test_mein_tag.py`:

```python
from self_talk_coach.conversation.mein_tag import MEIN_TAG, MeinTagDeck


def test_deck_opens_once_then_only_follow_ups() -> None:
    deck = MeinTagDeck()
    first, second, third = deck.next(), deck.next(), deck.next()
    assert first.section == MEIN_TAG and "Tag" in first.text
    assert second == third and "Folgefrage" in second.text
    assert deck.options() == [MEIN_TAG] and deck.label == MEIN_TAG
    assert deck.switch() == MEIN_TAG and deck.choose(0) == MEIN_TAG
```

`test_partner.py`:

```python
def test_drop_recast_removes_recast_from_spoken_text() -> None:
    client = FakeClient({"p": [json.dumps(GOOD)], "f": []})
    reply = Partner(client, "p", "f", "SYS", drop_recast=True).respond("Ich war müde.", "x")
    assert reply.turn.recast is None
    assert reply.turn.spoken_text() == GOOD["reply"]


def test_mein_tag_prompt_rules() -> None:
    from self_talk_coach.conversation.partner import build_mein_tag_prompt

    prompt = build_mein_tag_prompt("Wohnt in Reutlingen.")
    assert "Rückerstattung" in prompt  # English word taken up in German
    assert "recast" in prompt and "immer null" in prompt
    assert prompt.rstrip().endswith("Wohnt in Reutlingen.")
```

`test_talk_summary.py`:

```python
def test_start_menu_m_picks_mein_tag_and_leaves_deck_alone() -> None:
    import random

    from self_talk_coach.cli import choose_start_scenario
    from self_talk_coach.conversation.mein_tag import MEIN_TAG
    from self_talk_coach.conversation.question_bank import ScenarioDeck, Seed

    shown: list[str] = []
    deck = ScenarioDeck([Seed("A", "a")], None, random.Random(0))
    assert choose_start_scenario(deck, lambda _: "m", shown.append) == MEIN_TAG
    assert any("Mein Tag" in line for line in shown)
    assert deck.label == ScenarioDeck.MIXED
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

`mein_tag.py` (extend):

```python
from self_talk_coach.conversation.question_bank import Seed

MEIN_TAG = "Mein Tag"
MEIN_TAG_MAX_RECORD_SECONDS = 180.0  # the learner narrates; one turn may be long
OPENING = Seed(MEIN_TAG, "Wie war dein Tag heute? Erzähl mal.")
FOLLOW_UP = Seed(MEIN_TAG, "Kurze Folgefrage zu dem, was er gerade erzählt hat. Kein neues Thema.")


class MeinTagDeck:
    """Seeds for Mein Tag: one opening, then always a follow-up impulse. No scenarios to switch to."""

    label = MEIN_TAG
    current_option = 0

    def __init__(self) -> None:
        self._opened = False

    def next(self) -> Seed:
        if self._opened:
            return FOLLOW_UP
        self._opened = True
        return OPENING

    def options(self) -> list[str]:
        return [MEIN_TAG]

    def choose(self, option: int) -> str:
        return MEIN_TAG

    def switch(self) -> str:
        return MEIN_TAG
```

`question_bank.py` — add (and `from typing import Protocol`):

```python
class Deck(Protocol):
    label: str

    def next(self) -> Seed: ...
    def options(self) -> list[str]: ...
    @property
    def current_option(self) -> int: ...
    def choose(self, option: int) -> str: ...
    def switch(self) -> str: ...
```

`session.py`: `picker: Deck` instead of `picker: ScenarioDeck` (import `Deck`).

`partner.py`:

```python
_MEIN_TAG_TEMPLATE = """Du bist ein guter Freund aus Baden-Württemberg. Der Lerner (Deutsch B1) erzählt dir von seinem Tag.
Regeln:
- Du hörst zu. "reply": genau EINE kurze Folgefrage (höchstens 12 Wörter) zu dem, was er gerade erzählt hat.
  Kein neues Thema, keine eigene Geschichte, kein Lob.
- Keine Korrekturen: "recast" ist immer null.
- Benutzt der Lerner englische Wörter, nimm in deiner Folgefrage das deutsche Wort auf.
  Beispiel: Lerner "Der Kunde wollte einen refund." → reply "Eine Rückerstattung? Und hat er sie bekommen?"
- Erfinde nie, was der Lerner gesagt hat.
- Bittet er um Wiederholung ("Wie bitte?"): stell deine letzte Frage noch einmal, einfacher.
- "starter_phrase": ein Satzanfang, mit dem er weitererzählen kann (z. B. "Danach bin ich …").
- "simpler_rephrase": deine Frage einfacher. "topic_jump": false.
Antworte NUR mit JSON: {{"reply": str, "recast": null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": false}}
{profile_block}"""


def _profile_block(profile: str | None) -> str:
    return f"\nÜber den Lerner:\n{profile.strip()}" if profile and profile.strip() else ""


def build_system_prompt(profile: str | None) -> str:
    return _SYSTEM_TEMPLATE.format(profile_block=_profile_block(profile))


def build_mein_tag_prompt(profile: str | None) -> str:
    return _MEIN_TAG_TEMPLATE.format(profile_block=_profile_block(profile))
```

`Partner.__init__` gains `drop_recast: bool = False` (stored as `self._drop_recast`); in `_turn`, right after `turn = parse_partner_turn(raw)`:

```python
                if self._drop_recast and turn.recast:
                    turn = turn.model_copy(update={"recast": None})  # Mein Tag: no corrections while he talks
```

`cli.py`:
- `talk_command` gets `mein_tag: Annotated[bool, typer.Option("--mein-tag", help="Talk freely about your day; partner only asks follow-ups.")] = False`.
- `choose_start_scenario`: before the loop `echo("   m  Mein Tag (frei erzählen)")`; inside the loop, before the digit check:

```python
        if answer.lower() == "m":
            return MEIN_TAG
```

- In `talk_command`, choose the mode before building the partner:

```python
    if mein_tag:
        label = MEIN_TAG
    elif scenario is None:
        label = choose_start_scenario(deck, input, typer.echo)
    else:
        label = deck.label
    is_mein_tag = label == MEIN_TAG
    partner = Partner(
        OpenAIChatClient(cfg.gateway_base_url, cfg.gateway_api_key),
        cfg.partner_model,
        cfg.fallback_model,
        build_mein_tag_prompt(profile) if is_mein_tag else build_system_prompt(profile),
        drop_recast=is_mein_tag,
    )
    picker = MeinTagDeck() if is_mein_tag else deck
    typer.echo(f"Szenario: {picker.label}")
```

and in `SessionDeps(...)`: `picker=picker`, `ladder=cfg.mein_tag_ladder if is_mein_tag else cfg.ladder`, `max_record_seconds=MEIN_TAG_MAX_RECORD_SECONDS if is_mein_tag else MAX_RECORD_SECONDS`, `comprehension_every=0 if is_mein_tag else COMPREHENSION_EVERY`; `ConversationSession(deps, scenario=picker.label, ...)`. Imports: `MEIN_TAG, MEIN_TAG_MAX_RECORD_SECONDS, MeinTagDeck` from `mein_tag`, `MAX_RECORD_SECONDS, COMPREHENSION_EVERY` from `session`, `build_mein_tag_prompt` from `partner`. `MEIN_TAG` is needed at module level by `choose_start_scenario` — import it at the top of `cli.py` (`mein_tag.py` only imports `question_bank`, so it stays cheap).

Known limit (documented, not fixed): `w`/`f` in Mein Tag reset the partner's memory and reopen ("Wie war dein Tag?") because `MeinTagDeck.switch()` is a no-op label; the key hint stays the same. Fix only if it bites in use.

- [ ] **Step 4: Run, expect PASS** — full suite.

- [ ] **Step 5: Real-LLM check** — 3 probes of `Partner(..., build_mein_tag_prompt(None), drop_recast=True).respond("Heute ich habe am Counter gearbeitet und es war really stressful.", FOLLOW_UP.text, section=MEIN_TAG)`. Expected each time: one question ≤ 12 words, German word for "stressful" taken up (e.g. "stressig"), no correction of "Heute ich habe". Record outputs in the commit body.

- [ ] **Step 6: Lint + commit**

```bash
git add src/self_talk_coach/conversation/mein_tag.py src/self_talk_coach/conversation/partner.py src/self_talk_coach/conversation/question_bank.py src/self_talk_coach/conversation/session.py src/self_talk_coach/cli.py tests/conversation/test_mein_tag.py tests/conversation/test_partner.py tests/conversation/test_talk_summary.py
git commit -m "feat(talk): Mein Tag mode - follow-up-only partner, 15 s ladder, long turns

Closes: mein-tag-mode"
```

---

### Task 10: Docs — ADR 0006, spec, glossary, backlog, env example

**Files:**
- Create: `docs/adr/0006-one-report-llm-call-with-verified-quotes.md`
- Modify: `docs/exec-plans/active/2026-10-04-conversation-partner-design.md`, `CONTEXT.md`, `BACKLOG.md`, `.env.example`

- [ ] **Step 1: ADR 0006** (one paragraph, same style as ADR 0005):

```markdown
# ADR 0006 – One report-LLM call per conversation, quotes verified in code

**Status:** Accepted
**Date:** 2026-10-08

The session report gets mistakes, better phrasings, English→German, rescue phrases and retell scores from a single report-LLM call per conversation (Sonnet 5 via the gateway, JSON), while freeze times, listening aids and missed rescue chances are computed in code from `turns`. One call sees the whole conversation, so recurring errors can be grouped and retellings judged against the partner's real text; per-turn calls would cost ~N× and lose that context. The risk is the model "finding" errors the learner never made, which would break the promise of ADR 0005; so code keeps a finding only if its quoted fragment is in that learner turn's stored transcript, and every drop is shown as a status line. Error categories are a fixed list (unknown → "Sonstiges") so "top 3" counts stay stable. If the call fails, the report still renders the numbers, `report_status='failed'`, and `stc report <id>` reruns it.
```

- [ ] **Step 2: Spec** — in § Session report replace the bullet "For interview seeds: …" with "For interview seeds: the learner's own model answer — deferred until `interview-questionnaire-format`"; add a paragraph "Phase 2 (2026-10-08)": report built by `conversation/report.py` (ADR 0006), Mein Tag mode (`stc talk --mein-tag` or `m` in the start menu: follow-up-only partner, ladder 15/25/35 s, 180 s turns, no recast, no comprehension check, English words taken up in German), comprehension check = partner tells 2–3 sentences with two details every 4th partner turn, scored 0–2 in the report. Configuration line gains `STC_MEIN_TAG_LADDER_SECONDS=15,25,35`. Bump **Last verified** to the commit date.

- [ ] **Step 3: CONTEXT.md** — under Conversation terms add:
  - `**Mein Tag** – Conversation mode where the learner narrates his day (German, some English) and the partner only asks short follow-up questions; no corrections during the talk, all in the session report. _Avoid_: diary mode, Tagebuch (that is the separate written /tagebuch practice).`
  - `**comprehension check** – Every 4th partner turn in a scenario conversation: the partner tells 2–3 sentences with two concrete details and asks the learner to retell them; the report scores the retelling 0–2.`

- [ ] **Step 4: BACKLOG.md** — move `vocab-miner`, `mein-tag-mode`, `report-rescue-phrases` to Done with their SHAs; add under S3: `mein-tag-switch-keys - In Mein Tag, w/f reset the partner's memory and reopen; disable or hide them in that mode if it bites.`

- [ ] **Step 5: `.env.example`** — add `# STC_REPORT_MODEL=claude-sonnet-5` and `# STC_MEIN_TAG_LADDER_SECONDS=15,25,35` next to the other optional lines.

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0006-one-report-llm-call-with-verified-quotes.md docs/exec-plans/active/2026-10-04-conversation-partner-design.md CONTEXT.md BACKLOG.md .env.example
git commit -m "docs: ADR 0006 report LLM, Mein Tag + comprehension check in spec and glossary"
```

---

### Task 11: Live verification with the learner (manual)

- [ ] **Step 1:** `stc report 3` and `stc report 10` on the real stored conversations. Agent reads each "Top-Fehler" quote against the DB text; learner reads the report and says whether the corrections and phrasings are right and useful.
- [ ] **Step 2:** Learner runs one scenario conversation of ≥ 9 partner turns (`.\.venv\Scripts\stc.exe talk` → 6 or 7, McDonald's). Check: partner turns 4 and 8 are comprehension checks; the report appears at the end; the checks section shows two scores.
- [ ] **Step 3:** Learner runs `.\.venv\Scripts\stc.exe talk --mein-tag` for ~5 minutes with some English. Check: no corrections spoken, follow-ups short, English words come back in German, ladder only after ~15 s, report has no Freeze section and lists English → Deutsch.
- [ ] **Step 4:** Record results in the spec ("Phase 2 first runs" paragraph), move this plan to `docs/exec-plans/completed/`, set **Status:** done, commit.

---

## Self-review (2026-10-08)

- Spec § Session report coverage: top errors ✓ (T4, T6), freeze per question + median + vs last 5 ✓ (T3), ladder steps / rescue used + missed ✓ (T3, T4), listening aids + hard sentences ✓ (T3), comprehension accuracy ✓ (T4, T8), new words ✓ (T5), interview model answers — explicitly deferred (needs parser), `report.md` + printed ✓ (T6, T7), `learning_candidates` with `turn_id` ✓ (T2, T6), `report_status` + rerun ✓ (T2, T6, T7). Data flow 5 (comprehension every 4th turn) ✓ (T8). Metrics `out_of_baseline_ratio` ✓ (T5, T6).
- User asks this session: Mein Tag with ~15 s ladder, no live corrections, English taken up in German, English→German in report ✓ (T9, T4, T6).
- Names cross-checked: `ReportFindings.rescue_phrases`, `ComprehensionFinding.turn` (= learner `turn_index`), `NewCandidate` field order, `SessionDeps.comprehension_every` / `max_record_seconds`, `MEIN_TAG` created in T6 and extended in T9.
- Open risks: gateway Sonnet 5 availability on report day (fallback = numbers-only report, visible); `de_core_news_lg` install is the user's step; `CliRunner` stderr handling may need `result.stderr` (noted in T7).
