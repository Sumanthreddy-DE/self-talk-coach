import pytest

from self_talk_coach.cli import median_freeze


def test_median_freeze_averages_middle_pair_for_even_count() -> None:
    turns = [{"freeze_seconds": 1.26}, {"freeze_seconds": None}, {"freeze_seconds": 22.75}]
    assert median_freeze(turns) == pytest.approx(12.005)


def test_median_freeze_odd_count_and_empty() -> None:
    assert median_freeze([{"freeze_seconds": s} for s in (5.0, 1.0, 3.0)]) == 3.0
    assert median_freeze([{"freeze_seconds": None}]) is None
