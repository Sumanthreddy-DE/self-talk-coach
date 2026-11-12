"""Anki export stage: approved practice items -> .apkg via genanki (ADR 0003)."""

from __future__ import annotations

import html
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import genanki

from self_talk_coach.domain import CandidateType, ExportStatus

# Fixed ids: re-importing a later package updates these notes instead of duplicating them.
MODEL_ID = 1_731_420_001
DECK_ID = 1_731_420_002
DECK_NAME = "self-talk-coach"

PROMPTS = {
    CandidateType.GRAMMAR_CORRECTION: "Korrigiere:",
    CandidateType.PHRASE_UPGRADE: "Sag es besser:",
    CandidateType.VOCABULARY: "Wort:",
}
DEFAULT_PROMPT = "Übe:"

MODEL = genanki.Model(
    MODEL_ID,
    "self-talk-coach practice item",
    fields=[{"name": "Prompt"}, {"name": "Front"}, {"name": "Back"}, {"name": "Notes"}],
    templates=[{
        "name": "Card 1",
        "qfmt": '<div class="prompt">{{Prompt}}</div><div class="front">{{Front}}</div>',
        "afmt": '{{FrontSide}}<hr id="answer">'
                '{{#Back}}<div class="back">{{Back}}</div>{{/Back}}'
                '{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}',
    }],
    css=".card { font-family: sans-serif; font-size: 22px; text-align: center; }"
        " .prompt { font-size: 14px; color: #888; } .back { font-weight: bold; }"
        " .notes { font-size: 16px; margin-top: 12px; }",
)


@dataclass(frozen=True)
class AnkiExport:
    """Written package path (None when nothing was due) and its card count."""

    path: Path | None
    count: int


def list_practice_items(conn: sqlite3.Connection, *, include_exported: bool = False) -> list[sqlite3.Row]:
    where = "" if include_exported else "WHERE export_status = ?"
    params = () if include_exported else (ExportStatus.NOT_EXPORTED,)
    return conn.execute(
        f"SELECT id, practice_type, front, back, notes FROM practice_items {where} ORDER BY id",
        params,
    ).fetchall()


def build_note(item: sqlite3.Row) -> genanki.Note:
    back = "" if item["back"] == item["front"] else item["back"]
    return genanki.Note(
        model=MODEL,
        fields=[PROMPTS.get(item["practice_type"], DEFAULT_PROMPT),
                *(html.escape(text or "") for text in (item["front"], back, item["notes"]))],
        guid=genanki.guid_for("self-talk-coach practice item", item["id"]),
        tags=[item["practice_type"]],
    )


def export_practice_items(
    conn: sqlite3.Connection,
    out_dir: Path,
    *,
    include_exported: bool = False,
    now: datetime | None = None,
) -> AnkiExport:
    items = list_practice_items(conn, include_exported=include_exported)
    if not items:
        return AnkiExport(None, 0)
    deck = genanki.Deck(DECK_ID, DECK_NAME)
    for item in items:
        deck.add_note(build_note(item))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"stc-{(now or datetime.now()):%Y-%m-%d-%H%M%S}.apkg"
    # Mark only after the file exists; a crash in between re-exports the same guids next run.
    genanki.Package(deck).write_to_file(path)
    conn.executemany(
        "UPDATE practice_items SET export_status = ?, updated_at = datetime('now') WHERE id = ?",
        [(ExportStatus.EXPORTED, item["id"]) for item in items],
    )
    conn.commit()
    return AnkiExport(path, len(items))
