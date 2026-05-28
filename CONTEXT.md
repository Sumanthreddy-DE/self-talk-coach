# CONTEXT — self-talk-coach domain glossary

Last swept: 2026-05-28

## Domain terms

- **self-talk** – User's own monologue video/audio files. Personal corpus, German, ≤5h total in V1. Casual register, not scripted.
- **transcript** – Output of Whisper for one source file. JSON with `{source, language, segments[{start, end, text}], duration, model}`. Stored under `data/transcripts/`.
- **segment** – One contiguous Whisper utterance with start/end timestamps. Used as the unit for vocab provenance.
- **baseline** – The Goethe-B1 ~4k-lemma wordlist that defines "already known." Lives in `resources/baseline-de-b1.txt`, one lemma per line, lowercase, UTF-8.
- **unknown-word / candidate** – A lemma found in a transcript that is NOT in the baseline AND has frequency ≥ 2 across the corpus AND is not a proper noun.
- **enriched card** – An unknown word annotated by Claude with `definition_de`, `definition_en`, `gender`, `pos`, `example_de`, `example_en`, plus provenance (`source`, `timestamp`, `original_sentence`).
- **deck / .apkg** – Final genanki output, importable into Anki / AnkiDroid.
- **B1 / B2** – CEFR language levels. Baseline = B1; surfaced unknowns ≈ B2+.

## What "self-talk" includes / excludes

- **Includes:** Sumanth's own monologue recordings (e.g. nightly reflection videos), language-practice audio, voice notes – sources where he is the only speaker, in German.
- **Excludes:** any audio with second speakers, calls with others (§ 201 StGB), interviews, anything that would create a consent issue. V1 is single-speaker only.

## Public-repo eventual scope

When V1 flips public:
- No `data/audio/`, no `data/transcripts/` ever committed
- `samples/synthetic-transcript.json` only – hand-authored fake monologue
- README in DE+EN
- No real PII in commits

## Glossary anti-patterns (don't conflate)

- **lemma ≠ token** – `Häuser` (token) → `Haus` (lemma). Mining works on lemmas.
- **freq ≥ 2 ≠ rare** – frequency cutoff is to filter Whisper hallucinations, not to define rarity.
- **B2+ ≠ "hard"** – baseline is approximate; some surfaced lemmas may feel A2 (gaps in baseline), others B2 (real unknowns). Hand-curate via Anki suspend.
