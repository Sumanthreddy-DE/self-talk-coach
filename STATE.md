# STATE — self-talk-coach

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: paused
Last touched: 2026-09-28

## What
German self-talk coaching tool (V1 weekend MVP): analyze spoken German practice audio against CEFR vocabulary baseline. Private repo Sumanthreddy-DE/self-talk-coach. Projects-level repo — sessions launch from THIS folder.

## Done
- 2026-08-27: moved out of `Myself/` to `Projects/self-talk-coach/`. Own Claude slug created (`C--Users-suman-Desktop-Docs-Job-Projects-self-talk-coach`); the project memory now lives there as a pointer to these repo docs. Pre-move sessions stay in the Myself slug.
- S1 + S3 slices shipped (commits caea308, 16de6aa), pushed
- 4000-lemma CEFR baseline via wordfreq (MIT) + spaCy lemmatize — license-clean, sidesteps Goethe/Cambridge PDFs
- 43-segment synthetic sample; 3 ADRs
- M1 local DB + media library (`init`, `import`) shipped 2026-05-31 (74bb4a2..f5f04e1)
- M2 transcription storage (faster-whisper, `transcribe`, `export transcripts`) shipped 2026-06-01/02 (0e55ec4..74bf901)
- 43 tests across 7 files (last green run 2026-06-02; not re-run since the venv was deleted)
- 2026-09-28: triaged plan headers — M1/M2 plans done, M3 first-language-analysis paused

## Doing
- Nothing in progress — project paused 2026-09-28

## Pipeline
- M3 first-language-analysis (plan written 5f7670a, not started — no `analyze.py`)
- review-queue (BACKLOG S2)

## Resume here
Paused. On resume: recreate `.venv`, run pytest, then execute `docs/superpowers/plans/2026-06-02-first-language-analysis.md`.

## Landmines
- `.venv` was deleted in the 2026-08-27 move (venvs hardcode absolute paths). Run `python -m venv .venv` before the next session.
- Typer: single registered command auto-promotes to root and breaks subcommand routing — always keep ≥2 commands registered
- wordfreq+spaCy baseline is deliberate (licensing) — don't swap in scraped Goethe lists
