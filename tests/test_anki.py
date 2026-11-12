import sqlite3
import zipfile
from datetime import datetime

import pytest
from typer.testing import CliRunner

from self_talk_coach import anki, db
from self_talk_coach.cli import app
from self_talk_coach.domain import CandidateStatus, CandidateType, NewCandidate, TurnSpeaker

NOW = datetime(2026, 11, 12, 15, 30, 0)


@pytest.fixture
def data_root(tmp_path):
    conn = db.connect(tmp_path / "db" / "self_talk_coach.sqlite")
    db.init_db(conn)
    cid = db.insert_conversation(
        conn, started_at="2026-11-12", scenario="Test", stt_model="s", llm_model="l", tts_voice="v"
    )
    turn = db.insert_turn(
        conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.LEARNER,
        text="Ich habe einen Frage.",
    )
    db.replace_conversation_candidates(conn, cid, [
        NewCandidate(turn, CandidateType.GRAMMAR_CORRECTION, "einen Frage", "eine Frage", "Artikel <f>"),
        NewCandidate(turn, CandidateType.VOCABULARY, "Anfrage", "", "die Anfrage, -n"),
        NewCandidate(turn, CandidateType.PHRASE_UPGRADE, "Frage", "Anliegen", "Präziser"),
    ])
    db.review_candidate(conn, 1, CandidateStatus.APPROVED)
    db.review_candidate(conn, 2, CandidateStatus.APPROVED)
    db.review_candidate(conn, 3, CandidateStatus.REJECTED)
    conn.commit()
    conn.close()
    return tmp_path


def _conn(data_root):
    return db.connect(data_root / "db" / "self_talk_coach.sqlite")


def _statuses(conn):
    return [row[0] for row in conn.execute("SELECT export_status FROM practice_items ORDER BY id")]


def test_export_writes_package_and_marks_items(data_root):
    with _conn(data_root) as conn:
        result = anki.export_practice_items(conn, data_root / "out", now=NOW)
        assert _statuses(conn) == ["exported", "exported"]
    assert result.count == 2
    assert result.path == data_root / "out" / "stc-2026-11-12-153000.apkg"
    with zipfile.ZipFile(result.path) as package:
        assert "collection.anki2" in package.namelist()


def test_notes_carry_prompt_escaped_fields_stable_guid_and_tag(data_root):
    with _conn(data_root) as conn:
        items = anki.list_practice_items(conn)
    correction, vocabulary = (anki.build_note(item) for item in items)
    assert correction.fields == ["Korrigiere:", "einen Frage", "eine Frage", "Artikel &lt;f&gt;"]
    assert correction.tags == ["grammar_correction"]
    assert correction.guid == anki.build_note(items[0]).guid
    assert correction.guid != vocabulary.guid
    # No suggestion: back repeats the front, so the card shows only the notes.
    assert vocabulary.fields == ["Wort:", "Anfrage", "", "die Anfrage, -n"]


def test_rerun_exports_only_new_items_unless_all(data_root):
    with _conn(data_root) as conn:
        anki.export_practice_items(conn, data_root / "out", now=NOW)
        assert anki.export_practice_items(conn, data_root / "out", now=NOW) == anki.AnkiExport(None, 0)
        again = anki.export_practice_items(conn, data_root / "out", include_exported=True, now=NOW)
    assert again.count == 2
    assert len(list((data_root / "out").iterdir())) == 1


def test_failed_write_leaves_items_unexported(data_root, monkeypatch):
    def broken_write(self, path):
        raise OSError("disk full")

    monkeypatch.setattr(anki.genanki.Package, "write_to_file", broken_write)
    with _conn(data_root) as conn:
        with pytest.raises(OSError, match="disk full"):
            anki.export_practice_items(conn, data_root / "out", now=NOW)
        assert _statuses(conn) == ["not_exported", "not_exported"]


def test_cli_export_anki(data_root):
    runner = CliRunner()
    result = runner.invoke(app, ["export", "anki", "--data-root", str(data_root)])
    assert result.exit_code == 0, result.output
    assert "Exported practice items: 2" in result.output
    assert len(list((data_root / "exports" / "anki").glob("stc-*.apkg"))) == 1
    second = runner.invoke(app, ["export", "anki", "--data-root", str(data_root)])
    assert second.exit_code == 0
    assert "No practice items to export." in second.output


def test_cli_export_anki_missing_database(tmp_path):
    result = CliRunner().invoke(app, ["export", "anki", "--data-root", str(tmp_path / "none")])
    assert result.exit_code == 1
    assert "no database at" in result.output
    assert not (tmp_path / "none").exists()


def test_unknown_practice_type_gets_generic_prompt(data_root):
    with _conn(data_root) as conn:
        conn.execute("UPDATE practice_items SET practice_type = 'other' WHERE id = 1")
        item = anki.list_practice_items(conn)[0]
    assert isinstance(item, sqlite3.Row)
    assert anki.build_note(item).fields[0] == "Übe:"
