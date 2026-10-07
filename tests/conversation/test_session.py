import json
import random
from pathlib import Path

import numpy as np

from self_talk_coach.conversation.help_ladder import NUDGE_PHRASES, LadderTimings
from self_talk_coach.conversation.partner import PartnerReply, PartnerTurn, PartnerUnavailable
from self_talk_coach.conversation.question_bank import ScenarioDeck, Seed
from self_talk_coach.conversation.session import PARDON, ConversationSession, SessionDeps
from self_talk_coach.conversation.stt import LearnerTranscript
from self_talk_coach.db import connect, get_conversation, init_db, list_turns
from self_talk_coach.paths import AppPaths


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t = round(self.t + seconds, 6)


class FakeKeys:
    """Returns each scripted key once the fake clock reaches its time."""

    def __init__(self, clock: FakeClock, script: list[tuple[float, str]]) -> None:
        self.clock = clock
        self.script = list(script)

    def poll(self):
        if self.script and self.clock.now() >= self.script[0][0]:
            return self.script.pop(0)[1]
        return None


class FakeRecorder:
    def __init__(self, seconds: list[float]) -> None:
        self.seconds = list(seconds)

    def start(self) -> None:
        pass

    def stop(self):
        return np.zeros(int(16000 * self.seconds.pop(0)), dtype="float32")


class FakePlayer:
    """Plays instantly: playback is over before the first key poll."""

    def __init__(self) -> None:
        self.played: list[bytes] = []
        self.stopped = 0

    def start(self, audio: bytes) -> None:
        self.played.append(audio)

    def is_playing(self) -> bool:
        return False

    def stop(self) -> None:
        self.stopped += 1


class FakeVoice:
    name = "fake-voice"

    def synthesize(self, text: str, slower: bool = False) -> bytes:
        return f"{'SLOW:' if slower else ''}{text}".encode()


class FakeTranscriber:
    model_name = "fake-stt"

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript:
        return LearnerTranscript(text=self.texts.pop(0), words=(), model=self.model_name)


def _reply(reply: str, recast: str | None = None) -> PartnerReply:
    turn = PartnerTurn(reply=reply, recast=recast, starter_phrase=f"START {reply}",
                       simpler_rephrase=f"SIMPLE {reply}", topic_jump=False)
    return PartnerReply(turn=turn, model="deepseek-v4-pro", raw=turn.model_dump_json())


class FakePartner:
    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.learner_texts: list[str] = []
        self.sections: list[str] = []
        self.phrases: list[bool] = []
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1

    def opening(self, seed: str, section: str = "", phrase: bool = False) -> PartnerReply:
        self.sections.append(section)
        self.phrases.append(phrase)
        return self._next()

    def respond(self, learner_text: str, seed: str, section: str = "", phrase: bool = False) -> PartnerReply:
        self.learner_texts.append(learner_text)
        self.sections.append(section)
        self.phrases.append(phrase)
        return self._next()

    def _next(self) -> PartnerReply:
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _deps(tmp_path: Path, keys_script, recordings, texts, replies):
    clock = FakeClock()
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    stored: list[Path] = []
    out: list[str] = []
    player = FakePlayer()
    deps = SessionDeps(
        partner=FakePartner(replies),
        transcriber=FakeTranscriber(texts),
        voice=FakeVoice(),
        player=player,
        recorder=FakeRecorder(recordings),
        keys=FakeKeys(clock, keys_script),
        clock=clock,
        picker=ScenarioDeck([Seed("S", "Arbeit"), Seed("S", "Essen"), Seed("S", "Wohnung")], None, random.Random(0)),
        conn=conn,
        paths=AppPaths.from_data_root(tmp_path),
        ladder=LadderTimings(),
        rng=random.Random(0),
        store_audio=lambda audio, dest: stored.append(dest),
        out=out.append,
        status=lambda line: None,
        now_iso=lambda: "2026-10-05T20:00:00+00:00",
    )
    return deps, conn, player, stored, out


