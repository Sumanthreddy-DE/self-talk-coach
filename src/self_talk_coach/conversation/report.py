"""Session report: metrics + report-LLM findings + new words -> report.md, learning_candidates, status."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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

    findings, analysis_error = _findings(deps, turns)
    new_words, vocab_error = _new_words(deps, turns, findings)
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
    set_report_status(deps.conn, conversation_id, ReportStatus.FAILED if analysis_error else ReportStatus.DONE)
    return text


def _findings(deps: ReportDeps, turns: Sequence[Turn]) -> tuple[ReportFindings | None, str | None]:
    try:
        raw = analyze(deps.client, deps.model, turns)
    except Exception as exc:  # noqa: BLE001 — any failure: numbers-only report with a visible reason
        reason = f"{type(exc).__name__}: {str(exc)[:160]}"
        deps.status(f"[Hinweis] Fehleranalyse fehlgeschlagen, Bericht nur mit Zahlen. Grund: {reason}")
        return None, reason
    findings, dropped = verify_findings(raw, turns)
    if dropped:
        deps.status(f"[Hinweis] {dropped} KI-Fund(e) verworfen: Zitat steht nicht im Transkript.")
    return findings, None


def _new_words(
    deps: ReportDeps, turns: Sequence[Turn], findings: ReportFindings | None
) -> tuple[list[NewWord] | None, str | None]:
    try:
        lemmatize = deps.lemmatizer()
    except MinerUnavailable as exc:
        deps.status(f"[Hinweis] Neue Wörter übersprungen. Grund: {exc}")
        return None, str(exc)
    partner = [t for t in turns if t["speaker"] == "partner"]
    for turn in partner:
        update_turn_out_of_baseline(deps.conn, turn["id"], out_of_baseline_ratio(turn["text"], deps.baseline, lemmatize))
    known = {tok.lemma.lower() for t in turns if t["speaker"] == "learner" for tok in lemmatize(t["text"])}
    english = [x.german for x in findings.english] if findings else []
    return mine_new_words(english + [t["text"] for t in partner], deps.baseline, known, lemmatize), None


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
