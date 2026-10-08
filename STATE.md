# STATE — self-talk-coach

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: active
Last touched: 2026-10-08

## What
German speaking coach: live voice conversation partner (`stc talk`, role-play scenarios, help ladder) plus a local library of self-talk recordings and transcripts. Weekend-MVP blueprint abandoned 2026-10-07. Public repo Sumanthreddy-DE/self-talk-coach (made public 2026-10-07, MIT; README rewritten the same day). Projects-level repo — sessions launch from THIS folder.

## Done
- 2026-08-27: moved out of `Myself/` to `Projects/self-talk-coach/`. Own Claude slug created (`C--Users-suman-Desktop-Docs-Job-Projects-self-talk-coach`); the project memory now lives there as a pointer to these repo docs. Pre-move sessions stay in the Myself slug.
- S1 + S3 slices shipped (commits caea308, 16de6aa), pushed
- 4000-lemma CEFR baseline via wordfreq (MIT) + spaCy lemmatize — license-clean, sidesteps Goethe/Cambridge PDFs
- 43-segment synthetic sample; 3 ADRs
- M1 local DB + media library (`init`, `import`) shipped 2026-05-31 (74bb4a2..f5f04e1)
- M2 transcription storage (faster-whisper, `transcribe`, `export transcripts`) shipped 2026-06-01/02 (0e55ec4..74bf901)
- 43 tests across 7 files (last green run 2026-06-02; not re-run since the venv was deleted)
- 2026-09-28: triaged plan headers — M1/M2 plans done, M3 first-language-analysis paused
- 2026-10-04/05: live conversation partner designed (spec + ADR 0004/0005), Phase 0 spikes done (Deepgram STT, edge-tts Seraphina, DeepSeek→Sonnet), Phase 1 `stc talk` built on `feat/conversation-loop` — 85 tests; first real conversation (27 turns); SPACE-buffer + silent-fallback bugs fixed
- 2026-10-06/08: Phase 1 verified live on DeepSeek V4 Pro and merged (plan → completed/); keys interrupt partner speech (36b436d); partner prompt fixes — no invented claims, recast-echo guard, repeat on "Wie bitte?", phrase seeds as role-play (9f362d7, a8c2c5c); scenario menu `f` + `w` + start menu (0897d14, 9f2cfe8); McDonald's + cold-call scenario bank in Myself; 108 tests

## Doing
- Daily practice with `stc talk` (scenario menu, McDonald's/cold-call role-plays); next build: Phase 2 session report

## Pipeline
- M3 first-language-analysis (plan written 5f7670a, not started — no `analyze.py`)
- review-queue (BACKLOG S2)

## Resume here
User practises one scenario (`.\.venv\Scripts\stc.exe talk` → 6/7 McDonald's, try `f`/`w`); then test Deepgram `language=multi` on saved learner audio (BACKLOG `mixed-language-stt`); then write Phase 2 plan (session report + Mein Tag + comprehension check + vocab-miner).

## Landmines
- `stc talk` needs a real Windows console (msvcrt keys) and the repo root as cwd (`data/` is relative).
- `av<19` pin is load-bearing: av 19 breaks faster-whisper 1.2.1 (`open(metadata_errors=)`).
- LLM via dlabkeys reseller gateway: models listed ≠ available; plan can lapse mid-day (429). Fallback warning shows it.
- Typer: single registered command auto-promotes to root and breaks subcommand routing — always keep ≥2 commands registered
- wordfreq+spaCy baseline is deliberate (licensing) — don't swap in scraped Goethe lists
