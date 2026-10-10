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


def _turn(recast: str | None, reply: str):
    return parse_partner_turn(json.dumps({**GOOD, "recast": recast, "reply": reply}))


@pytest.mark.parametrize(
    ("recast", "reply", "spoken_reply"),
    [  # real echoes from DeepSeek V4 Pro, 2026-10-06/07
        ("Ah, du hast Maschinenbau studiert und suchst jetzt Arbeit in Deutschland?",
         "Ah, du hast Maschinenbau studiert und suchst jetzt Arbeit in Deutschland. Warum möchtest du hier arbeiten?",
         "Warum möchtest du hier arbeiten?"),
        ("Du suchst die Adresse in Stuttgart-Bad Cannstatt und willst wissen, wie du da hinkommst?",
         "Du willst also zur Adresse in Stuttgart-Bad Cannstatt? Meinst du mit der Bahn oder mit dem Auto?",
         "Meinst du mit der Bahn oder mit dem Auto?"),
        ("Du erinnerst dich nicht mehr, was du da machen musst?",
         "Du weißt also nicht mehr genau, was du da machen musst? Sollen sie dir das per E-Mail schicken?",
         "Sollen sie dir das per E-Mail schicken?"),
    ],
)
def test_spoken_text_drops_reply_sentence_that_echoes_recast(recast, reply, spoken_reply) -> None:
    assert _turn(recast, reply).spoken_text() == f"{recast} {spoken_reply}"


@pytest.mark.parametrize(
    ("recast", "reply"),
    [
        ("Ah, du hast Maschinenbau studiert?", "Warum hast du Maschinenbau studiert? Und dann?"),  # W-question is new
        ("Ah, du arbeitest seit Montag in dieser Firma?", "Was war am ersten Tag am schwierigsten?"),
        ("Ah, du arbeitest seit Montag in dieser Firma?", "Ah, du arbeitest seit Montag in dieser Firma?"),  # never empty
    ],
)
def test_spoken_text_keeps_reply_that_is_new_or_only_sentence(recast, reply) -> None:
    assert _turn(recast, reply).spoken_text() == f"{recast} {reply}"


def test_bank_section_reaches_the_model() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD), json.dumps(GOOD)]})
    partner = Partner(client, "primary", "fallback", "SYS")
    partner.opening("Ich suche diese Adresse.", section="Daily Life In Germany")
    assert "Daily Life In Germany" in client.calls[-1][1][-1]["content"]
    partner.respond("Ich weiß nicht.", "Bis wann soll ich das fertig machen?", section="Office German")
    content = client.calls[-1][1][-1]["content"]
    assert "Office German" in content and "Bis wann soll ich das fertig machen?" in content


def test_system_prompt_guards_phrase_seeds_and_repeat_requests() -> None:
    prompt = build_system_prompt(None)
    assert "Erfinde nie" in prompt  # no claims the learner never made
    assert "Rolle" in prompt  # phrase seeds become a role-play situation
    assert "Wie bitte?" in prompt  # repeat request → repeat, simpler


def test_phrase_seed_is_framed_as_role_play_question_seed_as_question() -> None:
    client = FakeClient({"primary": [json.dumps(GOOD), json.dumps(GOOD)]})
    partner = Partner(client, "primary", "fallback", "SYS")
    partner.opening("Bis wann soll ich das fertig machen?", section="Office German", phrase=True)
    content = client.calls[-1][1][-1]["content"]
    assert "Rollenspiel" in content and "nicht selbst" in content
    assert "Bis wann soll ich das fertig machen?" in content
    partner.respond("Ja.", "Wie gehen Sie mit Fehlern um?", section="Interview: Core")
    assert "Frage an den Lerner" in client.calls[-1][1][-1]["content"]


def test_openai_client_passes_max_tokens_and_temperature() -> None:
    from types import SimpleNamespace

    from self_talk_coach.conversation.partner import OpenAIChatClient

    seen: dict = {}

    def create(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    client = OpenAIChatClient("https://gw.example/v1", "k", max_tokens=3000, temperature=0.2)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert client.complete("m", [{"role": "user", "content": "x"}], 5.0) == "{}"
    assert seen["max_tokens"] == 3000 and seen["temperature"] == 0.2


def test_comprehension_impulse_replaces_seed() -> None:
    from self_talk_coach.conversation.partner import COMPREHENSION_IMPULSE

    client = FakeClient({"p": [json.dumps(GOOD)], "f": []})
    Partner(client, "p", "f", "SYS").respond("Ich arbeite.", "Hobbys?", section="S", comprehension=True)
    content = client.calls[0][1][-1]["content"]
    assert COMPREHENSION_IMPULSE in content and "Hobbys?" not in content


def test_drop_recast_removes_recast_from_spoken_text() -> None:
    client = FakeClient({"p": [json.dumps(GOOD)], "f": []})
    reply = Partner(client, "p", "f", "SYS", drop_recast=True).respond("Ich war müde.", "x")
    assert reply.turn.recast is None
    assert reply.turn.spoken_text() == GOOD["reply"]


def test_mein_tag_prompt_rules() -> None:
    from self_talk_coach.conversation.partner import build_mein_tag_prompt

    prompt = build_mein_tag_prompt("Wohnt in Reutlingen.")
    assert "Rückerstattung" in prompt  # English word taken up in German
    assert "recast" in prompt and "immer null" in prompt
    assert prompt.rstrip().endswith("Wohnt in Reutlingen.")