def test_full_exchange_with_ladder_aids_and_quit(tmp_path: Path) -> None:
    deps, conn, player, stored, out = _deps(
        tmp_path,
        keys_script=[(1.0, "r"), (2.0, "t"), (3.0, "s"), (5.0, " "), (7.0, " "), (9.0, "q")],
        recordings=[2.0],
        texts=["Gestern ich habe gearbeitet."],
        replies=[_reply("Was machst du beruflich?"),
                 _reply("Bis wann?", recast="Ah, du hast gestern gearbeitet?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="deepseek-v4-pro").run()

    turns = list_turns(conn, cid)
    assert [t["speaker"] for t in turns] == ["partner", "learner", "partner"]
    first, learner, second = turns
    assert first["text"] == "Was machst du beruflich?"
    assert first["replay_count"] == 1 and first["show_text_count"] == 1 and first["slower_count"] == 1
    assert first["ladder_step_reached"] == 1  # nudge at 4 s, spoke at 5 s
    assert learner["freeze_seconds"] == 5.0
    assert deps.partner.sections == ["S", "S"]  # bank section travels with each seed
    assert deps.partner.phrases == [False, False]
    assert learner["text"] == "Gestern ich habe gearbeitet."
    assert second["text"] == "Ah, du hast gestern gearbeitet? Bis wann?"
    assert second["seed"] is not None
    assert json.loads(second["partner_turn_json"])["recast"] == "Ah, du hast gestern gearbeitet?"
    assert get_conversation(conn, cid)["status"] == "completed"
    assert deps.partner.learner_texts == ["Gestern ich habe gearbeitet."]

    assert b"SLOW:Was machst du beruflich?" in player.played
    assert any(p.decode() in NUDGE_PHRASES for p in player.played)
    # partner text only on 't', helpers never printed; learner sees own transcript to spot mishearing
    assert out == ["Partner: Was machst du beruflich?", "(du) Gestern ich habe gearbeitet."]
    assert len(stored) == 3
    assert all(str(p).endswith(".opus") for p in stored)


def test_ladder_reaches_rephrase_and_speaks_helpers(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _deps(
        tmp_path, keys_script=[(13.0, "q")], recordings=[], texts=[],
        replies=[_reply("Was kochst du gern?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert list_turns(conn, cid)[0]["ladder_step_reached"] == 3
    assert b"START Was kochst du gern?" in player.played
    assert b"SIMPLE Was kochst du gern?" in player.played


def test_too_short_recording_gets_pardon_and_no_llm_call(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (1.1, " "), (2.0, " "), (4.0, " "), (6.0, "q")],
        recordings=[0.1, 2.0],
        texts=["Ich koche gern Biryani."],
        replies=[_reply("Was kochst du gern?"), _reply("Mit Hähnchen?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert PARDON.encode() in player.played
    assert deps.partner.learner_texts == ["Ich koche gern Biryani."]
    assert [t["speaker"] for t in list_turns(conn, cid)] == ["partner", "learner", "partner"]


def test_partner_unavailable_falls_back_to_seed_question(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, " "), (3.0, " "), (5.0, "q")],
        recordings=[2.0],
        texts=["Ich wohne in Reutlingen."],
        replies=[_reply("Wo wohnst du?"), PartnerUnavailable("deepseek: 429 plan expired")],
    )
    status: list[str] = []
    deps.status = status.append
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    # the fallback must be visible, with the reason, never silent
    assert any("nicht erreichbar" in line and "429 plan expired" in line for line in status)
    last = list_turns(conn, cid)[-1]
    assert last["speaker"] == "partner"
    assert last["llm_model"] == "none"
    assert last["seed"] == last["text"]


def test_keyboard_interrupt_marks_aborted(tmp_path: Path) -> None:
    deps, conn, _, _, _ = _deps(tmp_path, keys_script=[], recordings=[], texts=[],
                                replies=[_reply("Hallo?")])

    def boom() -> None:
        raise KeyboardInterrupt

    deps.keys.poll = boom
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()
    assert get_conversation(conn, cid)["status"] == "aborted"
    assert len(list_turns(conn, cid)) == 1


class TimedPlayer(FakePlayer):
    """Playback takes fake-clock time, like sd.play running in the background."""

    def __init__(self, clock: FakeClock, seconds_per_play: float) -> None:
        super().__init__()
        self.clock = clock
        self.seconds = seconds_per_play
        self.ends_at = 0.0

    def start(self, audio: bytes) -> None:
        super().start(audio)
        self.ends_at = round(self.clock.t + self.seconds, 6)

    def is_playing(self) -> bool:
        return self.clock.t < self.ends_at

    def stop(self) -> None:
        super().stop()
        self.ends_at = self.clock.t


def _timed(tmp_path: Path, keys_script, recordings=(), texts=(), replies=()):
    deps, conn, _, _, out = _deps(tmp_path, keys_script, list(recordings), list(texts), list(replies))
    player = TimedPlayer(deps.clock, seconds_per_play=3.0)
    deps.player = player
    status: list[str] = []
    deps.status = status.append
    return deps, conn, player, out, status


def test_space_while_partner_speaks_interrupts_and_starts_recording(tmp_path: Path) -> None:
    # Partner audio would play 0-3 s; SPACE at 1.0 s cuts it and records straight away.
    deps, conn, player, _, status = _timed(
        tmp_path,
        keys_script=[(1.0, " "), (2.0, " "), (8.0, "q")],
        recordings=[1.0],
        texts=["Ich wohne in Reutlingen."],
        replies=[_reply("Wo wohnst du?"), _reply("Seit wann?")],
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()

    turns = list_turns(conn, cid)
    assert [t["speaker"] for t in turns] == ["partner", "learner", "partner"]
    assert player.stopped >= 1
    assert turns[1]["freeze_seconds"] == 0.0  # learner barged in, no freeze
    assert any("unterbrechen" in line for line in status)
    assert any("Aufnahme" in line for line in status)


def test_q_while_partner_speaks_ends_conversation_at_once(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _timed(tmp_path, keys_script=[(1.0, "q")], replies=[_reply("Wo wohnst du?")])
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()

    assert [t["speaker"] for t in list_turns(conn, cid)] == ["partner"]
    assert player.stopped == 1
    assert deps.clock.now() < 2.0  # did not sit through the rest of the audio


def test_s_while_partner_speaks_restarts_slower(tmp_path: Path) -> None:
    deps, conn, player, _, _ = _timed(
        tmp_path, keys_script=[(1.0, "s"), (4.5, "q")], replies=[_reply("Wo wohnst du?")]
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()

    assert player.played[:2] == [b"Wo wohnst du?", b"SLOW:Wo wohnst du?"]
    assert player.stopped == 1
    assert list_turns(conn, cid)[0]["slower_count"] == 1


def test_t_while_partner_speaks_shows_text_without_stopping(tmp_path: Path) -> None:
    deps, conn, player, out, _ = _timed(
        tmp_path, keys_script=[(1.0, "t"), (10.0, "q")], replies=[_reply("Wo wohnst du?")]
    )
    cid = ConversationSession(deps, scenario=None, llm_label="x").run()

    assert out == ["Partner: Wo wohnst du?"]
    assert player.stopped == 0
    assert list_turns(conn, cid)[0]["show_text_count"] == 1


def test_w_switches_to_next_scenario_with_fresh_partner(tmp_path: Path) -> None:


    deps, conn, _, _, _ = _deps(
        tmp_path,
        keys_script=[(1.0, "w"), (3.0, "q")],
        recordings=[],
        texts=[],
        replies=[_reply("Was arbeitest du?"), _reply("Was isst du gern?")],
    )
    deps.picker = ScenarioDeck([Seed("A", "Arbeit"), Seed("B", "Essen")], "A", random.Random(0))
    status: list[str] = []
    deps.status = status.append
    cid = ConversationSession(deps, scenario="A", llm_label="x").run()

    assert deps.partner.sections == ["A", "B"]  # both are openings: new scene starts fresh
    assert deps.partner.resets == 1
    assert "[Szenario] B" in status
    assert [t["text"] for t in list_turns(conn, cid)] == ["Was arbeitest du?", "Was isst du gern?"]
