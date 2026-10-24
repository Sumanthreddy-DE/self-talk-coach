"""One live conversation: partner speaks, learner answers, help ladder and listening aids, per-turn storage."""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from self_talk_coach.conversation.audio_store import SAMPLE_RATE, encode_opus, wav_bytes
from self_talk_coach.conversation.help_ladder import (
    NUDGE_PHRASES,
    NUDGE_PHRASES_SIE,
    LadderStep,
    LadderTimings,
    step_for,
)
from self_talk_coach.conversation.partner import PartnerReply, PartnerUnavailable, fallback_reply, is_interview
from self_talk_coach.conversation.question_bank import Deck, Seed
from self_talk_coach.conversation.stt import LearnerTranscriber, LearnerTranscript
from self_talk_coach.conversation.tts import Voice
from self_talk_coach.db import (
    finish_conversation,
    insert_conversation,
    insert_turn,
    update_turn_listening,
)
from self_talk_coach.domain import ConversationStatus, TurnSpeaker
from self_talk_coach.paths import AppPaths

PARDON = "Wie bitte? Kannst du das nochmal sagen?"
PARDON_SIE = "Wie bitte? Können Sie das noch einmal sagen?"
MIN_SPEECH_SECONDS = 0.4
POLL_SECONDS = 0.05
MAX_RECORD_SECONDS = 60.0
INTERVIEW_MAX_RECORD_SECONDS = 120.0  # interview answers run long; 60 s cut one off mid-sentence
COMPREHENSION_EVERY = 4  # every Nth partner turn retells instead of asking (0 = off)
KEYS = "t = Text · f = Szenarien · w = nächstes · q = Ende"
# Keys that cut playback short; the key is then handled as if pressed while waiting.
INTERRUPT_KEYS = frozenset({" ", "q", "r", "s", "w", "f"})


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class KeyInput(Protocol):
    def poll(self) -> str | None: ...


class Recorder(Protocol):
    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...


class Player(Protocol):
    def start(self, audio: bytes) -> None: ...
    def is_playing(self) -> bool: ...
    def stop(self) -> None: ...


@dataclass
class SessionDeps:
    partner: Any
    transcriber: LearnerTranscriber
    voice: Voice
    player: Player
    recorder: Recorder
    keys: KeyInput
    clock: Clock
    picker: Deck
    conn: sqlite3.Connection
    paths: AppPaths
    ladder: LadderTimings
    rng: random.Random
    now_iso: Callable[[], str]
    store_audio: Callable[[bytes, Path], None] = encode_opus
    out: Callable[[str], None] = print
    status: Callable[[str], None] = print
    max_record_seconds: float = MAX_RECORD_SECONDS
    comprehension_every: int = COMPREHENSION_EVERY


@dataclass
class _Window:
    """Learner-side state for one partner turn, kept across pardon retries."""

    quit: bool = False
    switch: bool = False  # 'w' or the 'f' menu: leave this scenario
    switch_to: int | None = None  # menu option chosen with 'f'; None = next scenario
    freeze_seconds: float | None = None
    ladder_step: int = 0
    replay: int = 0
    slower: int = 0
    show_text: int = 0


@dataclass
class _State:
    conversation_id: int = 0
    turn_index: int = 0
    seed_text: str = ""
    reply: PartnerReply | None = None
    audio: bytes = b""
    partner_turns: int = 0
    check: bool = False  # current partner turn is a comprehension check
    interview: bool = False  # current section is a job interview: helpers say "Sie"
    picked: Seed | None = None  # bank seed behind the current partner turn


