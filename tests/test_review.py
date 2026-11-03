import sqlite3

import pytest
from typer.testing import CliRunner

from self_talk_coach import db
from self_talk_coach.cli import app
from self_talk_coach.domain import CandidateType, NewCandidate, TurnSpeaker


@pytest.fixture
def seeded(tmp_path):
    conn = db.connect(tmp_path / "db" / "self_talk_coach.sqlite")
    db.init_db(conn)
    cid = db.insert_conversation(
        conn, started_at="2026-11-03", scenario="Test", stt_model="s", llm_model="l", tts_voice="v"
    )
    turn = db.insert_turn(
        conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.LEARNER,
        text="Ich habe einen Frage.",
    )
    candidates = [
        NewCandidate(turn, CandidateType.GRAMMAR_CORRECTION, "einen Frage", "eine Frage", "Artikel"),
        NewCandidate(turn, CandidateType.PHRASE_UPGRADE, "Frage", "Anfrage", "Präziser"),
        NewCandidate(turn, CandidateType.VOCABULARY, "Frage", "", "Wort"),
    ]
    db.replace_conversation_candidates(conn, cid, candidates)
    yield conn, cid, candidates
    conn.close()


@pytest.mark.parametrize("initial", ["pending", "deferred"])
@pytest.mark.parametrize("target,action", [
    ("approved", "approve"), ("rejected", "reject"), ("deferred", "defer"),
])
def test_review_transitions_and_noop(seeded, initial, target, action):
    conn, _, _ = seeded
    conn.execute("UPDATE learning_candidates SET status = ?, updated_at = 'old' WHERE id = 1", (initial,))
    conn.commit()
    changed = db.review_candidate(conn, 1, db.CandidateStatus(target), note="reason")
    row = db.get_candidate(conn, 1)
    assert row["status"] == target
    events = db.list_review_events(conn, 1)
    if initial == target:
        assert changed is False
        assert events == []
        assert row["updated_at"] == "old"
    else:
        assert changed is True
        assert row["updated_at"] != "old"
        assert len(events) == 1
        assert events[0]["action"] == action
        assert events[0]["note"] == "reason"
    assert conn.execute("SELECT count(*) FROM practice_items").fetchone()[0] == (target == "approved")


@pytest.mark.parametrize("final", ["approved", "rejected"])
@pytest.mark.parametrize("target", ["approved", "rejected", "deferred"])
def test_final_decisions_and_repeated_actions(seeded, final, target):
    conn, _, _ = seeded
    db.review_candidate(conn, 1, db.CandidateStatus(final))
    before = conn.total_changes
    if final == target:
        assert db.review_candidate(conn, 1, db.CandidateStatus(target), note="ignored") is False
    else:
        with pytest.raises(db.ReviewError, match=f"candidate 1 is {final}; review decisions are final"):
            db.review_candidate(conn, 1, db.CandidateStatus(target))
    assert conn.total_changes == before
    assert len(db.list_review_events(conn, 1)) == 1


@pytest.mark.parametrize("suggestion", [None, "", "eine Frage"])
def test_approve_mapping_and_single_practice_item(seeded, suggestion):
    conn, _, _ = seeded
    conn.execute("UPDATE learning_candidates SET suggested_text = ? WHERE id = 1", (suggestion,))
    conn.commit()
    db.review_candidate(conn, 1, db.CandidateStatus.APPROVED)
    db.review_candidate(conn, 1, db.CandidateStatus.APPROVED)
    items = conn.execute("SELECT * FROM practice_items").fetchall()
    assert len(items) == 1
    item = items[0]
    assert (item["practice_type"], item["front"], item["back"], item["notes"], item["export_status"]) == (
        "grammar_correction", "einen Frage", suggestion or "einen Frage", "Artikel", "not_exported",
    )
    events = db.list_review_events(conn, 1)
    assert len(events) == 1
    assert events[0]["practice_item_id"] == item["id"]
    assert events[0]["note"] is None


