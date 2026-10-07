import json

import pytest

from self_talk_coach.conversation.partner import (
    Partner,
    PartnerFormatError,
    PartnerUnavailable,
    build_system_prompt,
    fallback_reply,
    parse_partner_turn,
)

GOOD = {
    "reply": "Wann schläfst du dann?",
    "recast": "Ah, du hast gestern bis Mitternacht gearbeitet?",
    "starter_phrase": "Normalerweise gehe ich um …",
    "simpler_rephrase": "Wann gehst du schlafen?",
    "topic_jump": False,
}


class FakeClient:
    def __init__(self, script: dict[str, list]) -> None:
        self.script = script
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, model, messages, timeout):
        self.calls.append((model, [dict(m) for m in messages]))
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_parse_handles_fences_and_prose() -> None:
    raw = "Hier:\n```json\n" + json.dumps(GOOD) + "\n```"
    turn = parse_partner_turn(raw)
    assert turn.reply == GOOD["reply"]
    assert turn.spoken_text() == GOOD["recast"] + " " + GOOD["reply"]


def test_parse_rejects_garbage() -> None:
    with pytest.raises(PartnerFormatError):
        parse_partner_turn("Biryani ist lecker – gute Wahl.")


def test_spoken_text_without_recast() -> None:
    turn = parse_partner_turn(json.dumps({**GOOD, "recast": None}))
    assert turn.spoken_text() == GOOD["reply"]


def test_system_prompt_rules_and_profile() -> None:
    prompt = build_system_prompt("Wohnort: Reutlingen")
    assert "Wohnort: Reutlingen" in prompt
    assert "du hast" in prompt  # second-person recast example
    assert "Kein Lob" in prompt
    assert build_system_prompt(None)


def test_primary_success_records_history() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD), json.dumps(GOOD)]})
    partner = Partner(client, "primary", "fallback", "SYS")
    first = partner.opening("Arbeit")
    assert first.model == "primary"
    partner.respond("Ich habe gestern gearbeitet.", "Schlaf")
    _, messages = client.calls[-1]
    assert messages[0] == {"role": "system", "content": "SYS"}
    assert messages[-1]["role"] == "user"
    assert "Ich habe gestern gearbeitet." in messages[-1]["content"]
    assert "Schlaf" in messages[-1]["content"]
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]


def test_falls_back_on_error_and_on_bad_json() -> None:
    client = FakeClient({
        "primary": [TimeoutError("slow"), "kein json"],
        "fallback": [json.dumps(GOOD), json.dumps(GOOD)],
    })
    partner = Partner(client, "primary", "fallback", "SYS")
    assert partner.opening("Arbeit").model == "fallback"
    assert partner.respond("Hallo", "Essen").model == "fallback"


def test_both_fail_raises_unavailable_and_history_stays_clean() -> None:
    client = FakeClient({"primary": [RuntimeError("x")], "fallback": [RuntimeError("y")]})
    partner = Partner(client, "primary", "fallback", "SYS")
    with pytest.raises(PartnerUnavailable):
        partner.opening("Arbeit")
    assert partner.history == []


def test_history_is_capped() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD)] * 10})
    partner = Partner(client, "primary", "fallback", "SYS", max_history=4)
    for i in range(10):
        partner.respond(f"Satz {i}", "Thema")
    assert len(partner.history) == 4
    assert "Satz 9" in partner.history[-2]["content"]


def test_fallback_reply_uses_seed() -> None:
    reply = fallback_reply("Was kochst du gern?")
    assert reply.turn.reply == "Was kochst du gern?"
    assert reply.model == "none"
