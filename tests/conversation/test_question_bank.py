import random
from pathlib import Path

import pytest

from self_talk_coach.conversation.question_bank import (
    Seed,
    SeedPicker,
    filter_scenario,
    load_banks,
    parse_bank,
)

BANK = """# German Question Bank

1. ignored, no section yet

## Interview: Core

1. Erzählen Sie mir bitte etwas über sich.
2. Was sind Ihre Stärken?

## Daily Life In Germany

1. Wie kommst du zur Arbeit?
10. Was kochst du gern?
- not numbered, ignored
"""

SAMPLE = """# Interview-Fragenbank — Name

**Stand:** 11 / 26 · **Kurzfassung** · **Hinweis:**

★ = wichtigste Fragen zuerst (ca. zehn)

---

## Wie nutze ich dieses Heft?

- Erst laut antworten, dann lesen.
- Platzhalter in eckigen Klammern ersetzen.

---

# 1. Kern (Core)

## 1.1 ★ Erzählen Sie etwas über sich.

Ich bin Ingenieur und arbeite gern mit Simulation.

---

## 1.2 Warum interessieren Sie sich für diese Stelle?

> Vorbereiten: `[Firmenname]`, `[Produkt]`

Die Stelle passt, weil `[Firmenname]` Berechnung und Software verbindet.

Zweiter Absatz der Antwort.

> **Merksatz (Kurzfassung):** Erst die Firma, dann ich.

---

## 1.3a ★ Was sind Ihre Stärken? — Version A (modern)

Schnelles Prototyping mit Python.

---

## 1.3b ★ Was sind Ihre Stärken? — Version B (klassisch)

Gründlichkeit und saubere Dokumentation.

---

# 5a. Berater-Flow (Karriereberater-Gespräch)

## 5a.1 Welche Branchen interessieren Sie?

Maschinenbau und Energie.

---

## 5.11 Haben Sie Fragen an uns?

Ja, zum Beispiel:

1. Wie sieht ein typischer Tag aus?
2. Wie ist das Team aufgebaut?

---

# 5b. AGG-sensible Fragen (Deflektion)

> **Hinweis:** Diese Fragen sind meist unzulässig.

## 5b.1 Planen Sie eine Familie?

Darauf möchte ich höflich nicht eingehen.

---

# Ende

**Vor dem Gespräch:**
1. Laut üben.
2. Ruhig bleiben.
"""


def _expected_questionnaire() -> list[Seed]:
    return [
        Seed("Interview: Kern (Core)", "Erzählen Sie etwas über sich.",
             model_answer="Ich bin Ingenieur und arbeite gern mit Simulation."),
        Seed("Interview: Kern (Core)", "Warum interessieren Sie sich für diese Stelle?",
             model_answer="Die Stelle passt, weil `[Firmenname]` Berechnung und Software verbindet."
             "\n\nZweiter Absatz der Antwort."),
        Seed("Interview: Kern (Core)", "Was sind Ihre Stärken?",
             model_answer="Version A (modern): Schnelles Prototyping mit Python."
             "\n\nVersion B (klassisch): Gründlichkeit und saubere Dokumentation."),
        Seed("Interview: Berater-Flow (Karriereberater-Gespräch)", "Welche Branchen interessieren Sie?",
             model_answer="Maschinenbau und Energie."),
        Seed("Interview: Berater-Flow (Karriereberater-Gespräch)", "Haben Sie Fragen an uns?",
             model_answer="Ja, zum Beispiel:\n\n1. Wie sieht ein typischer Tag aus?\n2. Wie ist das Team aufgebaut?"),
        Seed("Interview: AGG-sensible Fragen (Deflektion)", "Planen Sie eine Familie?",
             model_answer="Darauf möchte ich höflich nicht eingehen."),
    ]


def test_parse_questionnaire_reads_questions_answers_and_variants() -> None:
    from self_talk_coach.conversation.question_bank import parse_questionnaire

    assert parse_questionnaire(SAMPLE) == _expected_questionnaire()


def test_load_banks_detects_questionnaire_per_file(tmp_path: Path) -> None:
    questionnaire = tmp_path / "questionnaire.md"
    questionnaire.write_text(SAMPLE, encoding="utf-8")
    bank = tmp_path / "bank.md"
    bank.write_text(BANK, encoding="utf-8")
    assert load_banks([questionnaire]) == _expected_questionnaire()
    assert load_banks([bank]) == parse_bank(BANK)
    assert all(seed.model_answer is None for seed in load_banks([bank]))
    assert load_banks([bank, questionnaire]) == parse_bank(BANK) + _expected_questionnaire()


def test_questionnaire_sections_are_interviews() -> None:
    from self_talk_coach.conversation.question_bank import is_interview, parse_questionnaire

    sections = [seed.section for seed in parse_questionnaire(SAMPLE)]
    assert len(sections) == 6
    assert all(is_interview(section) for section in sections)


@pytest.mark.parametrize("markdown", [
    "# 1. Group\n## Ordinary section\n1. Question?",
    "# Ordinary title\n## 1.1 Question?\n1. Answer list item",
])
def test_questionnaire_detection_requires_both_heading_types(tmp_path: Path, markdown: str) -> None:
    bank = tmp_path / "bank.md"
    bank.write_text(markdown, encoding="utf-8")
    assert load_banks([bank]) == parse_bank(markdown)