class ConversationSession:
    def __init__(self, deps: SessionDeps, scenario: str | None, llm_label: str) -> None:
        self._d = deps
        self._scenario = scenario
        self._llm_label = llm_label
        self._s = _State()
        self._pending_key: str | None = None

    def run(self) -> int:
        d = self._d
        self._s.conversation_id = insert_conversation(
            d.conn,
            started_at=d.now_iso(),
            scenario=self._scenario,
            stt_model=d.transcriber.model_name,
            llm_model=self._llm_label,
            tts_voice=d.voice.name,
        )
        status = ConversationStatus.COMPLETED
        try:
            self._partner_turn(opening=True, learner_text="")
            while True:
                window = _Window()
                partner_turn_id = self._speak_and_store_partner(window)
                transcript: LearnerTranscript | None = None
                while transcript is None and not window.quit and not window.switch:
                    self._wait_for_learner(window)  # after a pardon: same partner turn, fresh timer
                    if not window.quit and not window.switch:
                        transcript = self._record_and_transcribe(window.freeze_seconds)
                update_turn_listening(
                    d.conn, partner_turn_id,
                    ladder_step_reached=window.ladder_step, replay_count=window.replay,
                    slower_count=window.slower, show_text_count=window.show_text,
                )
                if window.switch:
                    label = d.picker.switch() if window.switch_to is None else d.picker.choose(window.switch_to)
                    d.status(f"[Szenario] {label}")
                    d.partner.reset()
                    self._partner_turn(opening=True, learner_text="")
                    continue
                if transcript is None:
                    break
                self._partner_turn(opening=False, learner_text=transcript.text)
        except KeyboardInterrupt:
            status = ConversationStatus.ABORTED
        except Exception:
            # A crash must not leave the conversation 'active' with no end time.
            finish_conversation(d.conn, self._s.conversation_id, ended_at=d.now_iso(),
                                status=ConversationStatus.ABORTED)
            raise
        finish_conversation(d.conn, self._s.conversation_id, ended_at=d.now_iso(), status=status)
        return self._s.conversation_id

    # --- partner side -------------------------------------------------------

    def _partner_turn(self, *, opening: bool, learner_text: str) -> None:
        every = self._d.comprehension_every
        check = not opening and every > 0 and (self._s.partner_turns + 1) % every == 0
        # A check asks no bank question, so it must not use one up: interview questions would be skipped.
        picked = self._s.picked if check and self._s.picked else self._d.picker.next()
        seed = picked.text
        try:
            if opening:
                reply = self._d.partner.opening(seed, section=picked.section, phrase=picked.phrase)
            else:
                reply = self._d.partner.respond(
                    learner_text, seed, section=picked.section, phrase=picked.phrase, comprehension=check
                )
        except PartnerUnavailable as exc:
            self._d.status(f"[Hinweis] KI-Partner nicht erreichbar, ich lese die Frage aus der Liste vor. Grund: {str(exc)[:160]}")
            if check:  # the fallback reads a bank question aloud: take a fresh one, not the last
                picked = self._d.picker.next()
                seed = picked.text
            reply = fallback_reply(seed)
            check = False
        self._s.partner_turns += 1
        self._s.check = check
        self._s.seed_text = seed
        self._s.picked = picked
        self._s.interview = is_interview(picked.section)
        self._s.reply = reply
        self._s.audio = self._say(reply.turn.spoken_text(), announce=False)

    def _speak_and_store_partner(self, window: _Window) -> int:
        d, s = self._d, self._s
        assert s.reply is not None
        d.status("[Partner spricht] SPACE = unterbrechen · r = nochmal · s = langsamer · t = Text · f = Szenarien · w = nächstes · q = Ende")
        if not s.audio:  # voice failed: the learner reads instead of listening
            d.out(f"Partner: {s.reply.turn.spoken_text()}")
        self._play(s.audio, window)
        index = self._next_index()
        audio_path = self._store(s.audio, index, "partner") if s.audio else None
        return insert_turn(
            d.conn,
            conversation_id=s.conversation_id,
            turn_index=index,
            speaker=TurnSpeaker.PARTNER,
            text=s.reply.turn.spoken_text(),
            audio_path=str(audio_path) if audio_path else None,
            seed=s.seed_text,
            partner_turn_json=s.reply.turn.model_dump_json(),
            llm_model=s.reply.model,
            comprehension_check=s.check,
        )

    # --- waiting for the learner -------------------------------------------

    def _wait_for_learner(self, window: _Window) -> None:
        """Wait for SPACE (or q); counts listening aids and fires the ladder into `window`."""
        d, s = self._d, self._s
        assert s.reply is not None
        spoken = s.reply.turn.spoken_text()
        d.status("[Du bist dran] SPACE = sprechen · r = nochmal · s = langsamer · t = Text · f = Szenarien · w = nächstes · q = Ende")
        started = d.clock.now()
        while True:
            key = self._next_key()
            if key == " ":
                window.freeze_seconds = round(d.clock.now() - started, 2)
                return
            if key == "q":
                window.quit = True
                return
            if key == "w":
                window.switch = True
                return
            if key == "f":
                choice = self._scenario_menu()
                if choice is not None:
                    window.switch, window.switch_to = True, choice
                    return
                d.status("[Du bist dran] SPACE = sprechen · r = nochmal · s = langsamer · " + KEYS)
                started = d.clock.now()  # menu time is not freeze time
            if key == "r":
                window.replay += 1
                self._play(s.audio, window)
            elif key == "s":
                window.slower += 1
                self._play(self._say(spoken, slower=True), window)
            elif key == "t":
                self._show_text(window)
            target = step_for(d.clock.now() - started, d.ladder)
            if target > window.ladder_step:
                window.ladder_step = int(target)
                helper = self._helper_text(target)
                if helper:
                    self._play(self._say(helper), window)
            d.clock.sleep(POLL_SECONDS)

    def _scenario_menu(self) -> int | None:
        """List scenarios ('>' = current); number + Enter picks one, Enter alone or Esc goes back."""
        d = self._d
        d.out("[Szenarien]")
        for i, name in enumerate(d.picker.options()):
            d.out(f"{'>' if i == d.picker.current_option else ' '} {i:2}  {name}")
        d.status("Nummer + Enter = wechseln · Enter = zurück")
        digits = ""
        while True:
            key = d.keys.poll()
            if key in ("\r", "\n", "\x1b"):
                break
            if key is not None and key.isdigit():
                digits += key
                d.status(f"Auswahl: {digits}")
            d.clock.sleep(POLL_SECONDS)
        if key == "\x1b" or not digits:
            return None
        if int(digits) < len(d.picker.options()):
            return int(digits)
        d.status(f"Keine Nummer {digits} — weiter im aktuellen Szenario.")
        return None

    def _helper_text(self, step: LadderStep) -> str:
        assert self._s.reply is not None
        turn = self._s.reply.turn
        if step == LadderStep.NUDGE:
            return self._d.rng.choice(NUDGE_PHRASES_SIE if self._s.interview else NUDGE_PHRASES)
        if step == LadderStep.STARTER:
            return turn.starter_phrase
        if step == LadderStep.REPHRASE:
            return turn.simpler_rephrase
        return ""

    # --- learner side --------------------------------------------------------

    def _record_and_transcribe(self, freeze_seconds: float | None) -> LearnerTranscript | None:
        d, s = self._d, self._s
        d.recorder.start()
        d.status("[Aufnahme] ... SPACE = Stopp")
        limit = max(d.max_record_seconds, INTERVIEW_MAX_RECORD_SECONDS) if s.interview else d.max_record_seconds
        record_started = d.clock.now()
        stopped = False
        while d.clock.now() - record_started < limit:
            if d.keys.poll() == " ":
                stopped = True
                break
            d.clock.sleep(POLL_SECONDS)
        samples = d.recorder.stop()
        if not stopped:
            d.status(f"[Hinweis] Aufnahme nach {limit:.0f} s automatisch gestoppt.")
        d.status("[...] Partner denkt nach")
        if len(samples) < MIN_SPEECH_SECONDS * SAMPLE_RATE:
            self._play(self._say(PARDON_SIE if s.interview else PARDON))
            return None
        audio = wav_bytes(samples)
        transcript = self._transcribe_with_retry(audio)
        if transcript is None or not transcript.text.strip():
            self._play(self._say(PARDON_SIE if s.interview else PARDON))
            return None
        index = self._next_index()
        audio_path = self._store(audio, index, "learner")
        insert_turn(
            d.conn,
            conversation_id=s.conversation_id,
            turn_index=index,
            speaker=TurnSpeaker.LEARNER,
            text=transcript.text,
            audio_path=str(audio_path),
            words_json=transcript.words_json(),
            freeze_seconds=freeze_seconds,
        )
        d.out(f"(du) {transcript.text}")
        return transcript

    def _transcribe_with_retry(self, audio: bytes) -> LearnerTranscript | None:
        for _ in range(2):
            try:
                return self._d.transcriber.transcribe(audio)
            except Exception:  # noqa: BLE001 — network/API failure: retry once, then pardon
                continue
        return None

    # --- helpers -------------------------------------------------------------

    def _say(self, text: str, slower: bool = False, announce: bool = True) -> bytes:
        """Synthesize `text`; if the voice service fails, say so and show the text instead (b"" = nothing to play).

        `announce=False`: the caller prints the text itself (partner turns, at speaking time).
        """
        try:
            return self._d.voice.synthesize(text, slower=slower)
        except Exception as exc:  # noqa: BLE001 — edge-tts is an unofficial endpoint; any failure falls back to text
            self._d.status(f"[Hinweis] Sprachausgabe fehlgeschlagen, ich zeige den Text. Grund: {type(exc).__name__}: {str(exc)[:120]}")
            if announce:
                self._d.out(f"Partner: {text}")
            return b""

    def _play(self, audio: bytes, window: _Window | None = None) -> None:
        """Play partner audio while polling keys.

        't' shows the text and playback goes on; an INTERRUPT_KEYS key stops playback and is
        queued for `_wait_for_learner`. Other keys are dropped. A key pressed as playback ends
        stays in the buffer for `_wait_for_learner` instead of being flushed away.
        """
        d = self._d
        if not audio:
            return
        d.player.start(audio)
        while d.player.is_playing():
            key = d.keys.poll()
            if key == "t" and window is not None:
                self._show_text(window)
            elif key in INTERRUPT_KEYS:
                d.player.stop()
                self._pending_key = key
                break
            d.clock.sleep(POLL_SECONDS)

    def _next_key(self) -> str | None:
        key, self._pending_key = self._pending_key, None
        return key if key is not None else self._d.keys.poll()

    def _show_text(self, window: _Window) -> None:
        assert self._s.reply is not None
        window.show_text += 1
        self._d.out(f"Partner: {self._s.reply.turn.spoken_text()}")

    def _next_index(self) -> int:
        index = self._s.turn_index
        self._s.turn_index += 1
        return index

    def _store(self, audio: bytes, index: int, speaker: str) -> Path:
        dest = self._d.paths.conversation_dir(self._s.conversation_id) / f"turn-{index:03d}-{speaker}.opus"
        self._d.store_audio(audio, dest)
        return dest
