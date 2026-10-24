"""Session report: metrics + report-LLM findings + new words -> report.md, learning_candidates, status."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from self_talk_coach.conversation.mein_tag import MEIN_TAG
from self_talk_coach.conversation.partner import ChatClient
from self_talk_coach.conversation.report_llm import ReportFindings, analyze, verify_findings
from self_talk_coach.conversation.report_metrics import (
    answer_pairs,
    freeze_per_question,
    freeze_trend,
    listening_summary,
    missed_rescue,
)
from self_talk_coach.conversation.report_render import ReportData, render_report
from self_talk_coach.conversation.word_list import update_word_list
from self_talk_coach.db import (
    get_conversation,
    list_turns,
    previous_conversations,
    replace_conversation_candidates,
    set_report_status,
    update_turn_out_of_baseline,
)
from self_talk_coach.domain import CandidateType, NewCandidate, ReportStatus
from self_talk_coach.mine import (
    Lemmatize,
    MinerUnavailable,
    NewWord,
    mine_new_words,
    out_of_baseline_ratio,
)
from self_talk_coach.paths import AppPaths

Turn = Mapping[str, Any]
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


@dataclass
class ReportDeps:
    conn: sqlite3.Connection
    paths: AppPaths
    client: ChatClient
    model: str
    lemmatizer: Callable[[], Lemmatize]  # factory: spaCy loads only when a report runs
    baseline: frozenset[str]
    status: Callable[[str], None] = print


def build_report(deps: ReportDeps, conversation_id: int) -> str:
    conv = get_conversation(deps.conn, conversation_id)
    if conv is None:
        raise ValueError(f"Kein Gespräch {conversation_id}")
    turns = list_turns(deps.conn, conversation_id)
    mein_tag = conv["scenario"] == MEIN_TAG

    lemmatize, vocab_error = _lemmatizer(deps)
    mined = _mine(deps, turns, lemmatize) if lemmatize else []
    findings, analysis_error = _findings(deps, turns, [w.lemma for w in mined])
    new_words = _with_meanings(deps, turns, lemmatize, mined, findings) if lemmatize else None
    previous = [
        list_turns(deps.conn, c["id"])
        for c in previous_conversations(deps.conn, conversation_id, exclude_scenario=MEIN_TAG)
    ]
    rescue_turns = {r.turn for r in findings.rescue_phrases} if findings else set()
    data = ReportData(
        conversation_id=conversation_id,
        started_at=conv["started_at"],
        scenario=conv["scenario"],
        mein_tag=mein_tag,
        learner_turns=sum(t["speaker"] == "learner" for t in turns),
        findings=findings,
        analysis_error=analysis_error,
        freeze=freeze_trend(turns, previous),
        freeze_per_question=freeze_per_question(turns),
        listening=listening_summary(turns),
        missed_rescue=missed_rescue(turns, rescue_turns),
        checks=_checks(turns, findings),
        new_words=new_words,
        vocab_error=vocab_error,
    )
    if findings is not None:
        replace_conversation_candidates(deps.conn, conversation_id, _candidates(findings, turns))
    text = render_report(data)
    path = deps.paths.conversation_dir(conversation_id) / "report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if new_words is not None:
        heading = f"Gespräch {conversation_id} — {conv['started_at'][:10]} — {conv['scenario'] or 'alle Bereiche'}"
        update_word_list(deps.paths.word_list, conversation_id, heading, new_words)
        if new_words:
            deps.status(f"[Wörter] {len(new_words)} neue Wörter in {deps.paths.word_list}")
    set_report_status(deps.conn, conversation_id, ReportStatus.FAILED if analysis_error else ReportStatus.DONE)
    return text


def _findings(
    deps: ReportDeps, turns: Sequence[Turn], words: Sequence[str]
) -> tuple[ReportFindings | None, str | None]:
    try:
        raw = analyze(deps.client, deps.model, turns, words)
    except Exception as exc:  # noqa: BLE001 — any failure: numbers-only report with a visible reason
        reason = f"{type(exc).__name__}: {str(exc)[:160]}"
        deps.status(f"[Hinweis] Fehleranalyse fehlgeschlagen, Bericht nur mit Zahlen. Grund: {reason}")
        return None, reason
    findings, dropped = verify_findings(raw, turns)
    if dropped:
        deps.status(f"[Hinweis] {dropped} KI-Fund(e) verworfen: Zitat steht nicht im Transkript.")
    return findings, None


def _lemmatizer(deps: ReportDeps) -> tuple[Lemmatize | None, str | None]:
    try:
        return deps.lemmatizer(), None
    except MinerUnavailable as exc:
        deps.status(f"[Hinweis] Neue Wörter übersprungen. Grund: {exc}")
        return None, str(exc)


def _known(turns: Sequence[Turn], lemmatize: Lemmatize) -> set[str]:
    return {key for t in turns if t["speaker"] == "learner" for tok in lemmatize(t["text"]) for key in tok.keys()}


def _mine(deps: ReportDeps, turns: Sequence[Turn], lemmatize: Lemmatize) -> list[NewWord]:
    """Partner words outside the baseline; the example is the one sentence the word appeared in."""
    partner = [t for t in turns if t["speaker"] == "partner"]
    for turn in partner:
        update_turn_out_of_baseline(deps.conn, turn["id"], out_of_baseline_ratio(turn["text"], deps.baseline, lemmatize))
    sentences = [s for t in partner for s in _SENTENCE_END.split(t["text"].strip()) if s]
    return mine_new_words(sentences, deps.baseline, _known(turns, lemmatize), lemmatize)


def _with_meanings(
    deps: ReportDeps, turns: Sequence[Turn], lemmatize: Lemmatize, mined: list[NewWord],
    findings: ReportFindings | None,
) -> list[NewWord]:
    """German words for the learner's English first (meaning = his English), then mined words with glosses."""
    if findings is None:
        return mined
    english = [replace(w, example=x.english, meaning=x.english)
               for x in findings.english
               for w in mine_new_words([x.german], deps.baseline, _known(turns, lemmatize), lemmatize, limit=1)]
    glosses = {m.word.lower(): m.meaning for m in findings.meanings}
    seen = {w.lemma.lower() for w in english}
    return english + [replace(w, meaning=glosses.get(w.lemma.lower(), "")) for w in mined if w.lemma.lower() not in seen]


def _checks(turns: Sequence[Turn], findings: ReportFindings | None) -> list:
    scores = {c.turn: c for c in findings.comprehension} if findings else {}
    return [
        (p["text"], a["text"], scores.get(a["turn_index"]))
        for p, a in answer_pairs(turns)
        if p["comprehension_check"]
    ]


def _candidates(findings: ReportFindings, turns: Sequence[Turn]) -> list[NewCandidate]:
    ids = {t["turn_index"]: t["id"] for t in turns}
    out = [
        NewCandidate(ids[e.turn], CandidateType.GRAMMAR_CORRECTION, e.original, e.corrected,
                     f"{e.category}: {e.explanation}")
        for e in findings.errors
    ]
    out += [NewCandidate(ids[p.turn], CandidateType.PHRASE_UPGRADE, p.original, p.better, "natürlicher")
            for p in findings.phrasings]
    out += [NewCandidate(ids[x.turn], CandidateType.VOCABULARY, x.english, x.german, "Englisch → Deutsch")
            for x in findings.english]
    return out
