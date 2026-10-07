"""Conversation partner: prompt, structured reply parsing, primary/fallback LLM calls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

_SYSTEM_TEMPLATE = """Du bist ein Gesprächspartner aus Baden-Württemberg. Du sprichst mit einem Deutschlerner (Niveau B1).
Regeln:
- Kurze Antworten: 1–2 Sätze. Umgangssprachlich, natürlich, Sprachniveau B1.
- Kein Lob, keine Floskeln wie "Super!", "Toll gemacht!" oder "Gute Wahl".
- "recast": Wenn der Lerner einen Fehler gemacht hat, greif seine Aussage korrigiert in der Du-Form auf, wie ein Muttersprachler nachfragt.
  Beispiel: Lerner "Gestern ich habe bis Mitternacht gearbeitet." → recast "Ah, du hast gestern bis Mitternacht gearbeitet?"
  Keine Erklärung. Kein Fehler → null.
- "reply": NUR deine neue Frage. Wiederhole oder fasse NICHT zusammen, was der Lerner gesagt hat – das macht schon der recast.
  Falsch: recast "Ah, du hast Maschinenbau studiert?" → reply "Du hast also Maschinenbau studiert. Warum hier?"
  Richtig: recast "Ah, du hast Maschinenbau studiert?" → reply "Und warum gerade Deutschland?"
- Impuls: Zu jedem Zug bekommst du einen Impuls aus einer Liste, mit Bereich. Er ist eins von zwei Dingen:
  a) eine Frage an den Lerner (z. B. "Wie gehen Sie mit Fehlern um?") → stell sie natürlich, als Folgefrage oder als plötzlicher Themenwechsel.
  b) ein Satz, den der LERNER im Alltag sagen können soll (z. B. "Ich habe eine Frage zu meiner Anmeldung.", "Können Sie mir das per E-Mail schicken?")
     → übernimm eine passende Rolle (z. B. Mitarbeiterin im Bürgeramt, Kollegin, Verkäufer) und schaff eine Situation, in der der Lerner so einen Satz braucht. Sag den Satz nicht selbst vor.
- Erfinde nie, was der Lerner gesagt, gewollt oder gefragt hat. Schreib ihm nur zu, was wirklich im Gespräch steht.
  Verboten, wenn er es nicht gesagt hat: "Du hattest noch eine Frage zu …", "Und jetzt willst du …".
- Bittet der Lerner um Wiederholung oder hat er nicht verstanden ("Wie bitte?", "Kannst du das nochmal sagen?", "Ich habe das nicht verstanden"):
  ignoriere den Impuls und stell deine letzte Frage noch einmal, einfacher formuliert. recast null, topic_jump false.
