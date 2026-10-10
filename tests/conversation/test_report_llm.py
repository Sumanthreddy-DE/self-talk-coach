import json

import pytest

from self_talk_coach.conversation.report_llm import (
    ErrorFinding,
    ReportFindings,
    ReportFormatError,
    analyze,
    parse_findings,
    top_errors,
    transcript_lines,
    verify_findings,
)

TURNS = [
    {"turn_index": 0, "speaker": "partner", "text": "Wie war die Schicht?", "comprehension_check": 0},
    {"turn_index": 1, "speaker": "learner", "text": "Ich habe einen Frage, es war really stressful.", "comprehension_check": 0},
    {"turn_index": 2, "speaker": "partner", "text": "Ich war um acht im Laden. Erzähl kurz nach.", "comprehension_check": 1},
    {"turn_index": 3, "speaker": "learner", "text": "Du warst im Laden. Kannst du das nochmal sagen?", "comprehension_check": 0},
]

FINDINGS = {
    "errors": [
        {"turn": 1, "original": "einen Frage", "corrected": "eine Frage", "category": "Kasus/Artikel", "explanation": "Frage is feminine"},
        {"turn": 1, "original": "einen Antwort", "corrected": "eine Antwort", "category": "Kasus/Artikel", "explanation": "invented"},
        {"turn": 0, "original": "Wie war", "corrected": "x", "category": "Verbposition", "explanation": "partner turn"},
        {"turn": 3, "original": "Du warst im Laden", "corrected": "Du warst im Laden", "category": "Tippfehler", "explanation": "odd"},
    ],
    "phrasings": [],
    "english": [{"turn": 1, "english": "really stressful", "german": "echt stressig"}],
    "rescue_phrases": [{"turn": 3, "phrase": "Kannst du das nochmal sagen"}],
    "comprehension": [{"turn": 3, "score": 1, "missed": "um acht"}, {"turn": 3, "score": 7, "missed": ""}],
}


class FakeClient:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls: list = []

    def complete(self, model, messages, timeout):
        self.calls.append((model, messages, timeout))
        return self.raw


def test_transcript_lines_mark_speaker_turn_and_check() -> None:
    lines = transcript_lines(TURNS).splitlines()
    assert lines[0] == "[P0] Wie war die Schicht?"
    assert lines[2] == "[P2] (CHECK) Ich war um acht im Laden. Erzähl kurz nach."
    assert lines[3].startswith("[L3] ")


def test_parse_handles_fences_and_unknown_category() -> None:
    findings = parse_findings("Hier:\n```json\n" + json.dumps(FINDINGS) + "\n```")
    assert findings.errors[3].category == "Sonstiges"
    with pytest.raises(ReportFormatError):
        parse_findings("kein JSON")


def test_verify_drops_quotes_the_learner_never_said() -> None:
    kept, dropped = verify_findings(parse_findings(json.dumps(FINDINGS)), TURNS)
    assert [e.original for e in kept.errors] == ["einen Frage", "Du warst im Laden"]
    assert kept.english[0].german == "echt stressig"
    assert kept.rescue_phrases[0].turn == 3
    assert [c.score for c in kept.comprehension] == [1]
    assert dropped == 3  # invented quote, partner turn, score out of range


def test_verify_matches_whole_words_only() -> None:
    partial = ReportFindings(errors=[ErrorFinding(turn=1, original="abe einen Fr", corrected="x", category="Wortwahl")])
    kept, dropped = verify_findings(partial, TURNS)
    assert kept.errors == [] and dropped == 1


def test_analyze_sends_transcript_to_report_model() -> None:
    client = FakeClient(json.dumps(FINDINGS))
    findings = analyze(client, "claude-sonnet-5", TURNS)
    model, messages, timeout = client.calls[0]
    assert model == "claude-sonnet-5" and timeout == 90.0
    assert "[L1] Ich habe einen Frage" in messages[1]["content"]
    assert isinstance(findings, ReportFindings)


def test_top_errors_groups_by_category_most_frequent_first() -> None:
    errors = [
        ErrorFinding(turn=1, original="a", corrected="b", category="Verbposition"),
        ErrorFinding(turn=3, original="c", corrected="d", category="Kasus/Artikel"),
        ErrorFinding(turn=5, original="e", corrected="f", category="Kasus/Artikel"),
    ]
    assert [(cat, len(items)) for cat, items in top_errors(errors)] == [("Kasus/Artikel", 2), ("Verbposition", 1)]
