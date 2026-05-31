"""Generate resources/baseline-de-b1.txt from wordfreq + spaCy lemmatization.

Run from project root:
    .venv/Scripts/python scripts/build_baseline.py

Pipeline:
  1. Take top N German word forms from `wordfreq` (Zipf-frequency, MIT licensed).
  2. Lemmatize each via spaCy `de_core_news_lg`.
  3. Filter out punctuation / single-letter / numeric / proper-noun-ish entries.
  4. Dedupe to lowercase lemmas, target ~4000 entries.
  5. Write one lemma per line, UTF-8, sorted.

The result is a frequency-derived approximate B1 baseline. NOT the actual Goethe-B1
list (which has redistribution constraints). Quality good enough for V1 vocab
mining; tracked in BACKLOG to upgrade later.
"""

from __future__ import annotations

import sys
from pathlib import Path

import spacy
from wordfreq import top_n_list

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "resources" / "baseline-de-b1.txt"
TOP_N_SOURCE = 7000
TARGET_LEMMAS = 4000


def main() -> int:
    print(f"Loading top {TOP_N_SOURCE} German word forms from wordfreq...")
    forms = top_n_list("de", TOP_N_SOURCE, wordlist="best")
    print(f"  got {len(forms)} forms")

    print("Loading spaCy de_core_news_lg...")
    nlp = spacy.load("de_core_news_lg", disable=["parser", "ner"])

    lemmas: set[str] = set()
    skipped = 0
    for form in forms:
        if len(form) < 2:
            skipped += 1
            continue
        if not form.isalpha():
            skipped += 1
            continue
        doc = nlp(form)
        if not doc:
            skipped += 1
            continue
        token = doc[0]
        if token.pos_ == "PROPN":
            skipped += 1
            continue
        lemma = token.lemma_.lower()
        if len(lemma) < 2 or not lemma.isalpha():
            skipped += 1
            continue
        lemmas.add(lemma)
        if len(lemmas) >= TARGET_LEMMAS:
            break

    print(f"  collected {len(lemmas)} unique lemmas, skipped {skipped} entries")

    sanity_check = {"und", "haben", "gehen", "haus", "wasser"}
    missing = sanity_check - lemmas
    if missing:
        print(f"WARNING: core words missing from baseline: {missing}", file=sys.stderr)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for lemma in sorted(lemmas):
            fh.write(lemma + "\n")
    print(f"wrote {OUT_PATH} ({len(lemmas)} lemmas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
