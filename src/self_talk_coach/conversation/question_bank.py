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


class ScenarioDeck:
    """Seeds for the current scenario; `switch()` moves on to the next bank section (key 'w').

    Starts with all sections mixed (no scenario) or with the sections matching `scenario`.
    Switching steps through single sections in bank order and wraps around.
    """

    MIXED = "alle Bereiche"

    def __init__(self, seeds: Sequence[Seed], scenario: str | None, rng: random.Random) -> None:
        chosen = filter_scenario(seeds, scenario)
        self._seeds = list(seeds)
        self._sections = list(dict.fromkeys(s.section for s in seeds))
        self._rng = rng
        matched = list(dict.fromkeys(s.section for s in chosen))
        if scenario is None:
            self._index, self.label = -1, self.MIXED
        else:
            self._index = self._sections.index(matched[-1])
            self.label = matched[0] if len(matched) == 1 else scenario
        self._picker = SeedPicker(chosen, rng)

    def next(self) -> Seed:
        return self._picker.next()

    def options(self) -> list[str]:
        """Menu entries: 0 = all sections mixed, then each section in bank order."""
        return [self.MIXED, *self._sections]

    @property
    def current_option(self) -> int:
        return self._index + 1

    def choose(self, option: int) -> str:
        if option == 0:
            self._index, self.label = -1, self.MIXED
            self._picker = SeedPicker(self._seeds, self._rng)
            return self.label
        self._index = option - 1
        self.label = self._sections[self._index]
        self._picker = SeedPicker([s for s in self._seeds if s.section == self.label], self._rng)
        return self.label

    def switch(self) -> str:
        return self.choose((self._index + 1) % len(self._sections) + 1)


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
