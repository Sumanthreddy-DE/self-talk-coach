# STATE — self-talk-coach

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: active
Last touched: 2026-10-05

## What
German self-talk coaching tool (V1 weekend MVP): analyze spoken German practice audio against CEFR vocabulary baseline. Public repo Sumanthreddy-DE/self-talk-coach (made public 2026-10-07, MIT; README rewritten the same day). Projects-level repo — sessions launch from THIS folder.

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

## Doing
- Phase 1 conversation partner: code done on `feat/conversation-loop`; real-LLM verification run + Step 8 + merge pending

## Pipeline
- M3 first-language-analysis (plan written 5f7670a, not started — no `analyze.py`)
- review-queue (BACKLOG S2)

## Resume here
From repo root (PowerShell): `stc talk --scenario "Daily"` with gateway credits back; test SPACE during partner speech, 13 s silence, r/s/t, a deliberate error; check SQLite, record result in spec (Phase 1 Step 8), merge `feat/conversation-loop` → main.

## Landmines
- `stc talk` needs a real Windows console (msvcrt keys) and the repo root as cwd (`data/` is relative).
- `av<19` pin is load-bearing: av 19 breaks faster-whisper 1.2.1 (`open(metadata_errors=)`).
- LLM via dlabkeys reseller gateway: models listed ≠ available; plan can lapse mid-day (429). Fallback warning shows it.
- Typer: single registered command auto-promotes to root and breaks subcommand routing — always keep ≥2 commands registered
- wordfreq+spaCy baseline is deliberate (licensing) — don't swap in scraped Goethe lists
