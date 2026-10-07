# Blueprint: self-talk-coach (V1 Weekend MVP)

**Status:** abandoned
**Last verified:** 2026-10-07
**Status evidence:** S1 scaffold + S3 baseline shipped (caea308, 16de6aa); S2 was rebuilt as M2 under the local-first core design (2026-05-31 spec), which replaced this file-based pipeline with a SQLite core. S4–S6 never built: `mine.py`, `enrich.py`, `anki.py` are 4-line stubs, no CLI commands. Reusable designs carried to BACKLOG: `vocab-miner` (S4), `anki-export` (S5).

**Project root:** `C:/Users/suman/Desktop/Docs/Job/Projects/self-talk-coach/`
**Objective:** Python CLI that ingests German self-talk video files → transcribes (faster-whisper) → mines unknown vocab vs Goethe-B1 baseline (spaCy) → enriches via Claude API → exports Anki `.apkg`.
**Scope:** Selfish utility, sole user = Sumanth. Corpus <5h. Private repo, flip public later.
**Owner:** Sumanth (Sumanthreddy-DE)
**Created:** 2026-05-28

---

## Invariants (verify after every step)

1. No real audio/video files committed (`data/` gitignored)
2. No PII in committed transcripts (synthetic sample only)
3. No secrets committed (`.env`, API keys → `.env.example` only)
4. Tests pass locally (`pytest` green) after S4 onward
5. CLI remains runnable end-to-end (`stc run samples/` smoke test) from S6 onward
6. Every `stc` sub-command named in README exists in `cli.py` (concrete README↔code check)
7. All file I/O passes explicit `encoding="utf-8"` — Windows default is cp1252 and would corrupt umlauts

## Anti-patterns to avoid

- Don't commit `data/audio/` or `data/transcripts/` (real PII)
- Don't hardcode API keys — `os.environ["ANTHROPIC_API_KEY"]`
- Don't ship the full Goethe-B1 list if license forbids redistribution — verify license, prefer derived/public-domain wordlist (e.g., dwds-derived freq list or CC-licensed source) and document provenance in `resources/README.md`
- Don't bundle Whisper model in repo — download on first run, cache in user dir
- Don't add features beyond V1 scope (RAG journal = V2, separate plan)
- Don't over-abstract — flat module per stage is fine for 7-step MVP
- Don't add `Co-Authored-By` / AI attribution in commits (per global rules)

## Dependency graph

```
S1 (scaffold)
 ├─→ S2 (ingest+transcribe)  ─┐
 └─→ S3 (baseline wordlist)  ─┤
                              ↓
                             S4 (vocab mine)
                              ↓
                             S5 (enrich + Anki)
                              ↓
                             S6 (CLI wire + synthetic sample)
                              ↓
                             S7 (private GitHub repo + push)
```

**Parallel:** S2 ∥ S3 (no shared files). All others serial.

## Model tier per step

| Step | Tier | Reason |
|------|------|--------|
| S1   | default | mechanical scaffold |
| S2   | strongest | whisper config + audio plumbing has subtle traps |
| S3   | default | data wrangling |
| S4   | strongest | spaCy pipeline + freq logic = correctness-sensitive |
| S5   | strongest | Claude prompt engineering for high-quality cards |
| S6   | default | wiring |
| S7   | default | gh CLI + push |

## Rollback strategy

Each step = one git branch + one commit (or small commit series). Rollback = `git reset --hard <prev-step-sha>` on the branch. No squash-merge until plan complete. If a step's exit criteria fail, do NOT proceed — fix or split (see "Plan mutation" below).

---

# Steps

## S1 — Scaffold + harness

**Branch:** `s1-scaffold`
**Depends on:** none
**Tier:** default

### Context brief

Fresh empty target dir. We need a Python project skeleton with the global-rules harness files (BACKLOG.md, SESSION-END.md, docs/exec-plans/, Archive/) plus `pyproject.toml` for `uv`/`pip` deps, plus README skeleton DE+EN, plus `.gitignore`, plus tooling config (ruff, pytest). spaCy German model `de_core_news_lg` must be installed.

