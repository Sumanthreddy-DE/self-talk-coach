import pytest

from self_talk_coach.cli import median_freeze


def test_median_freeze_averages_middle_pair_for_even_count() -> None:
    turns = [{"freeze_seconds": 1.26}, {"freeze_seconds": None}, {"freeze_seconds": 22.75}]
    assert median_freeze(turns) == pytest.approx(12.005)


def test_median_freeze_odd_count_and_empty() -> None:
    assert median_freeze([{"freeze_seconds": s} for s in (5.0, 1.0, 3.0)]) == 3.0
    assert median_freeze([{"freeze_seconds": None}]) is None


def test_choose_start_scenario_by_number_reasks_on_bad_input_enter_is_mixed() -> None:
    import random

    from self_talk_coach.cli import choose_start_scenario
    from self_talk_coach.conversation.question_bank import ScenarioDeck, Seed

    seeds = [Seed("A", "a"), Seed("B", "b")]
    shown: list[str] = []
    answers = iter(["7", "x", "2"])
    deck = ScenarioDeck(seeds, None, random.Random(0))
    assert choose_start_scenario(deck, lambda _: next(answers), shown.append) == "B"
    assert "   2  B" in shown and deck.next().text == "b"
    assert sum("Keine Nummer" in line for line in shown) == 2
    assert choose_start_scenario(ScenarioDeck(seeds, None, random.Random(0)), lambda _: "", shown.append) == "alle Bereiche"


def test_report_command_is_registered_and_reports_unknown_id(tmp_path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from self_talk_coach.cli import app

    for name, value in {"DEEPGRAM_API_KEY": "d", "GATEWAY_BASE_URL": "https://gw.example/v1",
                        "GATEWAY_API_KEY": "g", "STC_QUESTION_BANKS": "x.md"}.items():
        monkeypatch.setenv(name, value)
    result = CliRunner().invoke(app, ["report", "999", "--data-root", str(tmp_path)])
    assert result.exit_code == 1
    assert "Kein Gespräch 999" in result.output


def test_start_menu_m_picks_mein_tag_and_leaves_deck_alone() -> None:
    import random

    from self_talk_coach.cli import choose_start_scenario
    from self_talk_coach.conversation.mein_tag import MEIN_TAG
    from self_talk_coach.conversation.question_bank import ScenarioDeck, Seed

    shown: list[str] = []
    deck = ScenarioDeck([Seed("A", "a")], None, random.Random(0))
    assert choose_start_scenario(deck, lambda _: "m", shown.append) == MEIN_TAG
    assert any("Mein Tag" in line for line in shown)
    assert deck.label == ScenarioDeck.MIXED
