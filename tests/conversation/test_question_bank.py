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