def test_questionnaire_boundaries_empty_answers_and_nonconsecutive_duplicates() -> None:
    from self_talk_coach.conversation.question_bank import parse_questionnaire

    markdown = """## 0.1 Ignored before group?
# 1. Group
## Usage
1. Ignore this list
## 1.1 Empty?
> Note only
## 1.2 Kept?
  Indented answer.

Second paragraph.
---
Not part of the answer.
## 1.3 Empty?
# End
## 1.4 Ignored after end?
# 2. Group
## 2.1 Empty?
"""
    assert parse_questionnaire(markdown) == [
        Seed("Interview: Group", "Empty?"),
        Seed("Interview: Group", "Kept?", model_answer="  Indented answer.\n\nSecond paragraph."),
        Seed("Interview: Group", "Empty?"),
        Seed("Interview: Group", "Empty?"),
    ]


def test_parse_bank_reads_numbered_items_per_section() -> None:
    seeds = parse_bank(BANK)
    assert seeds == [
        Seed("Interview: Core", "Erzählen Sie mir bitte etwas über sich."),
        Seed("Interview: Core", "Was sind Ihre Stärken?"),
        Seed("Daily Life In Germany", "Wie kommst du zur Arbeit?"),
        Seed("Daily Life In Germany", "Was kochst du gern?"),
    ]


def test_load_banks_reads_files_and_names_missing(tmp_path: Path) -> None:
    bank = tmp_path / "bank.md"
    bank.write_text(BANK, encoding="utf-8")
    assert len(load_banks([bank])) == 4
    with pytest.raises(FileNotFoundError, match="nope.md"):
        load_banks([tmp_path / "nope.md"])


def test_filter_scenario() -> None:
    seeds = parse_bank(BANK)
    assert filter_scenario(seeds, None) == seeds
    assert [s.text for s in filter_scenario(seeds, "interview")] == [
        "Erzählen Sie mir bitte etwas über sich.",
        "Was sind Ihre Stärken?",
    ]
    with pytest.raises(ValueError, match="Daily Life In Germany"):
        filter_scenario(seeds, "Behörde")


def test_picker_never_repeats_until_exhausted() -> None:
    seeds = parse_bank(BANK)
    picker = SeedPicker(seeds, random.Random(1))
    first_round = [picker.next() for _ in range(4)]
    assert sorted(s.text for s in first_round) == sorted(s.text for s in seeds)
    assert picker.next() in seeds


def test_mark_phrase_sections_matches_section_names_case_insensitively() -> None:
    from self_talk_coach.conversation.question_bank import mark_phrase_sections

    seeds = mark_phrase_sections(parse_bank(BANK), ("daily life",))
    assert {s.section: s.phrase for s in seeds} == {"Interview: Core": False, "Daily Life In Germany": True}
    assert all(not s.phrase for s in mark_phrase_sections(parse_bank(BANK), ()))


def _deck_seeds() -> list[Seed]:
    return [Seed("A", "a1"), Seed("A", "a2"), Seed("B", "b1"), Seed("C", "c1")]


def test_deck_mixed_start_then_switch_cycles_sections_in_bank_order() -> None:
    from self_talk_coach.conversation.question_bank import ScenarioDeck

    deck = ScenarioDeck(_deck_seeds(), None, random.Random(0))
    assert deck.label == "alle Bereiche"
    assert {deck.next().section for _ in range(8)} == {"A", "B", "C"}
    assert [deck.switch() for _ in range(4)] == ["A", "B", "C", "A"]
    assert {deck.next().text for _ in range(4)} == {"a1", "a2"}


def test_deck_filtered_start_switches_to_following_section() -> None:
    from self_talk_coach.conversation.question_bank import ScenarioDeck

    deck = ScenarioDeck(_deck_seeds(), "b", random.Random(0))
    assert deck.label == "B"
    assert deck.next().text == "b1"
    assert deck.switch() == "C"
    assert deck.next().text == "c1"
    with pytest.raises(ValueError):
        ScenarioDeck(_deck_seeds(), "zzz", random.Random(0))


def test_deck_options_mark_current_and_choose_by_number() -> None:
    from self_talk_coach.conversation.question_bank import ScenarioDeck

    deck = ScenarioDeck(_deck_seeds(), "b", random.Random(0))
    assert deck.options() == ["alle Bereiche", "A", "B", "C"]
    assert deck.current_option == 2
    assert deck.choose(3) == "C" and deck.current_option == 3
    assert deck.next().text == "c1"
    assert deck.choose(0) == "alle Bereiche" and deck.current_option == 0
    assert {deck.next().section for _ in range(8)} == {"A", "B", "C"}
    assert deck.switch() == "A"


def test_interview_sections_are_asked_in_bank_order() -> None:
    from self_talk_coach.conversation.question_bank import ScenarioDeck, Seed

    seeds = [Seed("Interview: Core", f"Q{i}") for i in range(1, 5)] + [Seed("Daily", "D1"), Seed("Daily", "D2")]
    deck = ScenarioDeck(seeds, "Interview: Core", random.Random(0))
    assert [deck.next().text for _ in range(5)] == ["Q1", "Q2", "Q3", "Q4", "Q1"]
    mixed = ScenarioDeck(seeds, None, random.Random(0))
    assert {mixed.next().text for _ in range(6)} == {"Q1", "Q2", "Q3", "Q4", "D1", "D2"}
