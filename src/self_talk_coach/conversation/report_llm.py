"""Session-report analysis: one report-LLM call per conversation, every quote checked (ADR 0006)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from self_talk_coach.conversation.partner import ChatClient

Turn = Mapping[str, Any]
CATEGORIES = ("Verbposition", "Kasus/Artikel", "Verbform", "Präposition", "Wortwahl", "Sonstiges")
CHECK_MARK = "(CHECK)"

_SYSTEM = f"""You analyse one spoken German practice conversation of a B1 learner.
Learner turns are speech-to-text output that keeps the learner's errors exactly as spoken.
Lines look like "[L4] text" (learner, turn 4) or "[P3] text" (partner, turn 3). "{CHECK_MARK}" marks a partner turn
that asked the learner to retell what the partner just said.
Return ONLY a JSON object with these keys:
- "errors": real grammar or word errors in LEARNER turns:
  {{"turn": int, "original": str, "corrected": str, "category": one of {list(CATEGORIES)}, "explanation": str}}
  "explanation": English, max 12 words. Skip filler (äh, okay), errors the learner corrected himself, and
  unclear words that may be speech-to-text noise.
- "phrasings": correct but unnatural learner sentences: {{"turn": int, "original": str, "better": str}}
- "english": English words or phrases the learner used: {{"turn": int, "english": str, "german": str}}
- "rescue_phrases": phrases the learner used to buy time or ask for repetition or clarification
  ("Kannst du das nochmal sagen?", "Ich habe das nicht verstanden", "Moment, ich überlege"):
  {{"turn": int, "phrase": str}}. These are a good strategy, never a listening failure.
- "comprehension": for each learner turn directly after a {CHECK_MARK} partner turn:
  {{"turn": int, "score": 0|1|2, "missed": str}} (0 = main point missed, 1 = main point only,
  2 = main point and a detail; "missed": what was left out, short German).
"original", "english" and "phrase" must be copied character for character from that learner turn.
Use empty lists when there is nothing to report."""

_FENCE = re.compile(r"`{3}(?:json)?")
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_NOT_WORD = re.compile(r"[^\wäöüß ]")


class ReportFormatError(ValueError):
    """The report model's output could not be parsed into ReportFindings."""


class ErrorFinding(BaseModel):
    turn: int
    original: str
    corrected: str
    category: str
    explanation: str = ""

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        return value if value in CATEGORIES else "Sonstiges"


class PhrasingFinding(BaseModel):
    turn: int
    original: str
    better: str


class EnglishFinding(BaseModel):
    turn: int
    english: str
    german: str


class RescueFinding(BaseModel):
    turn: int
    phrase: str


class ComprehensionFinding(BaseModel):
    turn: int
    score: int
    missed: str = ""


class ReportFindings(BaseModel):
    errors: list[ErrorFinding] = Field(default_factory=list)
    phrasings: list[PhrasingFinding] = Field(default_factory=list)
    english: list[EnglishFinding] = Field(default_factory=list)
    rescue_phrases: list[RescueFinding] = Field(default_factory=list)
    comprehension: list[ComprehensionFinding] = Field(default_factory=list)

    def count(self) -> int:
        return sum(len(getattr(self, name)) for name in type(self).model_fields)


def transcript_lines(turns: Sequence[Turn]) -> str:
    lines = []
    for t in turns:
        tag = "L" if t["speaker"] == "learner" else "P"
        mark = f" {CHECK_MARK}" if t["comprehension_check"] else ""
        lines.append(f"[{tag}{t['turn_index']}]{mark} {t['text']}")
    return "\n".join(lines)


def build_messages(turns: Sequence[Turn]) -> list[dict[str, str]]:
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": transcript_lines(turns)}]


def parse_findings(raw: str) -> ReportFindings:
    match = _OBJECT.search(_FENCE.sub("", raw))
    if not match:
        raise ReportFormatError(f"No JSON object in: {raw[:80]!r}")
    try:
        return ReportFindings.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise ReportFormatError(str(exc)) from exc


def _norm(text: str) -> str:
    """Lower-cased words joined by single spaces, padded so `in` matches whole words only."""
    return " " + " ".join(_NOT_WORD.sub(" ", text.lower()).split()) + " "


def verify_findings(findings: ReportFindings, turns: Sequence[Turn]) -> tuple[ReportFindings, int]:
    """Keep only findings whose quote is in that learner turn: the report never claims words he did not say."""
    learner = {t["turn_index"]: _norm(t["text"]) for t in turns if t["speaker"] == "learner"}

    def said(turn: int, quote: str) -> bool:
        return turn in learner and bool(_norm(quote).strip()) and _norm(quote) in learner[turn]

    kept = ReportFindings(
        errors=[f for f in findings.errors if said(f.turn, f.original)],
        phrasings=[f for f in findings.phrasings if said(f.turn, f.original)],
        english=[f for f in findings.english if said(f.turn, f.english)],
        rescue_phrases=[f for f in findings.rescue_phrases if said(f.turn, f.phrase)],
        comprehension=[f for f in findings.comprehension if f.turn in learner and 0 <= f.score <= 2],
    )
    return kept, findings.count() - kept.count()


def analyze(client: ChatClient, model: str, turns: Sequence[Turn], timeout: float = 90.0) -> ReportFindings:
    return parse_findings(client.complete(model, build_messages(turns), timeout))


def top_errors(errors: Sequence[ErrorFinding], n: int = 3) -> list[tuple[str, list[ErrorFinding]]]:
    """Most frequent error categories first; ties keep the order of first appearance."""
    groups: dict[str, list[ErrorFinding]] = {}
    for error in errors:
        groups.setdefault(error.category, []).append(error)
    return sorted(groups.items(), key=lambda item: -len(item[1]))[:n]
