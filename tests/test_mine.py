import re
from pathlib import Path

from self_talk_coach.mine import Token, load_baseline, mine_new_words, out_of_baseline_ratio

STOP = {"ich", "die", "der", "eine", "und", "in"}


def fake_lemmatize(text: str) -> list[Token]:
    """Every word is a NOUN with itself as lemma; 'Reutlingen' is a proper noun."""
    return [
        Token(w, "PROPN" if w == "Reutlingen" else "NOUN", w.lower() in STOP)
        for w in re.findall(r"\w+", text)
    ]


def test_load_baseline_lowercases_and_skips_blank(tmp_path: Path) -> None:
    path = tmp_path / "b.txt"
    path.write_text("Arbeit\n\nschicht\n", encoding="utf-8")
    assert load_baseline(path) == frozenset({"arbeit", "schicht"})


def test_out_of_baseline_ratio_counts_content_words_only() -> None:
    baseline = frozenset({"arbeit"})
    assert out_of_baseline_ratio("Die Arbeit und die Rückerstattung", baseline, fake_lemmatize) == 0.5
    assert out_of_baseline_ratio("und die", baseline, fake_lemmatize) is None


def test_mine_new_words_skips_baseline_known_propn_and_repeats() -> None:
    words = mine_new_words(
        ["Eine Rückerstattung in Reutlingen", "Die Rückerstattung und der Schichtleiter", "Arbeit Quittung"],
        baseline=frozenset({"arbeit"}),
        known={"quittung"},
        lemmatize=fake_lemmatize,
    )
    assert [(w.lemma, w.example) for w in words] == [
        ("Rückerstattung", "Eine Rückerstattung in Reutlingen"),
        ("Schichtleiter", "Die Rückerstattung und der Schichtleiter"),
    ]
    assert len(mine_new_words(["A B C D"], frozenset(), set(), fake_lemmatize, limit=2)) == 2
