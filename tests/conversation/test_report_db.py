import sqlite3
from pathlib import Path

from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_conversation_candidates,
    list_turns,
    previous_conversations,
    replace_conversation_candidates,
    set_report_status,
    update_turn_out_of_baseline,
)
from self_talk_coach.domain import (
    CandidateType,
    ConversationStatus,
    NewCandidate,
    ReportStatus,
    TurnSpeaker,
)


def _conn(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "t.sqlite")
    init_db(conn)
    return conn


def _conversation(conn, scenario=None, status=ConversationStatus.COMPLETED) -> int:
    cid = insert_conversation(conn, started_at="2026-10-08T10:00:00+00:00", scenario=scenario,
                              stt_model="s", llm_model="l", tts_voice="v")
    finish_conversation(conn, cid, ended_at="2026-10-08T10:05:00+00:00", status=status)
    return cid


def test_old_db_gets_turn_id_column(tmp_path: Path) -> None:
    conn = connect(tmp_path / "old.sqlite")
    conn.execute("CREATE TABLE learning_candidates (id INTEGER PRIMARY KEY, candidate_type TEXT NOT NULL, "
                 "transcript_segment_id INTEGER, original_text TEXT NOT NULL, suggested_text TEXT, "
                 "explanation TEXT NOT NULL, severity INTEGER NOT NULL DEFAULT 1, usefulness INTEGER NOT NULL DEFAULT 1, "
                 "status TEXT NOT NULL DEFAULT 'pending', producer TEXT NOT NULL, "
                 "created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))")
    init_db(conn)
    init_db(conn)  # idempotent
    columns = [r[1] for r in conn.execute("PRAGMA table_info(learning_candidates)")]
    assert columns.count("turn_id") == 1


def test_comprehension_flag_status_ratio_and_candidates(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = _conversation(conn)
    partner = insert_turn(conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER,
                          text="Erzähl kurz nach.", comprehension_check=True)
    learner = insert_turn(conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
                          text="Ich habe einen Frage.")
    update_turn_out_of_baseline(conn, partner, 0.25)
    set_report_status(conn, cid, ReportStatus.DONE)
    first = NewCandidate(learner, CandidateType.GRAMMAR_CORRECTION, "einen Frage", "eine Frage", "Kasus/Artikel: Frage is feminine")
    replace_conversation_candidates(conn, cid, [first])
    replace_conversation_candidates(conn, cid, [first])  # rerun replaces, never duplicates

    turns = list_turns(conn, cid)
    assert turns[0]["comprehension_check"] == 1 and turns[1]["comprehension_check"] == 0
    assert turns[0]["out_of_baseline_ratio"] == 0.25
    assert get_conversation(conn, cid)["report_status"] == "done"
    rows = list_conversation_candidates(conn, cid)
    assert len(rows) == 1
    assert rows[0]["turn_id"] == learner and rows[0]["producer"] == "conversation"
    assert rows[0]["candidate_type"] == "grammar_correction" and rows[0]["suggested_text"] == "eine Frage"


def test_previous_conversations_completed_only_excluding_scenario(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    a = _conversation(conn)
    _conversation(conn, status=ConversationStatus.ABORTED)
    _conversation(conn, scenario="Mein Tag")
    b = _conversation(conn, scenario="McDonald's")
    current = _conversation(conn)
    ids = [r["id"] for r in previous_conversations(conn, current, exclude_scenario="Mein Tag")]
    assert ids == [b, a]
