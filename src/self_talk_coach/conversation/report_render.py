"""Session report as Markdown (German headings; spec § Session report)."""

from __future__ import annotations

from dataclasses import dataclass

from self_talk_coach.conversation.report_llm import ComprehensionFinding, ReportFindings, top_errors
from self_talk_coach.conversation.report_metrics import FreezeTrend, ListeningSummary
from self_talk_coach.mine import NewWord


@dataclass(frozen=True)
class ReportData:
    conversation_id: int
    started_at: str
    scenario: str | None
    mein_tag: bool
    learner_turns: int
    findings: ReportFindings | None  # None = report LLM failed
    analysis_error: str | None
    freeze: FreezeTrend
    freeze_per_question: list[tuple[str, float]]
    listening: ListeningSummary
    missed_rescue: list[str]
    checks: list[tuple[str, str, ComprehensionFinding | None]]  # partner text, learner retell, score
    new_words: list[NewWord] | None  # None = miner skipped
    vocab_error: str | None


def _freeze_line(f: FreezeTrend) -> str:
    if f.current is None:
        return "Keine Freeze-Zeit gemessen."
    line = f"Median {f.current:.1f} s"
    if f.previous is None or f.delta is None:
        return line + " (noch kein Vergleich)."
    sign = "+" if f.delta > 0 else ""
    return line + f", vorher {f.previous:.1f} s (letzte {f.compared} Gespräche) → {sign}{f.delta:.1f} s."


def _or_dash(lines: list[str]) -> list[str]:
    return lines or ["–"]


def render_report(d: ReportData) -> str:
    out = [f"# Gespräch {d.conversation_id} — {d.started_at[:10]} — {d.scenario or 'alle Bereiche'}", ""]
    out.append(f"{d.learner_turns} Antworten, {d.listening.partner_turns} Partner-Turns.")

    out += ["", "## Top-Fehler"]
    if d.findings is None:
        out.append(f"Fehleranalyse fehlgeschlagen ({d.analysis_error}). Wiederholen: `stc report {d.conversation_id}`")
    else:
        groups = top_errors(d.findings.errors)
        if not groups:
            out.append("Keine Fehler gefunden.")
        for category, items in groups:
            out.append(f"- **{category}** ({len(items)}×)")
            out += [f"  - {e.original} → **{e.corrected}** — {e.explanation}" for e in items[:2]]
        out += ["", "## Besser formulieren"]
        out += _or_dash([f"- {p.original} → **{p.better}**" for p in d.findings.phrasings])
        out += ["", "## Englisch → Deutsch"]
        out += _or_dash([f"- {x.english} → **{x.german}**" for x in d.findings.english])

    if not d.mein_tag:
        out += ["", "## Freeze", _freeze_line(d.freeze)]
        out += [f"- {seconds:.1f} s — {question}" for question, seconds in d.freeze_per_question]

    out += ["", "## Hörhilfen",
            f"{d.listening.aids} Hörhilfen bei {d.listening.partner_turns} Partner-Turns ({d.listening.per_turn} pro Turn)."]
    out += [f"- schwer: {sentence}" for sentence in d.listening.hard]

    out += ["", "## Rettungssätze"]
    used = [f"- benutzt: {r.phrase}" for r in d.findings.rescue_phrases] if d.findings else []
    missed = [f"- verpasst (Hilfe kam, kein Rettungssatz): {question}" for question in d.missed_rescue]
    out += _or_dash(used + missed)

    if d.checks:
        out += ["", "## Verständnis-Checks"]
        for partner_text, retell, finding in d.checks:
            score = f"{finding.score}/2" if finding else "–"
            gap = f" — fehlte: {finding.missed}" if finding and finding.missed else ""
            out.append(f"- {score} — Partner: {partner_text} / Du: {retell}{gap}")

    out += ["", "## Neue Wörter"]
    if d.new_words is None:
        out.append(f"übersprungen ({d.vocab_error})")
    else:
        out += _or_dash([f"- **{w.lemma}** — {w.example}" for w in d.new_words])
    return "\n".join(out) + "\n"
