# CONTEXT — self-talk-coach domain glossary

Last swept: 2026-05-28

## Domain terms

- **self-talk** – User's own monologue video/audio files. Personal corpus, German, ≤5h total in V1. Casual register, not scripted.
- **transcript** – Output of Whisper for one source file. JSON with `{source, language, segments[{start, end, text}], duration, model}`. Stored under `data/transcripts/`.
- **learner transcript** – Deepgram Nova-3 transcription of one learner turn, with word confidences; feeds both the partner's reply and the session report (single pass — ADR 0005). Keeps learner errors and self-corrections verbatim. _Avoid_: live/review transcript (two-pass design dropped 2026-10-05 after spike S1).
- **segment** – One contiguous Whisper utterance with start/end timestamps. Used as the unit for vocab provenance.
- **baseline** – The ~4k-lemma frequency-derived approximate B1 wordlist (wordfreq + spaCy, MIT — not Goethe, for licensing) that defines "already known." Lives in `resources/baseline-de-b1.txt`, one lemma per line, lowercase, UTF-8.
- **unknown-word / candidate** – A lemma found in a transcript that is NOT in the baseline AND has frequency ≥ 2 across the corpus AND is not a proper noun.
- **enriched card** – An unknown word annotated by Claude with `definition_de`, `definition_en`, `gender`, `pos`, `example_de`, `example_en`, plus provenance (`source`, `timestamp`, `original_sentence`).
- **deck / .apkg** – Final genanki output, importable into Anki / AnkiDroid.
- **B1 / B2** – CEFR language levels. Baseline = B1; surfaced unknowns ≈ B2+.

## Conversation terms (live partner, designed 2026-10-04)

- **conversation** – One live practice session between the learner and the AI partner. Distinct from self-talk. _Avoid_: chat, call, dialogue.
- **partner** – The AI conversation counterpart (an LLM for text — DeepSeek V4 Pro in v1 — and TTS for voice). Never a real human. _Avoid_: bot, tutor, assistant.
- **turn** – One utterance by either the learner or the partner within a conversation.
- **scenario card** – A predefined role-play setup (e.g. Vorstellungsgespräch, McDonald's Schicht, Behörde) with goals; "free talk" is a conversation without one.
- **freeze time** – Seconds from the end of the partner's audio to the learner starting to speak (v1: toggle-key press).
- **help ladder** – Escalating partner help during silence: nudge → starter phrase → simpler rephrase. Never answers for the learner. Starter and rephrase are pre-generated with each partner question, kept hidden, and delivered by voice only when the ladder fires.
- **rescue phrase** – A German time-buying or clarifying phrase (e.g. "Gute Frage, lass mich kurz überlegen …").
- **listening aid** – Learner request during a partner turn: replay, slower, or show text. Every use is logged.
- **recast** – Partner repeats a learner error back in corrected form, in passing, with no explanation.
- **session report** – Post-conversation summary built from the learner transcripts: recurring errors, freeze times, rescue phrases, listening-aid use, new words.

Relationships:
- A **conversation** has many **turns**; each turn belongs to the learner or the partner.
- A **conversation** uses zero or one **scenario card**.
- A learner **turn** has one **learner transcript**.
- A **conversation** produces exactly one **session report**.

Boundary: a conversation contains exactly two voices — the learner and the AI partner. Recording any real third person is out of scope (§ 201 StGB rationale below still holds).

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
