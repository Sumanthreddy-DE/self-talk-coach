from pathlib import Path

from self_talk_coach.db import (
    connect,
    finish_conversation,
    get_conversation,
    init_db,
    insert_conversation,
    insert_turn,
    list_turns,
    update_turn_listening,
)
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.paths import AppPaths


def _conn(tmp_path: Path):
    conn = connect(tmp_path / "t.sqlite")
    init_db(conn)
    return conn


def test_conversation_lifecycle(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = insert_conversation(
        conn,
        started_at="2026-10-05T20:00:00+00:00",
        scenario=None,
        stt_model="deepgram:nova-3:de",
        llm_model="deepseek-v4-pro",
        tts_voice="de-DE-SeraphinaMultilingualNeural",
    )
    row = get_conversation(conn, cid)
    assert row["status"] == "active"
    assert row["report_status"] == "pending"

    finish_conversation(conn, cid, ended_at="2026-10-05T20:10:00+00:00", status=ConversationStatus.COMPLETED)
    row = get_conversation(conn, cid)
    assert row["status"] == "completed"
    assert row["ended_at"] == "2026-10-05T20:10:00+00:00"


def test_turns_insert_update_and_order(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    cid = insert_conversation(
        conn, started_at="x", scenario="Interview: Core", stt_model="s", llm_model="l", tts_voice="v"
    )
    learner_id = insert_turn(
        conn, conversation_id=cid, turn_index=1, speaker=TurnSpeaker.LEARNER,
        text="Ich habe einen Frage.", audio_path="a.opus", words_json="[]", freeze_seconds=5.2,
    )
    partner_id = insert_turn(
        conn, conversation_id=cid, turn_index=0, speaker=TurnSpeaker.PARTNER,
        text="Was machst du?", seed="Arbeit", partner_turn_json="{}", llm_model="deepseek-v4-pro",
    )
    update_turn_listening(conn, partner_id, ladder_step_reached=2, replay_count=1, slower_count=0, show_text_count=3)

    turns = list_turns(conn, cid)
    assert [t["turn_index"] for t in turns] == [0, 1]
    assert turns[0]["id"] == partner_id
    assert turns[0]["ladder_step_reached"] == 2
    assert turns[0]["show_text_count"] == 3
    assert turns[1]["id"] == learner_id
    assert turns[1]["freeze_seconds"] == 5.2
    assert turns[1]["speaker"] == "learner"


def test_conversation_paths(tmp_path: Path) -> None:
    paths = AppPaths.from_data_root(tmp_path)
    assert paths.conversations_root == tmp_path / "conversations"
    assert paths.conversation_dir(7) == tmp_path / "conversations" / "0007"
    assert paths.learner_profile_path == tmp_path / "learner-profile.md"
    paths.ensure_workspace()
    assert paths.conversations_root.is_dir()
