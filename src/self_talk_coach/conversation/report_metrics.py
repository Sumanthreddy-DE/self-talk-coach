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
