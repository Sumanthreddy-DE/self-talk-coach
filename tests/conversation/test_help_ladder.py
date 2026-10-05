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
