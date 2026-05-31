# resources/

Static data files used at runtime by the vocab miner.

## baseline-de-b1.txt

A frequency-derived approximate B1 German vocabulary baseline. Contains ~4000
lowercase lemmas, one per line, UTF-8. Used as the "known words" set – anything
in a transcript that lemmatizes to something OUTSIDE this list becomes a vocab
candidate.

### Source and license

- **Source:** `wordfreq` Python package (https://github.com/rspeer/wordfreq),
  MIT licensed. `wordfreq` aggregates Zipf-frequency data across multiple
  corpora including Subtlex-DE, Google Books, Twitter, Wikipedia, and Common
  Crawl. We take the top 7000 German word forms (`wordlist="best"`).
- **Processing:** lemmatized via spaCy `de_core_news_lg`, filtered to remove
  proper nouns, single-letter entries, non-alphabetic tokens. Truncated to the
  first 4000 unique lemmas.
- **Regeneration:** `.venv/Scripts/python scripts/build_baseline.py` from the
  project root. Output is deterministic given the same wordfreq + spaCy model
  versions.

### Why not the actual Goethe-B1 list

The official Goethe-Institut B1 wordlist is a PDF with redistribution
constraints. A frequency-derived approximation is "good enough" for V1: most
true B1 words are high-frequency anyway, and the miner over-surfaces rather
than under-surfaces (false positives are easy to suspend in Anki; false
negatives mean missed learning opportunities).

Tracked in BACKLOG: upgrade to an actual CEFR-aligned source when one with a
clean license is found.

### Sanity check

```
python -c "
lines = set(open('resources/baseline-de-b1.txt', encoding='utf-8').read().splitlines())
assert 3000 <= len(lines) <= 5000
assert {'und','haben','gehen','haus','wasser'} <= lines
"
```

## ignore.txt (created in S4)

Hand-curated list of high-frequency filler words to skip even if they slip
past the baseline. Examples: `halt`, `irgendwie`, `quasi`, `naja`.
