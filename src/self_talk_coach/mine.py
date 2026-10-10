"""Vocab miner: lemmas outside the B1 baseline that the learner has not used himself yet."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parents[2] / "resources" / "baseline-de-b1.txt"
CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})
SPACY_MODEL = "de_core_news_lg"  # ADR 0002


@dataclass(frozen=True)
class Token:
    lemma: str
    pos: str
    is_stop: bool


Lemmatize = Callable[[str], list[Token]]


@dataclass(frozen=True)
class NewWord:
    lemma: str
    example: str  # the sentence it first appeared in


class MinerUnavailable(Exception):
    """The lemmatizer cannot run (spaCy model missing)."""


def load_baseline(path: Path = BASELINE_PATH) -> frozenset[str]:
    return frozenset(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _content(tokens: list[Token]) -> list[Token]:
    return [t for t in tokens if t.pos in CONTENT_POS and not t.is_stop and t.lemma.isalpha()]


def out_of_baseline_ratio(text: str, baseline: frozenset[str], lemmatize: Lemmatize) -> float | None:
    """Share of content lemmas outside the baseline (spec § Metrics: partner level check)."""
    words = _content(lemmatize(text))
    if not words:
        return None
    return round(sum(t.lemma.lower() not in baseline for t in words) / len(words), 2)


def mine_new_words(
    sources: Sequence[str],
    baseline: frozenset[str],
    known: set[str],
    lemmatize: Lemmatize,
    limit: int = 10,
) -> list[NewWord]:
    found: dict[str, NewWord] = {}
    for text in sources:
        for token in _content(lemmatize(text)):
            key = token.lemma.lower()
            if key in baseline or key in known or key in found:
                continue
            found[key] = NewWord(token.lemma, text)
            if len(found) == limit:
                return list(found.values())
    return list(found.values())


def spacy_lemmatizer() -> Lemmatize:
    import spacy

    try:
        nlp = spacy.load(SPACY_MODEL, disable=["parser", "ner"])
    except OSError as exc:
        raise MinerUnavailable(
            f"spaCy-Modell {SPACY_MODEL} fehlt: .venv\\Scripts\\python.exe -m spacy download {SPACY_MODEL}"
        ) from exc

    def lemmatize(text: str) -> list[Token]:
        return [Token(t.lemma_, t.pos_, t.is_stop) for t in nlp(text)]

    return lemmatize
