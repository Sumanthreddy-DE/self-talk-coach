"""Question banks: Markdown files of numbered questions grouped under '## ' sections."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

_ITEM = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")


@dataclass(frozen=True)
class Seed:
    section: str
    text: str
    phrase: bool = False  # a sentence the learner should say, not a question for the learner


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


def mark_phrase_sections(seeds: Sequence[Seed], section_names: Sequence[str]) -> list[Seed]:
    """Flag seeds whose section name contains one of `section_names` (case-insensitive)."""
    wanted = [name.lower() for name in section_names]
    return [replace(s, phrase=any(w in s.section.lower() for w in wanted)) for s in seeds]


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
    """Random seeds without repeats until every seed was used once, then a fresh shuffle."""

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
