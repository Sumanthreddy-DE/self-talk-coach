# STATE — self-talk-coach

<!-- Machine-maintained by save-session Step 6b. Do not hand-edit. -->

Status: active
Last touched: 2026-08-27

## What
German self-talk coaching tool (V1 weekend MVP): analyze spoken German practice audio against CEFR vocabulary baseline. Private repo Sumanthreddy-DE/self-talk-coach. Projects-level repo — sessions launch from THIS folder.

## Done
- 2026-08-27: moved out of `Myself/` to `Projects/self-talk-coach/`. Own Claude slug created (`C--Users-suman-Desktop-Docs-Job-Projects-self-talk-coach`); the project memory now lives there as a pointer to these repo docs. Pre-move sessions stay in the Myself slug.
- S1 + S3 slices shipped (commits caea308, 16de6aa), pushed
- 4000-lemma CEFR baseline via wordfreq (MIT) + spaCy lemmatize — license-clean, sidesteps Goethe/Cambridge PDFs
- 43-segment synthetic sample; 3 ADRs; pytest 3/3 green

## Doing
- Nothing in progress

## Pipeline
- S2: audio ingest + transcription (Whisper medium + int8 default)

## Resume here
Build S2: ingest pipeline + Whisper transcription, wire to existing lemma analysis.

## Landmines
- `.venv` was deleted in the 2026-08-27 move (venvs hardcode absolute paths). Run `python -m venv .venv` before the next session.
- Typer: single registered command auto-promotes to root and breaks subcommand routing — always keep ≥2 commands registered
- wordfreq+spaCy baseline is deliberate (licensing) — don't swap in scraped Goethe lists
