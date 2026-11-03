import json
import re
from pathlib import Path
from types import SimpleNamespace

from self_talk_coach.cli import report_deps
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
    assert len(status) == 1 and status[0].startswith("[Wörter] ") and "neue-woerter.md" in status[0]


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


def test_new_words_get_meanings_sentence_examples_and_the_running_list(tmp_path: Path) -> None:
    conn, cid = _setup(tmp_path)
    glossed = {**FINDINGS, "meanings": [{"word": "acht", "meaning": "eight"}]}
    client = FakeClient(json.dumps(glossed))
    seen: list = []
    client.complete = lambda model, messages, timeout: seen.append(messages) or json.dumps(glossed)
    deps, _ = _deps(conn, tmp_path, client)
    text = build_report(deps, cid)

    assert "New words: " in seen[0][-1]["content"] and "acht" in seen[0][-1]["content"]
    words = text.split("## Neue Wörter")[1]
    assert "**Rückerstattung** (refund)" in words  # learner's English comes first, meaning = his word
    assert "**acht** (eight) — Ich war um acht im Laden." in words  # one sentence, not the whole turn
    listed = (tmp_path / "neue-woerter.md").read_text(encoding="utf-8")
    assert f"<!-- stc:{cid} -->" in listed and "- [ ] **acht** — eight · „Ich war um acht im Laden.“" in listed


def _interview_setup(tmp_path: Path, scenario: str = "Interview: Test"):
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    cid = insert_conversation(conn, started_at="2026-11-03T10:00:00+00:00", scenario=scenario,
                              stt_model="s", llm_model="l", tts_voice="v")
    turns = [
        (TurnSpeaker.PARTNER, "Erzählen Sie von sich.", "Frage A?"),
        (TurnSpeaker.LEARNER, "Ich lerne Deutsch.", None),
        (TurnSpeaker.PARTNER, "Und warum?", "Frage A?"),
        (TurnSpeaker.LEARNER, "Ich möchte üben.", None),
        (TurnSpeaker.PARTNER, "Nächste Frage.", "Frage B?"),
        (TurnSpeaker.LEARNER, "Meine dritte Antwort.", None),
        (TurnSpeaker.PARTNER, "Letzte Frage.", "Frage C?"),
    ]
    for index, (speaker, text, seed) in enumerate(turns):
        insert_turn(conn, conversation_id=cid, turn_index=index, speaker=speaker, text=text, seed=seed)
    finish_conversation(conn, cid, ended_at="2026-11-03T10:05:00+00:00", status=ConversationStatus.COMPLETED)
    return conn, cid


def test_model_answers_group_followups_quote_paragraphs_and_keep_unanswered_questions(tmp_path: Path) -> None:
    conn, cid = _interview_setup(tmp_path)
    deps, _ = _deps(conn, tmp_path, FakeClient(json.dumps({})))
    # Deliberately reverse mapping order: stored partner turns determine report order.
    deps.model_answers = {"Frage C?": "Antwort C.", "Frage A?": "Absatz eins.\n\nAbsatz zwei."}
    text = build_report(deps, cid)
    assert text.endswith(
        "\n## Musterantworten\n"
        "### Frage A?\n**Du:** Ich lerne Deutsch. / Ich möchte üben.\n\n"
        "> Absatz eins.\n>\n> Absatz zwei.\n\n"
        "### Frage C?\n**Du:** –\n\n> Antwort C.\n"
    )
    assert "Frage B?" not in text.split("## Musterantworten")[1]
    assert text.index("## Neue Wörter") < text.index("## Musterantworten")
    assert (tmp_path / "conversations" / f"{cid:04d}" / "report.md").read_text(encoding="utf-8") == text


def test_empty_model_answers_preserve_report_text(tmp_path: Path) -> None:
    conn, cid = _interview_setup(tmp_path)
    deps, _ = _deps(conn, tmp_path, FakeClient(json.dumps({})))
    without_field = build_report(deps, cid)
    explicit = ReportDeps(conn=deps.conn, paths=deps.paths, client=deps.client, model=deps.model,
                          lemmatizer=deps.lemmatizer, baseline=deps.baseline, status=deps.status,
                          model_answers={})
    text = build_report(explicit, cid)
    assert "## Musterantworten" not in text
    assert text == without_field


def test_mein_tag_omits_model_answers_even_with_matching_seeds(tmp_path: Path) -> None:
    conn, cid = _interview_setup(tmp_path, scenario="Mein Tag")
    deps, _ = _deps(conn, tmp_path, FakeClient(json.dumps({})))
    deps.model_answers = {"Frage A?": "Vorbereitete Antwort."}
    assert "## Musterantworten" not in build_report(deps, cid)


def _report_config(question_banks: list[Path]) -> SimpleNamespace:
    return SimpleNamespace(question_banks=question_banks, gateway_base_url="https://example.invalid",
                           gateway_api_key="synthetic-test-key", report_model="test-model")


def test_report_deps_missing_bank_skips_model_answers_visibly(tmp_path: Path) -> None:
    status: list[str] = []
    missing = tmp_path / "missing.md"
    deps = report_deps(None, AppPaths.from_data_root(tmp_path), _report_config([missing]), status.append)
    assert deps.model_answers == {}
    assert len(status) == 1
    assert status[0].startswith("[Hinweis] Musterantworten übersprungen: ")
    assert str(missing) in status[0]


def test_report_deps_loads_only_nonempty_model_answers(tmp_path: Path) -> None:
    bank = tmp_path / "synthetic-bank.md"
    bank.write_text("# 1. Test\n## 1.1 Frage A?\nAntwort A.\n\n## 1.2 Frage B?\n", encoding="utf-8")
    status: list[str] = []
    deps = report_deps(None, AppPaths.from_data_root(tmp_path), _report_config([bank]), status.append)
    assert deps.model_answers == {"Frage A?": "Antwort A."}
    assert status == []
