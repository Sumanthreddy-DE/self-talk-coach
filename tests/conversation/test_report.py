import json
import re
from pathlib import Path

from self_talk_coach.conversation.report import ReportDeps, build_report
from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_conversation_candidates,
    list_turns,
)
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.mine import MinerUnavailable, Token
from self_talk_coach.paths import AppPaths

FINDINGS = {
    "errors": [{"turn": 1, "original": "einen Frage", "corrected": "eine Frage",
                "category": "Kasus/Artikel", "explanation": "Frage is feminine"}],
    "phrasings": [{"turn": 3, "original": "Ich war im Laden", "better": "Ich war gerade im Laden"}],
    "english": [{"turn": 1, "english": "refund", "german": "Rückerstattung"}],
    "rescue_phrases": [{"turn": 3, "phrase": "Kannst du das nochmal sagen"}],
    "comprehension": [{"turn": 3, "score": 1, "missed": "um acht"}],
}


class FakeClient:
    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def complete(self, model, messages, timeout):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fake_lemmatize(text: str) -> list[Token]:
    return [Token(w, "NOUN", False) for w in re.findall(r"\w+", text)]


def _setup(tmp_path: Path, scenario: str | None = "McDonald's"):
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    cid = insert_conversation(conn, started_at="2026-10-08T10:00:00+00:00", scenario=scenario,
                              stt_model="s", llm_model="l", tts_voice="v")
    insert_turn(conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER, text="Was möchtest du?")
    insert_turn(conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
                text="Ich habe einen Frage zum refund.", freeze_seconds=3.0)
    insert_turn(conn, conversation_id=cid, turn_index=2, speaker=TurnSpeaker.PARTNER,
                text="Ich war um acht im Laden. Erzähl kurz nach.", comprehension_check=True)
    insert_turn(conn, conversation_id=cid, turn_index=3, speaker=TurnSpeaker.LEARNER,
                text="Ich war im Laden. Kannst du das nochmal sagen?", freeze_seconds=5.0)
    finish_conversation(conn, cid, ended_at="2026-10-08T10:05:00+00:00", status=ConversationStatus.COMPLETED)
    return conn, cid


def _deps(conn, tmp_path, client, lemmatizer=lambda: fake_lemmatize):
    status: list[str] = []
    deps = ReportDeps(conn=conn, paths=AppPaths.from_data_root(tmp_path), client=client, model="claude-sonnet-5",
                      lemmatizer=lemmatizer, baseline=frozenset({"laden", "ich", "war"}), status=status.append)
    return deps, status


def test_full_report_written_and_candidates_stored(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)))
    text = build_report(deps, cid)

    assert (tmp_path / "conversations" / f"{cid:04d}" / "report.md").read_text(encoding="utf-8") == text
    for heading in ("## Top-Fehler", "## Besser formulieren", "## Englisch → Deutsch", "## Freeze",
                    "## Hörhilfen", "## Rettungssätze", "## Verständnis-Checks", "## Neue Wörter"):
        assert heading in text
    assert "einen Frage → **eine Frage**" in text
    assert "refund → **Rückerstattung**" in text
    assert "1/2" in text and "um acht" in text
    assert "Rückerstattung" in text.split("## Neue Wörter")[1]
    assert get_conversation(conn, cid)["report_status"] == "done"
    types = [r["candidate_type"] for r in list_conversation_candidates(conn, cid)]
    assert types == ["grammar_correction", "phrase_upgrade", "vocabulary"]
    partner = [t for t in list_turns(conn, cid) if t["speaker"] == "partner"]
    assert all(t["out_of_baseline_ratio"] is not None for t in partner)
    assert status == []


def test_llm_failure_gives_metrics_only_report_and_visible_reason(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    deps, status = _deps(conn, tmp_path, FakeClient(RuntimeError("429 plan expired")))
    text = build_report(deps, cid)
    assert any("Fehleranalyse fehlgeschlagen" in s and "429 plan expired" in s for s in status)
    assert f"stc report {cid}" in text and "## Freeze" in text
    assert get_conversation(conn, cid)["report_status"] == "failed"
    assert list_conversation_candidates(conn, cid) == []


def test_missing_spacy_model_skips_new_words_visibly(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)

    def missing():
        raise MinerUnavailable("spaCy-Modell de_core_news_lg fehlt")

    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)), lemmatizer=missing)
    text = build_report(deps, cid)
    assert any("Neue Wörter übersprungen" in s and "de_core_news_lg" in s for s in status)
    assert "übersprungen" in text.split("## Neue Wörter")[1]


def test_dropped_findings_are_reported(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    invented = {**FINDINGS, "errors": [{"turn": 1, "original": "nie gesagt", "corrected": "x",
                                        "category": "Wortwahl", "explanation": "y"}]}
    deps, status = _deps(conn, tmp_path, FakeClient(json.dumps(invented)))
    build_report(deps, cid)
    assert any("1 KI-Fund" in s for s in status)


def test_mein_tag_report_has_no_freeze_section(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path, scenario="Mein Tag")
    deps, _ = _deps(conn, tmp_path, FakeClient(json.dumps(FINDINGS)))
    assert "## Freeze" not in build_report(deps, cid)
