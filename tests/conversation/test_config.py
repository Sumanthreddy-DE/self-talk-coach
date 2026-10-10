from pathlib import Path

import pytest

from self_talk_coach.conversation.config import ConfigError, TalkConfig
from self_talk_coach.conversation.help_ladder import LadderTimings

BASE = {
    "DEEPGRAM_API_KEY": "dg",
    "GATEWAY_BASE_URL": "https://gw.example/v1",
    "GATEWAY_API_KEY": "gw",
    "STC_QUESTION_BANKS": "C:/a/bank1.md;C:/b/bank2.md",
}


def test_defaults_and_parsing() -> None:
    cfg = TalkConfig.from_env(BASE)
    assert cfg.partner_model == "deepseek-v4-pro"
    assert cfg.fallback_model == "claude-sonnet-5"
    assert cfg.tts_voice == "de-DE-SeraphinaMultilingualNeural"
    assert cfg.question_banks == (Path("C:/a/bank1.md"), Path("C:/b/bank2.md"))
    assert cfg.ladder == LadderTimings()


def test_overrides() -> None:
    cfg = TalkConfig.from_env({**BASE, "STC_PARTNER_MODEL": "m", "STC_LADDER_SECONDS": "3,6,9"})
    assert cfg.partner_model == "m"
    assert cfg.ladder == LadderTimings(3, 6, 9)


@pytest.mark.parametrize("missing", ["DEEPGRAM_API_KEY", "GATEWAY_BASE_URL", "GATEWAY_API_KEY", "STC_QUESTION_BANKS"])
def test_missing_required_names_the_variable(missing: str) -> None:
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        TalkConfig.from_env(env)


def test_phrase_sections_default_and_override() -> None:
    assert TalkConfig.from_env(BASE).phrase_sections == ("Daily Life In Germany", "Office German", "Szenario")
    cfg = TalkConfig.from_env({**BASE, "STC_PHRASE_SECTIONS": " Beim Arzt ; ;Office "})
    assert cfg.phrase_sections == ("Beim Arzt", "Office")
    assert TalkConfig.from_env({**BASE, "STC_PHRASE_SECTIONS": ""}).phrase_sections == ()


def test_report_model_and_mein_tag_ladder_defaults() -> None:
    cfg = TalkConfig.from_env(BASE)
    assert cfg.report_model == "claude-sonnet-5"
    assert cfg.mein_tag_ladder == LadderTimings(15.0, 25.0, 35.0)


def test_mein_tag_ladder_from_env_and_invalid() -> None:
    cfg = TalkConfig.from_env({**BASE, "STC_MEIN_TAG_LADDER_SECONDS": "10,20,30", "STC_REPORT_MODEL": "m"})
    assert cfg.mein_tag_ladder == LadderTimings(10.0, 20.0, 30.0)
    assert cfg.report_model == "m"
    with pytest.raises(ConfigError, match="STC_MEIN_TAG_LADDER_SECONDS"):
        TalkConfig.from_env({**BASE, "STC_MEIN_TAG_LADDER_SECONDS": "30,20,10"})
