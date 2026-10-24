"""Running word list: new words from every conversation in one Markdown file the learner reads and ticks off."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from self_talk_coach.mine import NewWord

TITLE = "# Neue Wörter"
INTRO = (
    "Wörter aus deinen Gesprächen, die nicht in der B1-Grundliste stehen und die du selbst noch nicht benutzt hast.\n"
    "Hake ab (`[x]`), was du in deine eigene Liste übernommen hast. Haken bleiben, wenn der Bericht neu läuft."
)
_MARKER = re.compile(r"^<!-- stc:(\d+) -->$")
_TICKED = re.compile(r"^- \[[xX]\] \*\*(.+?)\*\*")


def _sections(text: str) -> dict[int, list[str]]:
    """Existing sections by conversation id; each section is its lines from the '## ' heading on."""
    sections: dict[int, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = [line]
            continue
        if current is None:
            continue
        current.append(line)
        match = _MARKER.match(line)
        if match:
            sections[int(match.group(1))] = current
    return sections


def _entry(word: NewWord, ticked: bool) -> str:
    meaning = f" — {word.meaning}" if word.meaning else ""
    return f"- [{'x' if ticked else ' '}] **{word.lemma}**{meaning} · „{word.example}“"


def update_word_list(path: Path, conversation_id: int, heading: str, words: Sequence[NewWord]) -> None:
    """Write this conversation's words into the list (newest conversation first), keeping ticks already set."""
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    sections = _sections(existing)
    old = sections.get(conversation_id, [])
    ticked = {m.group(1) for line in old if (m := _TICKED.match(line))}
    if words:
        sections[conversation_id] = [f"## {heading}", f"<!-- stc:{conversation_id} -->",
                                     *(_entry(w, w.lemma in ticked) for w in words)]
    else:
        sections.pop(conversation_id, None)
    body = ["\n".join(lines).rstrip() for _, lines in sorted(sections.items(), reverse=True)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join([TITLE, INTRO, *body]) + "\n", encoding="utf-8")
