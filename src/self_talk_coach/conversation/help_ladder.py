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
