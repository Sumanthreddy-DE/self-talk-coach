"""Conversation settings from environment (.env)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from self_talk_coach.conversation.help_ladder import LadderTimings

_REQUIRED = ("DEEPGRAM_API_KEY", "GATEWAY_BASE_URL", "GATEWAY_API_KEY", "STC_QUESTION_BANKS")


class ConfigError(Exception):
    """A required setting is missing or invalid."""


@dataclass(frozen=True)
class TalkConfig:
    deepgram_api_key: str
    gateway_base_url: str
    gateway_api_key: str
    partner_model: str
    fallback_model: str
    tts_voice: str
    question_banks: tuple[Path, ...]
    ladder: LadderTimings

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> TalkConfig:
        missing = [name for name in _REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise ConfigError(f"Missing in .env: {', '.join(missing)}")
        try:
            ladder = LadderTimings.from_csv(env.get("STC_LADDER_SECONDS", "4,8,12"))
        except ValueError as exc:
            raise ConfigError(f"STC_LADDER_SECONDS: {exc}") from exc
        return cls(
            deepgram_api_key=env["DEEPGRAM_API_KEY"].strip(),
            gateway_base_url=env["GATEWAY_BASE_URL"].strip(),
            gateway_api_key=env["GATEWAY_API_KEY"].strip(),
            partner_model=env.get("STC_PARTNER_MODEL", "deepseek-v4-pro"),
            fallback_model=env.get("STC_FALLBACK_MODEL", "claude-sonnet-5"),
            tts_voice=env.get("STC_TTS_VOICE", "de-DE-SeraphinaMultilingualNeural"),
            question_banks=tuple(Path(p.strip()) for p in env["STC_QUESTION_BANKS"].split(";") if p.strip()),
            ladder=ladder,
        )
