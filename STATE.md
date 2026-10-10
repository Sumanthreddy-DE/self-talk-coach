# STATE — self-talk-coach

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: active
Last touched: 2026-10-10

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
- 2026-10-08/09: Deepgram `language=multi` tested and rejected (s6 spike: corrected 7/10 learner errors, garbled 8/28 real turns), keep `de` (fead0b8); Phase 2 plan written + approved (e3bf658, 89eec43)
- 2026-10-10: Phase 2 Tasks 1–10 built on `feat/phase2-report` (54a5014..6b6ab43): `stc report <id>` + auto-report (one Sonnet 5 call, whole-word quote check, ADR 0006), comprehension check every 4th partner turn, Mein Tag mode (`--mein-tag` / menu `m`), vocab miner; 142 tests. `stc report 10` verified on real data (8 findings, 0 invented)

## Doing
- Phase 2 (`docs/exec-plans/active/2026-10-08-phase2-report-mein-tag.md`): Tasks 1–10 committed on `feat/phase2-report`, not pushed; Task 11 live verification open

## Pipeline
- M3 first-language-analysis (plan written 5f7670a, not started — no `analyze.py`)
- review-queue (BACKLOG S2)

## Resume here
User installs spaCy `de_core_news_lg` and pushes `feat/phase2-report`; then Task 11 live: `stc report 3`/`10` (Neue Wörter should appear), McDonald's talk ≥ 9 partner turns (checks at turns 4 and 8), `stc talk --mein-tag` ~5 min with English. Record results in spec, plan → completed/.

## Landmines
- `stc talk` needs a real Windows console (msvcrt keys) and the repo root as cwd (`data/` is relative).
- `av<19` pin is load-bearing: av 19 breaks faster-whisper 1.2.1 (`open(metadata_errors=)`).
- LLM via dlabkeys reseller gateway: models listed ≠ available; plan can lapse mid-day (429). Fallback warning shows it.
- Typer: single registered command auto-promotes to root and breaks subcommand routing — always keep ≥2 commands registered
- wordfreq+spaCy baseline is deliberate (licensing) — don't swap in scraped Goethe lists