The user's harness helper script is at `~/.claude/scripts/new-project-init.sh` and templates at `~/.claude/templates/new-project/`. Use it OR copy the templates manually. Don't pollute user root with a CLAUDE.md.

### Tasks

1. Create dir `C:/Users/suman/Desktop/Docs/Job/Projects/self-talk-coach/`
2. Run `bash ~/.claude/scripts/new-project-init.sh self-talk-coach` from inside the new dir (creates ARCHITECTURE.md, BACKLOG.md, SESSION-END.md, docs/exec-plans/, Archive/, etc.)
3. Move this blueprint file to `docs/exec-plans/01-weekend-mvp.md`
4. Create `pyproject.toml` with **all deps locked at S1** (pyproject is treated as frozen after this step — prevents merge conflicts on S2∥S3):
   - runtime: `faster-whisper`, `spacy`, `genanki`, `anthropic`, `typer`, `pydub`, `python-dotenv`, `numpy`, `scipy`, `requests`, `pydantic>=2`
   - dev: `pytest`, `ruff`
5. Create `src/self_talk_coach/__init__.py` + empty module stubs: `ingest.py`, `transcribe.py`, `mine.py`, `enrich.py`, `anki.py`, `cli.py`
6. Create `tests/__init__.py` + `tests/test_smoke.py` with one `def test_import(): import self_talk_coach`
7. Create `.gitignore` covering: `data/`, `.env`, `__pycache__/`, `*.apkg`, `.venv/`, `models/`, `dist/`, `build/`, `.pytest_cache/`, `.ruff_cache/`, plus root-level audio safety net `*.wav`, `*.mp4`, `*.mov`, `*.webm`, `*.mkv`, `*.m4a`, `*.mp3` AND explicit allow `!samples/*.json` so synthetic samples land
8. Create `.env.example` with `ANTHROPIC_API_KEY=` placeholder
9. Create `data/.gitkeep` but `data/audio/`, `data/transcripts/`, `data/out/` themselves stay empty + gitignored
10. Create `resources/.gitkeep` (Goethe baseline lands here in S3)
11. Create `samples/.gitkeep` (synthetic transcript lands here in S3)
12. Create README.md skeleton — DE on top, EN below, with sections: Was es macht / What it does, Quickstart, Konfiguration / Configuration, Voraussetzungen / Requirements (Python 3.12+, ffmpeg on PATH — `winget install ffmpeg` on Windows), Lizenz / License. **En-dash (–), NOT em-dash (—)** for German typography — see global lesson `lessons_em-dash-ai-tell-de.md`
13. Create `CONTEXT.md` at project root — domain glossary: lemma, baseline, unknown-word, enriched card, .apkg, B1/B2 levels, what counts as "self-talk"
14. Create three short ADRs under `docs/adr/`:
    - `0001-faster-whisper-over-openai-whisper.md` — CTranslate2 backend = 4× faster CPU, int8 quant available
    - `0002-spacy-de_core_news_lg-over-sm.md` — `_lg` has better lemmatization on casual register
    - `0003-genanki-over-ankiconnect.md` — no running Anki required, offline pipeline
15. Initialize venv + install deps using direct interpreter path (no `activate` — keeps the chain shell-agnostic on Windows):
    ```
    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"
    .venv/Scripts/python -m spacy download de_core_news_lg
    ```
16. Run `pytest` → green smoke test
17. `git init && git add . && git commit -m "chore: scaffold self-talk-coach project"`

### Verification

```bash
cd C:/Users/suman/Desktop/Docs/Job/Projects/self-talk-coach
test -f pyproject.toml && test -f README.md && test -f BACKLOG.md && test -d docs/exec-plans && test -f docs/exec-plans/01-weekend-mvp.md
test -f docs/adr/0001-faster-whisper-over-openai-whisper.md
ffmpeg -version | head -1    # system dep must be on PATH
.venv/Scripts/python -c "import spacy; nlp = spacy.load('de_core_news_lg'); print(nlp('Hallo Welt')[0].lemma_)"
.venv/Scripts/python -m pytest -q
git log --oneline | head -1
```

