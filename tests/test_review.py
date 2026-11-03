import sqlite3

import pytest

from self_talk_coach import db
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