@pytest.mark.parametrize("table", ["practice_items", "review_events"])
def test_approve_failure_rolls_back_all_writes(seeded, table):
    conn, _, _ = seeded
    conn.execute(f"CREATE TRIGGER fail_insert BEFORE INSERT ON {table} "
                 "BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
    conn.commit()
    before = dict(db.get_candidate(conn, 1))
    with pytest.raises(sqlite3.IntegrityError, match="forced failure"):
        db.review_candidate(conn, 1, db.CandidateStatus.APPROVED)
    assert dict(db.get_candidate(conn, 1)) == before
    assert conn.execute("SELECT count(*) FROM practice_items").fetchone()[0] == 0
    assert db.list_review_events(conn, 1) == []


def test_unknown_candidate_and_invalid_target(seeded):
    conn, _, _ = seeded
    with pytest.raises(db.ReviewError, match="candidate 999 not found"):
        db.review_candidate(conn, 999, db.CandidateStatus.APPROVED)
    with pytest.raises(db.ReviewError, match="invalid review status"):
        db.review_candidate(conn, 1, db.CandidateStatus.PENDING)


def test_list_filters_and_order_and_history(seeded):
    conn, _, _ = seeded
    db.review_candidate(conn, 1, db.CandidateStatus.DEFERRED)
    assert [r["id"] for r in db.list_candidates(conn)] == [2, 3, 1]
    assert [r["id"] for r in db.list_candidates(conn, db.CandidateStatus.DEFERRED)] == [1]
    db.review_candidate(conn, 1, db.CandidateStatus.REJECTED)
    assert [r["id"] for r in db.list_candidates(conn)] == [2, 3]
    assert len(db.list_candidates(conn, "all")) == 3
    assert [r["action"] for r in db.list_review_events(conn, 1)] == ["defer", "reject"]
    source = db.get_candidate_source(conn, 1)
    assert source["conversation_id"] == 1
    assert source["turn_index"] == 0
    assert source["text"] == "Ich habe einen Frage."


def test_report_rerun_preserves_decisions_and_practice(seeded):
    conn, cid, candidates = seeded
    db.review_candidate(conn, 1, db.CandidateStatus.APPROVED)
    db.review_candidate(conn, 2, db.CandidateStatus.DEFERRED)
    kept = [dict(db.get_candidate(conn, i)) for i in (1, 2)]
    practice = dict(conn.execute("SELECT * FROM practice_items").fetchone())
    history = [dict(r) for r in db.list_review_events(conn, 1)]
    # Distinguish replacement from an unchanged pending row despite SQLite id reuse.
    conn.execute("UPDATE learning_candidates SET explanation = 'stale' WHERE id = 3")
    conn.commit()
    db.replace_conversation_candidates(conn, cid, candidates)
    items = conn.execute("SELECT * FROM practice_items").fetchall()
    assert len(items) == 1
    assert dict(items[0]) == practice
    assert [dict(db.get_candidate(conn, i)) for i in (1, 2)] == kept
    assert [dict(r) for r in db.list_review_events(conn, 1)] == history
    rows = db.list_conversation_candidates(conn, cid)
    assert len(rows) == 3
    assert rows[2]["status"] == "pending"
    assert rows[2]["explanation"] == "Wort"
    db.review_candidate(conn, 2, db.CandidateStatus.REJECTED)
    rejected = dict(db.get_candidate(conn, 2))
    db.replace_conversation_candidates(conn, cid, candidates + [candidates[0]])
    assert dict(db.get_candidate(conn, 2)) == rejected
    assert len(db.list_conversation_candidates(conn, cid)) == 3


def test_report_rerun_failure_restores_previous_candidates(seeded):
    conn, cid, candidates = seeded
    before = [dict(r) for r in db.list_conversation_candidates(conn, cid)]
    conn.execute("CREATE TRIGGER fail_candidate BEFORE INSERT ON learning_candidates "
                 "BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="forced failure"):
        db.replace_conversation_candidates(conn, cid, candidates)
    assert [dict(r) for r in db.list_conversation_candidates(conn, cid)] == before


def review_cli(tmp_path, *args):
    return CliRunner().invoke(app, ["review", *args, "--data-root", str(tmp_path)])


def test_cli_list_show_and_review(seeded, tmp_path):
    conn, _, _ = seeded
    result = review_cli(tmp_path, "approve", "1", "--note", "keep it")
    assert result.exit_code == 0, result.output
    assert "candidate 1 approved" in result.output
    result = review_cli(tmp_path, "approve", "1")
    assert result.exit_code == 0
    assert result.output.strip() == "candidate 1 already approved"
    result = review_cli(tmp_path, "reject", "1")
    assert result.exit_code == 1
    assert "candidate 1 is approved; review decisions are final" in result.output
    result = review_cli(tmp_path, "list")
    assert result.exit_code == 0
    assert "grammar_correction" not in result.output
    assert "phrase_upgrade" in result.output and "vocabulary" in result.output
    result = review_cli(tmp_path, "list", "--status", "all")
    assert result.exit_code == 0
    assert "grammar_correction" in result.output
    result = review_cli(tmp_path, "show", "1")
    assert result.exit_code == 0
    for key, value in dict(db.get_candidate(conn, 1)).items():
        assert f"{key}: {value}" in result.output
    for text in ("conversation_id: 1", "turn_index: 0", "Ich habe einen Frage.", "approve", "keep it"):
        assert text in result.output
    assert len(db.list_review_events(conn, 1)) == 1


def test_cli_defer_reject_filters_and_missing(seeded, tmp_path):
    conn, _, _ = seeded
    for action, status in (("defer", "deferred"), ("reject", "rejected")):
        result = review_cli(tmp_path, action, "2", "--note", action)
        assert result.exit_code == 0, result.output
        result = review_cli(tmp_path, "list", "--status", status)
        assert result.exit_code == 0
        assert "phrase_upgrade" in result.output
        assert "grammar_correction" not in result.output
    for command in ("show", "approve", "reject", "defer"):
        result = review_cli(tmp_path, command, "999")
        assert result.exit_code == 1
        assert "candidate 999 not found" in result.output
    result = review_cli(tmp_path, "list", "--status", "invalid")
    assert result.exit_code == 2
    assert conn.execute("SELECT count(*) FROM practice_items").fetchone()[0] == 0


def test_cli_empty_list(tmp_path):
    initialized = CliRunner().invoke(app, ["init", "--data-root", str(tmp_path)])
    assert initialized.exit_code == 0, initialized.output
    result = review_cli(tmp_path, "list")
    assert result.exit_code == 0
    assert result.output.strip() == "No candidates."


@pytest.mark.parametrize("args", [
    ("list",), ("show", "1"), ("approve", "1"), ("reject", "1"), ("defer", "1"),
])
def test_cli_missing_database_does_not_create_workspace(tmp_path, args):
    data_root = tmp_path / "typo"
    result = review_cli(data_root, *args)
    message = (
        f"no database at {data_root / 'db' / 'self_talk_coach.sqlite'} "
        f"-- check --data-root, or run: stc init --data-root {data_root}"
    )
    assert result.exit_code == 1
    assert message in result.output
    assert result.stderr.strip() == message
    assert not data_root.exists()


def test_cli_source_segment_and_none(seeded, tmp_path):
    conn, _, _ = seeded
    conn.execute("INSERT INTO media_files (original_filename, original_path, managed_path, content_hash, "
                 "size_bytes, inferred_session_at, date_confidence, status) "
                 "VALUES ('test', 'test', 'test', 'test', 1, '2026-11-03', 'high', 'transcribed')")
    conn.execute("INSERT INTO transcripts (media_file_id, language, model, status) "
                 "VALUES (1, 'de', 'test', 'completed')")
    conn.execute("INSERT INTO transcript_segments (transcript_id, start_seconds, end_seconds, text) "
                 "VALUES (1, 1.25, 3.5, 'Segment text')")
    conn.execute("UPDATE learning_candidates SET turn_id = NULL, transcript_segment_id = 1 WHERE id = 1")
    conn.execute("UPDATE learning_candidates SET turn_id = NULL WHERE id = 2")
    conn.commit()
    result = review_cli(tmp_path, "show", "1")
    assert result.exit_code == 0
    for text in ("Segment text", "start_seconds: 1.25", "end_seconds: 3.5"):
        assert text in result.output
    assert "source: none" in review_cli(tmp_path, "show", "2").output


def test_cli_list_truncates_text_columns(seeded, tmp_path):
    conn, _, _ = seeded
    conn.execute("UPDATE learning_candidates SET original_text = ?, suggested_text = ?, producer = ? "
                 "WHERE id = 1", ("a" * 80, "b" * 80, "c" * 80))
    conn.commit()
    result = review_cli(tmp_path, "list")
    assert result.exit_code == 0
    assert "id\tstatus\ttype\tproducer\toriginal\tsuggestion" in result.output
    for char in "abc":
        assert char * 60 in result.output
        assert char * 61 not in result.output
