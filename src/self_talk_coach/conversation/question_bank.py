"""Question banks: numbered lists or interview questionnaires with model answers."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import groupby
from pathlib import Path
from typing import Protocol

_ITEM = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_GROUP = re.compile(r"^# \d+[a-z]?\. (.*)", re.MULTILINE)
_QUESTION = re.compile(r"^## \d+[a-z]?\.\d+[a-z]? (.*)", re.MULTILINE)


@dataclass(frozen=True)
class Seed:
    section: str
    text: str
    phrase: bool = False  # a sentence the learner should say, not a question for the learner
    model_answer: str | None = None


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


def _questionnaire_section(section: str, lines: list[str]) -> list[Seed]:
    questions: list[tuple[str, str, str]] = []
    index = 0
    while index < len(lines):
        match = _QUESTION.match(lines[index])
        index += 1
        if not match:
            continue
        text, _, variant = match.group(1).lstrip("★ ").partition(" — ")
        answer: list[str] = []
        while index < len(lines) and not lines[index].startswith(("---", "## ", "# ")):
            if not lines[index].startswith(">"):
                answer.append(lines[index])
            index += 1
        while answer and not answer[0].strip():
            answer.pop(0)
        while answer and not answer[-1].strip():
            answer.pop()
        questions.append((text.strip(), variant, "\n".join(answer)))

    seeds: list[Seed] = []
    for text, versions in groupby(questions, key=lambda question: question[0]):
        entries = list(versions)
        if len(entries) == 1:
            model_answer = entries[0][2]
        else:
            model_answer = "\n\n".join(
                f"{variant}: {answer}" if variant else answer
                for _, variant, answer in entries if answer
            )
        seeds.append(Seed(section, text, model_answer=model_answer or None))
    return seeds


def parse_questionnaire(markdown: str) -> list[Seed]:
    """Read numbered question headings within numbered interview groups."""
    seeds: list[Seed] = []
    section: str | None = None
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            if section is not None:
                seeds.extend(_questionnaire_section(section, lines))
            match = _GROUP.match(line)
            section = f"Interview: {match.group(1).strip()}" if match else None
            lines = []
        elif section is not None:
            lines.append(line)
    if section is not None:
        seeds.extend(_questionnaire_section(section, lines))
    return seeds


def load_banks(paths: Sequence[Path]) -> list[Seed]:
    seeds: list[Seed] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Question bank not found: {path}")
        markdown = path.read_text(encoding="utf-8")
        parser = parse_questionnaire if _GROUP.search(markdown) and _QUESTION.search(markdown) else parse_bank
        seeds.extend(parser(markdown))
    return seeds


def is_interview(section: str) -> bool:
    """Bank sections named "Interview…" are played as a job interview: "Sie", questions in bank order."""
    return section.strip().lower().startswith("interview")


def _picker(seeds: Sequence[Seed], rng: random.Random) -> SeedPicker:
    return SeedPicker(seeds, rng, ordered=bool(seeds) and all(is_interview(s.section) for s in seeds))


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


class Deck(Protocol):
    """What a conversation session needs from its seed source (ScenarioDeck, MeinTagDeck)."""

    label: str

    def next(self) -> Seed: ...
    def options(self) -> list[str]: ...
    @property
    def current_option(self) -> int: ...
    def choose(self, option: int) -> str: ...
    def switch(self) -> str: ...


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
        self._picker = _picker(chosen, rng)

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
            self._picker = _picker(self._seeds, self._rng)
            return self.label
        self._index = option - 1
        self.label = self._sections[self._index]
        self._picker = _picker([s for s in self._seeds if s.section == self.label], self._rng)
        return self.label

    def switch(self) -> str:
        return self.choose((self._index + 1) % len(self._sections) + 1)


class SeedPicker:
    """Random seeds without repeats until every seed was used once, then a fresh shuffle.

    `ordered`: bank order instead (an interview opens with "Erzählen Sie etwas über sich").
    """

    def __init__(self, seeds: Sequence[Seed], rng: random.Random, ordered: bool = False) -> None:
        if not seeds:
            raise ValueError("SeedPicker needs at least one seed")
        self._seeds = list(seeds)
        self._rng = rng
        self._ordered = ordered
        self._queue: list[Seed] = []

    def next(self) -> Seed:
        if not self._queue:
            self._queue = self._seeds[::-1]
            if not self._ordered:
                self._rng.shuffle(self._queue)
        return self._queue.pop()
