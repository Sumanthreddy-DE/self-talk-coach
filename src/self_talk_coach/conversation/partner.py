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
  Keine Erklärung. Kein Fehler → null. "reply" wiederholt den recast nicht.
- "reply": danach eine Frage zum vorgegebenen Thema, als natürliche Folgefrage oder als plötzlicher Themenwechsel.
- "starter_phrase": ein Satzanfang, mit dem der Lerner antworten könnte.
- "simpler_rephrase": dieselbe Frage einfacher formuliert.
- "topic_jump": true, wenn du das Thema plötzlich gewechselt hast.
Antworte NUR mit JSON: {{"reply": str, "recast": str|null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": bool}}
{profile_block}"""

_FENCE = re.compile(r"`{3}(?:json)?")
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


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
        return f"{self.recast or ''} {self.reply}".strip()


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

    def opening(self, seed: str) -> PartnerReply:
        return self._turn(f"Beginne das Gespräch mit einer kurzen Begrüßung und einer Frage. Thema: {seed}")

    def respond(self, learner_text: str, seed: str) -> PartnerReply:
        return self._turn(f"Lerner: {learner_text}\nNächstes Thema: {seed}")

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