### Exit criteria

- All paths above exist
- `spacy.load('de_core_news_lg')` returns a working pipeline
- `pytest` green
- First commit landed on `s1-scaffold` branch (or `main` if going direct)

---

## S2 — Ingest + Transcribe

**Branch:** `s2-transcribe`
**Depends on:** S1
**Tier:** strongest

### Context brief

Two stages in one PR because they're tightly coupled and the intermediate `.wav` is throwaway. Input = a folder of video files (`.mp4`, `.mov`, `.webm`, `.mkv`, `.m4a`, `.mp3`). Output = `data/transcripts/<source-stem>.json` with structure `{ "source": str, "language": "de", "segments": [ { "start": float, "end": float, "text": str } ], "duration": float, "model": "faster-whisper:<size>" }`.

Whisper hallucinates on silence — apply VAD filter (`vad_filter=True` in faster-whisper) and skip segments shorter than ~0.2s. Force language to `de` (don't autodetect — corpus is mostly German).

**Model defaults — weekend-realistic:** default `--model medium` with `compute_type="int8"` (~0.5–1× real-time on CPU, ~5h corpus ≈ 5–10h wall-clock = overnight). `large-v3` is opt-in "overnight" mode and documented as such. `small` for fast iteration during dev. Document the wall-clock budget in README so user knows what they're committing to. All file I/O uses `encoding="utf-8"` (Invariant #7).

### Tasks

1. `ingest.py`:
   - `extract_audio(input_path: Path, out_path: Path) -> Path` — runs `ffmpeg -i {input} -ac 1 -ar 16000 -vn {out_path}` (mono, 16kHz, no video). Use subprocess, capture stderr, raise on nonzero.
   - `iter_media_files(root: Path) -> Iterator[Path]` — glob `*.{mp4,mov,webm,mkv,m4a,mp3,wav}` recursively
2. `transcribe.py`:
   - `Transcriber` class wrapping `faster_whisper.WhisperModel`
   - `__init__(model_size="medium", device="auto", compute_type="int8")` — `medium` + `int8` is the weekend default
   - `transcribe(wav_path: Path, language="de") -> dict` returning the schema above. Uses `vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}`.
   - Writes transcript JSON next to the call site (caller decides path) using `json.dump(..., ensure_ascii=False)` + `encoding="utf-8"`
3. Tests:
   - `test_ingest_glob` — temp dir with fake files, check filter
   - `test_transcribe_smoke` — skip if model not downloaded; if downloaded, transcribe a 3-second synthetic WAV (use `numpy` + `scipy.io.wavfile` to write a silent or tone WAV) and assert returned dict has `segments` key
4. Add a `scripts/synth_wav.py` utility that creates a 5-second test WAV with a TTS-free placeholder (silent or sine wave) — used in tests only
5. Commit: `feat(transcribe): ingest media + faster-whisper pipeline`

### Verification

**Automated (must pass):**
```bash
cd C:/Users/suman/Desktop/Docs/Job/Projects/self-talk-coach
.venv/Scripts/python -m pytest -q tests/test_ingest.py tests/test_transcribe.py
```

**Manual smoke (optional, user-driven — not a gate):**
```bash
# User drops one short DE video into data/audio/test.mp4 (NOT committed, gitignored)
.venv/Scripts/python -c "
from pathlib import Path
from self_talk_coach.ingest import extract_audio
from self_talk_coach.transcribe import Transcriber
wav = extract_audio(Path('data/audio/test.mp4'), Path('data/audio/test.wav'))
t = Transcriber(model_size='small')
out = t.transcribe(wav)
print(len(out['segments']), 'segments,', out['duration'], 's')
"
```

### Exit criteria

- `extract_audio` produces valid 16kHz mono WAV (verified in unit test against synthetic input)
- `Transcriber` returns dict matching schema (verified against synthetic sine-wave WAV from `scripts/synth_wav.py`)
- VAD filter on by default
- All automated tests green
- Commit on `s2-transcribe`

---

## S3 — Baseline wordlist (parallel with S2)

**Branch:** `s3-baseline`
**Depends on:** S1
**Tier:** default

### Context brief

We need a public/licenseable list of ~4000 German lemmas at A1–B1 level to use as the "known words" baseline. Anything in our transcript that lemmatizes to something OUTSIDE this list is a candidate vocab card. Goethe's official lists are PDFs and may have licensing restrictions for redistribution — prefer derived/CC-licensed sources.

**Candidate sources** (time-box research at **30 minutes max**, then commit):
- **dwds.de** lemma frequency list (CC-BY) — top 4k by frequency, decent overlap with A1–B1 → **default fallback if research stalls**
- **deutsch.lingolia.com**-derived community lists (check license)
- **Wiktionary** A1/A2/B1 categories scraped (CC-BY-SA)
- **DeReKo / DWDS Kernkorpus** derived

**Fallback rule:** if license unclear after 30 minutes, use DWDS top-4k frequency list (CC-BY) with attribution. Don't stall the plan.

Verify license, attribute in `resources/README.md`. If no clean source exists, ship a **starter list** (top 2000 from open frequency data + manually curated A2/B1 additions) and note in BACKLOG that we want to upgrade to a better list later.

**Bonus deliverable (resolves S4/S5 cold-start problem):** ship `samples/synthetic-transcript.json` in this step (data, not code — parallel-safe with S2). Hand-author ~50 segments of fake German "self-talk" with deliberate B2+ vocab so downstream steps can verify against this file without needing S2 output. Schema matches S2 output exactly.

### Tasks

1. Research sources (30-min time-box, document 2–3 options in `resources/README.md` with license + URL + size; default to DWDS top-4k if unclear)
2. Pick one, fetch the data
3. Normalize to one-lemma-per-line lowercase UTF-8 text → `resources/baseline-de-b1.txt`
4. Strip duplicates, non-words, single-letter entries
5. Sanity-check via Python (POSIX-tool-free, works on Windows):
   ```bash
   .venv/Scripts/python -c "
   lines = set(open('resources/baseline-de-b1.txt', encoding='utf-8').read().splitlines())
   assert 3000 <= len(lines) <= 5000, f'wrong size: {len(lines)}'
   assert {'und','haben','gehen','haus','wasser'} <= lines, 'core words missing'
   print('OK', len(lines), 'entries')
   "
   ```
6. `resources/README.md` — provenance, license, attribution, how to regenerate
7. **Author `samples/synthetic-transcript.json`** — ~50 segments of hand-written fake self-talk in German, with deliberate B2+ vocab seeded (so vocab miner has real signal to find). Schema matches S2 output (same `segments[]` shape). Add `samples/README.md` explaining purpose.
8. Add `baseline` loader: `mine.load_baseline(path: Path = None) -> set[str]` (real impl can land here or in S4)
9. Commit: `data(baseline): add German B1 baseline wordlist + synthetic sample transcript`

### Verification

```bash
test -f resources/baseline-de-b1.txt
.venv/Scripts/python -c "
lines = set(open('resources/baseline-de-b1.txt', encoding='utf-8').read().splitlines())
assert 3000 <= len(lines) <= 5000, f'wrong size: {len(lines)}'
assert {'und','haben','gehen','haus','wasser'} <= lines, 'core words missing'
"
test -f resources/README.md
test -f samples/synthetic-transcript.json
.venv/Scripts/python -c "
import json
data = json.load(open('samples/synthetic-transcript.json', encoding='utf-8'))
assert 'segments' in data and len(data['segments']) >= 30
"
```

### Exit criteria

- Baseline file exists with 3000–5000 entries, core words present
- Provenance + license documented
- Synthetic transcript exists, schema valid
- Commit on `s3-baseline`

---

## S4 — Vocab mine

**Branch:** `s4-mine`
**Depends on:** S2, S3
**Tier:** strongest

### Context brief

Input: `data/transcripts/*.json` (from S2) + `resources/baseline-de-b1.txt` (from S3).
Output: `data/out/unknown.json` — list of unknown-word entries with provenance.

Pipeline:
1. Load all transcripts
2. For each segment, run spaCy `de_core_news_lg` on the text
3. For each token: keep if `pos_` in {NOUN, VERB, ADJ, ADV}; skip if `is_stop`, `is_punct`, `is_space`, `is_digit`, `is_currency`, or `ent_type_` in {PER, LOC, ORG} (proper-noun filter)
4. Lemma = `token.lemma_.lower()` for non-nouns; for nouns keep `token.lemma_` capitalized (German convention) but compare lowercase against baseline
5. Aggregate by lemma across all transcripts → `Counter`
6. Filter: `freq >= 2` (cuts STT hallucinations / hapax errors) AND lemma not in baseline
7. For each surviving lemma, attach: best example sentence (longest segment containing it), source file, start timestamp (for audio snippet later)

Output schema:
```json
[
  {
    "lemma": "verwirklichen",
    "pos": "VERB",
    "gender": null,
    "freq": 4,
    "first_seen": { "source": "2026-05-12.mp4", "start": 142.3, "sentence": "Ich möchte das verwirklichen, was ich..." }
  },
  ...
]
```

Edge cases to handle:
- Compound words (German is heavy here): spaCy lemmatizes most; if `Donnerstagabend` not in baseline, that's correct — it's a "real" unknown for the deck
- Verb separation: spaCy joins separable verbs in lemmatization (`anrufen` not `ruf_an`)
- Filler words: `halt`, `ja`, `nee` — these are stopwords or in baseline; if leakage, add small `resources/ignore.txt` for hand-curated filler list and skip those
- Capitalization: German nouns are capitalized; preserve in output for Anki readability

### Tasks

1. `mine.py`:
   - `load_baseline(path: Path) -> set[str]` (lowercase set)
   - `load_ignore(path: Path | None) -> set[str]`
   - `mine_vocab(transcripts_dir: Path, baseline: set[str], ignore: set[str], min_freq: int = 2) -> list[dict]`
   - returns list matching the schema above
2. Create `resources/ignore.txt` with handful of starter entries (`halt`, `irgendwie`, `quasi`, `also`, `naja`)
3. Tests:
   - `test_mine_pos_filter` — synthetic transcript with mixed POS, assert only NOUN/VERB/ADJ/ADV survive
   - `test_mine_baseline_filter` — known word in baseline should be excluded
   - `test_mine_freq_cutoff` — hapax (freq=1) excluded
   - `test_mine_proper_noun_filter` — "Berlin" excluded
   - `test_mine_umlaut_roundtrip` — input contains `ä/ö/ü/ß`, assert correct lemmas in output (UTF-8 invariant guard)
4. Wire to CLI later (S6); for now `python -m self_talk_coach.mine samples/ -o data/out/unknown.json` should work via `if __name__ == "__main__"`
5. Commit: `feat(mine): spaCy-based vocab miner with B1 baseline filter`

### Verification

```bash
# Runs against samples/ (no dependency on S2 having produced real transcripts)
.venv/Scripts/python -m self_talk_coach.mine samples/ -o data/out/unknown.json
test -f data/out/unknown.json
.venv/Scripts/python -c "
import json
data = json.load(open('data/out/unknown.json', encoding='utf-8'))
assert len(data) >= 5, 'sample should surface at least 5 unknowns'
print(len(data), 'candidates')
print(data[0])
"
.venv/Scripts/python -m pytest -q
```

### Exit criteria

- `unknown.json` produced from `samples/`, schema valid, ≥5 candidates surfaced
- All 5 unit tests green (incl. umlaut roundtrip)
- POS filter + baseline filter + proper-noun filter + freq cutoff working
- Commit on `s4-mine`

---

## S5 — Enrich + Anki export

**Branch:** `s5-enrich-anki`
**Depends on:** S4
**Tier:** strongest

### Context brief

Two stages in one PR — enrichment and packaging are interlinked (genanki needs the enriched fields).

**Enrich:** for each entry in `unknown.json`, call Claude API (model = `claude-haiku-4-5` for speed/cost — alias, SDK resolves; allow override via `--model`) with a structured prompt asking for: clean DE definition, EN translation, grammatical info (gender for nouns, separable-prefix marker for verbs, comparative/superlative for adjectives), one polished example sentence that re-uses the user's own context where possible. Output JSON; validate with Pydantic.

**Use prompt caching (HARD requirement per global rules / `~/.claude/skills/claude-api`):** the system prompt + few-shot examples are static across all calls → mark them with `cache_control: {"type": "ephemeral"}` so we hit the cache on every word after the first.

**Gotcha:** Anthropic prompt caching has a **1024-token minimum** for the cacheable prefix. A short system prompt will silently NOT cache. Pad few-shot examples to ≥1024 tokens (3–5 worked-example cards is usually enough) and **verify it cached** by asserting `response.usage.cache_creation_input_tokens > 0` on first call and `cache_read_input_tokens > 0` on second.

**Cost guard:** default `--max-cards 200` × ~500 tokens out = ~100k output tokens (small). Cap prevents runaway corpus.

**Anki export:** genanki `Model` with fields = [Front (lemma + gender/POS marker), Back (DE def, EN def, example, source-timestamp)]. One `Deck` per run. Tag cards by source file. Write to `data/out/vokabeln-YYYY-MM-DD.apkg`.

### Tasks

1. `enrich.py`:
   - Pydantic schema: `EnrichedCard(lemma, pos, gender, definition_de, definition_en, example_de, example_en, notes, source: str, timestamp: float, original_sentence: str)` — `source/timestamp/original_sentence` carry the provenance from `unknown.json.first_seen.*` through to the Anki card (preserves "where you said it" link)
   - `enrich_one(client, lemma_entry: dict) -> EnrichedCard` — calls Claude with cached system prompt; copies `source/timestamp/original_sentence` from input directly (NOT regenerated by LLM)
   - `enrich_all(entries: list[dict], max_cards: int = 200) -> list[EnrichedCard]` — iterates with progress, handles rate limits + retries (use `anthropic` SDK built-in retries)
   - System prompt + few-shot lives in `enrich.py` as constants with `cache_control` set; few-shot block padded to ≥1024 tokens
   - On first call, log `usage.cache_creation_input_tokens` to console; on subsequent, log `cache_read_input_tokens` so user can confirm cache hits
2. `anki.py`:
   - `build_deck(cards: list[EnrichedCard], deck_name: str) -> genanki.Deck`
   - Fields: `Front` (lemma + gender/POS marker), `Back_DE` (DE def + DE example), `Back_EN` (EN def + EN example), `Source` (filename + timestamp like "2026-05-12.mp4 @ 142.3s"), `OriginalSentence` (the user's own utterance — so card reminds them of their own context)
   - `export(deck: genanki.Deck, out_path: Path)` — open file with binary mode (`.apkg` is a zip)
   - Model defined with stable `model_id` (random fixed int, hardcoded once) so re-imports update existing cards
3. Tests:
   - `test_enrich_schema` — mock Claude response, assert Pydantic parses
   - `test_anki_export` — build deck with 2 fake cards, export, assert `.apkg` file is valid zip with expected entries
4. CLI wire (preview, finalized in S6): `python -m self_talk_coach.enrich data/out/unknown.json -o data/out/enriched.json` and `python -m self_talk_coach.anki data/out/enriched.json -o data/out/vokabeln.apkg`
5. Update `.env.example` with comment about `ANTHROPIC_API_KEY`
6. Commit: `feat(enrich+anki): Claude enrichment + Anki .apkg export`

### Verification

```bash
# Real API call (small slice)
.venv/Scripts/python -m self_talk_coach.enrich data/out/unknown.json -o data/out/enriched.json --max-cards 5
test -f data/out/enriched.json
.venv/Scripts/python -m self_talk_coach.anki data/out/enriched.json -o data/out/vokabeln.apkg
test -f data/out/vokabeln.apkg
.venv/Scripts/python -m pytest -q
```

**Manual:** import `vokabeln.apkg` into AnkiDroid / Anki desktop → 5 cards appear with DE+EN+example.

### Exit criteria

- Claude API integration works (real call succeeds for ≥5 lemmas)
- Cache hit confirmed in second-call latency (or via response `usage.cache_read_input_tokens`)
- `.apkg` opens cleanly in Anki
- Tests green
- Commit on `s5-enrich-anki`

---

## S6 — CLI wire + synthetic sample

**Branch:** `s6-cli`
**Depends on:** S5
**Tier:** default

### Context brief

Glue everything via `typer`. Single entry command `stc` (short for self-talk-coach). Sub-commands:
- `stc ingest <input-dir>` — videos → wavs → transcripts
- `stc mine` — transcripts → unknown.json
- `stc enrich [--max-cards N]` — unknown.json → enriched.json
- `stc pack` — enriched.json → vokabeln.apkg
- `stc run <input-dir>` — full pipeline end-to-end

Add `console_scripts` entry in `pyproject.toml` so `stc` is on PATH after `pip install -e .`.

Synthetic sample data: a `samples/` dir with one short hand-authored German transcript (no real audio) so the public-facing demo path doesn't require uploading audio. Sample feeds straight into `stc mine` → `stc enrich --max-cards 5` → `stc pack`. README will reference this.

### Tasks

1. `cli.py` — `typer.Typer()` app, 5 sub-commands above, sensible defaults, `--help` text in DE+EN-mixed style ("Transcribes / Transkribiert ...")
2. `pyproject.toml` — add `[project.scripts]` `stc = "self_talk_coach.cli:app"`
3. Reinstall: `pip install -e .` so `stc` registers
4. Create `samples/synthetic-transcript.json` — hand-authored ~50 segments of fake "self-talk" mixing common + B2-level vocab
5. End-to-end smoke test `tests/test_e2e.py`:
   - Use `samples/synthetic-transcript.json` (no audio, no Whisper call)
   - Run mine → enrich (with mocked Claude) → pack
   - Assert `.apkg` produced
6. README "Quickstart" section updated with `stc run samples/` flow
7. Update BACKLOG: tick off S1–S6, log any deferred work (RAG journal V2 → S2 phase)
8. Commit: `feat(cli): typer entry + synthetic sample for end-to-end demo`

### Verification

```bash
stc --help                                    # shows all sub-commands
stc mine samples/                             # works on synthetic
stc enrich --max-cards 5                      # mocked or real
stc pack                                      # produces .apkg
.venv/Scripts/python -m pytest -q             # all green incl. test_e2e
```

### Exit criteria

- `stc` command works after fresh `pip install -e .`
- All 5 sub-commands runnable
- E2E test green
- README quickstart accurate
- Commit on `s6-cli`

---

## S7 — Private GitHub repo + push

**Branch:** `main` (final merge target)
**Depends on:** S6
**Tier:** default

### Context brief

Create private repo `Sumanthreddy-DE/self-talk-coach`, push all branches, optionally squash-merge feature branches into `main`. Keep private until V1 is reviewed; flip to public later (separate task, not this plan).

Per global rules:
- `git push` is blocked by hook → agent CANNOT run it; agent must hand off to user via `! git push ...`
- No `Co-Authored-By` lines anywhere
- Use `gh repo create --private` (no push step in that command — agent CAN run create, just not push)

### Tasks

1. `gh repo create Sumanthreddy-DE/self-talk-coach --private --source . --remote origin --description "Personal German vocab miner: self-talk videos → Anki cards via Whisper + spaCy + Claude"`
   - This step does NOT push (no `--push` flag)
2. Verify remote: `git remote -v`
3. Merge feature branches into `main` locally (if branches were used in S1–S6): `git checkout main && git merge --no-ff s1-scaffold && ...` OR rebase, your call
4. Verify working tree clean: `git status` → nothing to commit
5. **Hand-off to user** — print this exact block as the deliverable:
   ```
   ! git -C "C:/Users/suman/Desktop/Docs/Job/Projects/self-talk-coach" push -u origin main
   ```
6. After user pushes, verify: `git fetch && git rev-list --left-right --count main...origin/main` → expect `0 0`
7. **Do NOT** modify `Sumanthreddy-DE/Sumanthreddy-DE` profile README pin list — repo is private, must not appear in pins until a future "go public" plan explicitly handles the flip. Profile pin set stays at current six (per memory `project_github-profile.md`).
8. **Em-dash sweep:** before push, grep entire `README.md` (DE + EN sections) for `—` (U+2014); replace with `–` (U+2013) Gedankenstrich. Per global lesson `lessons_em-dash-ai-tell-de.md`.
   ```bash
   .venv/Scripts/python -c "
   import re, pathlib
   for p in pathlib.Path('.').rglob('*.md'):
       t = p.read_text(encoding='utf-8')
       if '—' in t:
           p.write_text(t.replace('—', '–'), encoding='utf-8')
           print('swept', p)
   "
   ```
8. Final commit (if any cleanup needed): `chore: prepare V1 for private repo push`

### Verification

```bash
gh repo view Sumanthreddy-DE/self-talk-coach --json visibility,name,isPrivate
# expect: {"visibility":"PRIVATE","name":"self-talk-coach","isPrivate":true}
git remote -v   # origin → github.com:Sumanthreddy-DE/self-talk-coach
git status      # clean
# After user push:
git rev-list --left-right --count main...origin/main   # 0 0
```

### Exit criteria

- Private repo exists on GitHub under Sumanthreddy-DE
- `gh repo view ... --json visibility` returns `PRIVATE`
- Remote configured (`origin` → SSH or HTTPS)
- Local main is clean and merged
- **Em-dash sweep complete** — `grep -r "—" *.md docs/` returns empty
- **Profile pins untouched** — `Sumanthreddy-DE/Sumanthreddy-DE` repo unchanged (no commits in this session)
- Push handed off to user with exact `! git push -u origin main` command
- After user push: local main = remote main (0 0 from rev-list)
- BACKLOG.md: all S1–S7 in "Done this session"

---

# Plan mutation protocol

If a step needs to change after this plan is finalized:

- **Split** a step into 2+ → renumber subsequent steps with `.5` suffix (`S4.5`) to avoid breaking references. Update dep graph.
- **Insert** a new step → append as `S{n}` between (e.g., `S2.5`).
- **Skip** a step → leave header with `**Status: SKIPPED — <reason>**` and update deps.
- **Reorder** → only allowed if dep graph permits; document rationale at top of "Steps" section.
- **Abandon** plan → move file to `Archive/plans/` with a one-line reason at top.

Every mutation = a commit on the plan branch itself before resuming work.

---

# V2 hooks (NOT in this plan)

These are explicitly out of scope for V1. Capture for next plan:

- **RAG journal** — feed same `transcripts/*.json` into chromadb or sqlite-vec; `stc ask "<question>"` queries via Claude RAG
- **Audio snippet attach** — embed 5-sec audio clips into Anki cards using genanki media
- **Streamlit dashboard** — browse transcripts + vocab visually
- **Spaced-repetition stats sync** — read Anki review log back to weight which lemmas need more cards
- **Mood / theme tagging** — LLM tags each transcript with topic + sentiment over time
- **Public flip** — go-public checklist: scrub `.git` history, license file, public README polish, GitHub pin

---

# Acceptance for whole plan

The plan is "done" when:

1. `Sumanthreddy-DE/self-talk-coach` exists as private repo
2. Cloning fresh + `pip install -e ".[dev]"` + `python -m spacy download de_core_news_lg` + `cp .env.example .env` + paste API key + `stc run samples/` produces a `.apkg` end-to-end
3. README explains usage in DE + EN
4. No real audio/PII in git history
5. Tests green
6. User imports the `.apkg` into Anki and confirms cards look usable

Once acceptance met → mark V1 complete in BACKLOG, optional → spin V2 plan.