- "starter_phrase": ein Satzanfang, mit dem der Lerner antworten könnte.
- "simpler_rephrase": dieselbe Frage einfacher formuliert.
- "topic_jump": true, wenn du das Thema plötzlich gewechselt hast.
Antworte NUR mit JSON: {{"reply": str, "recast": str|null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": bool}}
{profile_block}"""

_FENCE = re.compile(r"`{3}(?:json)?")
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+")
_WORD = re.compile(r"\w+")
_W_QUESTION = re.compile(
    r"^(wer|wen|wem|was|wann|wo|woher|wohin|warum|wieso|weshalb|wie|welche[rsmn]?|wofür|womit|worüber)$"
)
# Share of a reply sentence's words already in the recast at which it counts as an echo.
# Calibrated on real DeepSeek turns 2026-10-07: echoes 0.67–1.0, new questions 0–0.25.
_ECHO_OVERLAP = 0.6


class PartnerFormatError(ValueError):
    """The model's output could not be parsed into a PartnerTurn."""


class PartnerUnavailable(Exception):
    """Both primary and fallback models failed for one turn."""


class PartnerTurn(BaseModel):
    reply: str
    recast: str | None
    starter_phrase: str
    simpler_rephrase: str
    topic_jump: bool

    def spoken_text(self) -> str:
        return f"{self.recast or ''} {_drop_recast_echo(self.recast, self.reply)}".strip()


def _drop_recast_echo(recast: str | None, reply: str) -> str:
    """Models often open the reply by paraphrasing the recast again; speak that only once.

    The prompt forbids it, but DeepSeek did it in 6/6 probes, so the guard sits in code.
    W-questions are never dropped: "Warum hast du Maschinenbau studiert?" is a real follow-up.
    """
    if not recast:
        return reply
    first, *rest = _SENTENCE_END.split(reply.strip(), maxsplit=1)
    if not rest:
        return reply
    words = [w.lower() for w in _WORD.findall(first)]
    if not words or _W_QUESTION.match(words[0]):
        return reply
    recast_words = {w.lower() for w in _WORD.findall(recast)}
    overlap = sum(w in recast_words for w in words) / len(words)
    return rest[0] if overlap >= _ECHO_OVERLAP else reply


@dataclass(frozen=True)
class PartnerReply:
    turn: PartnerTurn
    model: str
    raw: str


class ChatClient(Protocol):
    def complete(self, model: str, messages: list[dict[str, str]], timeout: float) -> str: ...


class OpenAIChatClient:
    """OpenAI-compatible gateway client. No SDK retries: the Partner handles fallback itself."""

    def __init__(self, base_url: str, api_key: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def complete(self, model: str, messages: list[dict[str, str]], timeout: float) -> str:
        resp = self._client.chat.completions.create(
            model=model, messages=messages, temperature=0.8, max_tokens=400, timeout=timeout
        )
        if not getattr(resp, "choices", None):
            raise PartnerFormatError(f"{model}: response without choices")
        return resp.choices[0].message.content or ""


def build_system_prompt(profile: str | None) -> str:
    block = f"\nÜber den Lerner:\n{profile.strip()}" if profile and profile.strip() else ""
    return _SYSTEM_TEMPLATE.format(profile_block=block)


def parse_partner_turn(raw: str) -> PartnerTurn:
    match = _OBJECT.search(_FENCE.sub("", raw))
    if not match:
        raise PartnerFormatError(f"No JSON object in: {raw[:80]!r}")
    try:
        return PartnerTurn.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise PartnerFormatError(str(exc)) from exc


def _impulse(seed: str, section: str) -> str:
    return f"Impuls (Bereich: {section}): {seed}" if section else f"Impuls: {seed}"


def fallback_reply(seed: str) -> PartnerReply:
    turn = PartnerTurn(reply=seed, recast=None, starter_phrase="", simpler_rephrase=seed, topic_jump=True)
    return PartnerReply(turn=turn, model="none", raw="")


class Partner:
    def __init__(
        self,
        client: ChatClient,
        primary: str,
        fallback: str,
        system_prompt: str,
        timeout: float = 15.0,
        max_history: int = 12,
    ) -> None:
        self._client = client
        self._models = (primary, fallback)
        self._system = {"role": "system", "content": system_prompt}
        self._timeout = timeout
        self._max_history = max_history
        self.history: list[dict[str, str]] = []

    def opening(self, seed: str, section: str = "") -> PartnerReply:
        return self._turn(
            f"Beginne das Gespräch mit einer kurzen Begrüßung und einer Frage.\n{_impulse(seed, section)}"
        )

    def respond(self, learner_text: str, seed: str, section: str = "") -> PartnerReply:
        return self._turn(f"Lerner: {learner_text}\n{_impulse(seed, section)}")

    def _turn(self, user_content: str) -> PartnerReply:
        user = {"role": "user", "content": user_content}
        messages = [self._system, *self.history, user]
        errors: list[str] = []
        for model in self._models:
            try:
                raw = self._client.complete(model, messages, self._timeout)
                turn = parse_partner_turn(raw)
            except Exception as exc:  # noqa: BLE001 — any failure moves to the next model
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                continue
            self.history.extend([user, {"role": "assistant", "content": raw}])
            self.history = self.history[-self._max_history:]
            return PartnerReply(turn=turn, model=model, raw=raw)
        raise PartnerUnavailable("; ".join(errors))
