# Local-First German Learning Core Design

**Date:** 2026-05-31
**Status:** Approved direction, pending implementation plan
**Project:** self-talk-coach

## Purpose

`self-talk-coach` is a local-first German self-talk learning system. The user records daily German selfie videos about their day so they are forced to speak about varied topics, use varied vocabulary, and practice natural grammar.

The system imports those videos, organizes them locally, transcribes German speech, stores transcripts in a durable SQLite database, analyzes language-learning signals, and creates reviewable learning candidates. The user decides what becomes practice material.

## Non-Goals

This project is not a diary, personal memory system, emotional reflection tool, or RAG system over life events. The content of the day is useful only because it creates varied German input.

Out of scope for the first implementation:

- Personal memory search over past life events
- Emotional or life-pattern analytics
- Cloud sync
- Supabase backend
- Multi-speaker diarization
- Fully automatic card generation without review
- Dashboard UI before the database and CLI core are reliable

Supabase remains a later option. The first implementation is local-first, with schema and data-access choices kept portable enough that a future Supabase sync/backend layer is possible.

## Product Shape

The core workflow is:

```text
daily video
-> import into local media library
-> transcribe German speech
-> store transcript segments
-> analyze corrections and upgrades
-> review queue
-> approved practice items
-> Anki/drills/reports
```

The database is the source of truth. JSON, Markdown, Anki packages, and reports are exports or debug artifacts, not primary application state.

The primary feedback modes are:

- **Correction:** identify incorrect or weak German.
- **Upgrade:** suggest more natural, richer, or more precise German.

## Local Storage Layout

The application owns a managed local workspace under `data/`:

```text
data/
  db/
    self_talk_coach.sqlite
  media/
    inbox/
    processing/
    processed/YYYY/MM/
    failed/
    archived/
  exports/
    transcripts/
    anki/
    reports/
```

The user drops videos into `data/media/inbox/`. The app imports from there, computes metadata and a content hash, infers a session date, and moves successfully imported files into `processed/YYYY/MM/`.

Incoming filenames are treated as unreliable. The app preserves the original filename in the database but creates stable managed names using inferred session time plus a short hash, for example:

```text
2026-05-31_2130_ab12cd34.mp4
```

Session date inference priority:

1. Video metadata creation time, if available.
2. Filesystem modified time.
3. Import time.

The database stores `date_confidence` so uncertain dates can be repaired later.

## CLI Surface

The CLI is the control surface over durable state:

```text
stc init
stc import
stc transcribe
stc analyze
stc review list
stc review show <id>
stc review approve <id>
stc review reject <id>
stc review defer <id>
stc export anki
```

Every command must be idempotent. Re-running a command should skip completed work, continue pending work, or report recoverable failures without duplicating records.

## Architecture

The first implementation should stay Python-based and build around these modules:

- `db`: SQLite connection, migrations, schema versioning, repositories.
- `media`: inbox scanning, file hashing, metadata extraction, managed file moves.
- `transcribe`: ffmpeg audio extraction and faster-whisper transcription with German forced.
- `analyze`: language-learning candidate generation.
- `review`: approval/rejection/defer workflows.
- `practice`: approved practice item creation.
- `export`: Anki and later report exports.
- `cli`: Typer commands that orchestrate services.

Implementation should keep domain logic separate from CLI printing so a future dashboard can reuse the same services.

## Data Model

### `media_files`

Stores imported videos/audio.

Fields should include:

- `id`
- `original_filename`
- `original_path`
- `managed_path`
- `content_hash`
- `size_bytes`
- `duration_seconds`
- `inferred_session_at`
- `date_confidence`
- `status`
- `error_message`
- `created_at`
- `updated_at`

Expected statuses include `imported`, `transcribed`, `analyzed`, `failed`, and `archived`.

### `transcripts`

Stores one transcription result per media file.

Fields should include:

- `id`
- `media_file_id`
- `language`
- `model`
- `duration_seconds`
- `status`
- `created_at`
- `error_message`

### `transcript_segments`

Stores timestamped transcript chunks.

Fields should include:

- `id`
- `transcript_id`
- `start_seconds`
- `end_seconds`
- `text`
- optional confidence or quality metadata

### `learning_candidates`

Stores analysis suggestions before user approval.

Candidate types include:

- `grammar_correction`
- `phrase_upgrade`
- `vocab_candidate`
- `collocation`
- `article_gender`
- `sentence_rewrite`
- `filler_pattern`
- `recurring_pattern`

Fields should include:

- `id`
- `candidate_type`
- `transcript_segment_id`
- `original_text`
- `suggested_text`
- `explanation`
- `severity`
- `usefulness`
- `status`
- `producer`
- `created_at`
- `updated_at`

Expected statuses include `pending`, `approved`, `rejected`, and `deferred`.

### `practice_items`

Stores only approved learning material.

Fields should include:

- `id`
- `learning_candidate_id`
- `practice_type`
- `front`
- `back`
- `notes`
- `export_status`
- `created_at`
- `updated_at`

### `review_events`

Stores user decisions over time.

Fields should include:

- `id`
- `learning_candidate_id`
- optional `practice_item_id`
- `action`
- `note`
- `created_at`

This keeps the central invariant clear:

```text
analysis suggestion != approved practice
```

## Analysis Scope

The first analysis layer should create learning candidates in two families.

### Correction Candidates

Corrections cover German that is wrong, weak, or likely to fossilize:

- Article or gender errors
- Case and preposition issues
- Verb position
- Tense or modality mistakes
- Unnatural grammar
- English-style phrasing
- Filler or repetition patterns

### Upgrade Candidates

Upgrades cover German that is understandable but could become more natural, richer, or more precise:

- More natural phrasing
- Stronger verbs
- Useful synonyms
- Collocations
- Sentence rewrites
- B1/B2/C1 alternatives
- Everyday native-like expressions

## Review Workflow

Analysis creates candidates, not final cards or drills.

```text
stc analyze
  -> creates pending candidates

stc review list
  -> shows pending candidates grouped by session, type, or usefulness

stc review show <id>
  -> shows source segment, original text, suggestion, and explanation

stc review approve <id>
  -> creates a practice item

stc review reject <id>
  -> records rejection and keeps the candidate out of practice

stc review defer <id>
  -> keeps the candidate for later review
```

The app should later learn from review behavior. If the user repeatedly rejects a candidate type, the analysis layer should lower its priority or produce fewer similar suggestions. If the user approves a type often, the app should surface more of that type.

## Milestones

### Milestone 1: Local Database And Media Library

Implementation status: planned in `docs/superpowers/plans/2026-05-31-local-db-media-library.md`; completed when `stc init` and `stc import` pass the full test suite.

- Add SQLite schema and migrations.
- Add `stc init`.
- Create managed media folders.
- Import videos from `data/media/inbox/`.
- Hash files and infer session dates.
- Move files into `processed/YYYY/MM/`.
- Track status and errors.

### Milestone 2: Transcription Storage

- Extract audio with ffmpeg.
- Transcribe with faster-whisper.
- Force German transcription.
- Store transcripts and timestamped segments in SQLite.
- Avoid duplicate transcriptions on rerun.
- Export transcripts to JSON or Markdown for inspection.

### Milestone 3: First Language Analysis

- Create vocabulary candidates.
- Create phrase upgrades.
- Create basic correction candidates.
- Link every candidate to a transcript segment.
- Store candidates as pending review items.

### Milestone 4: Review Queue

- List pending candidates.
- Show candidate details.
- Approve, reject, and defer candidates.
- Create practice items only after approval.
- Record review history.

### Milestone 5: Practice Export

- Export approved practice items to Anki.
- Track export status.
- Support richer drills later, such as cloze and rewrite exercises.

## Design Constraints

- Local-first: no cloud dependency in the first implementation.
- Privacy-first: no real media or transcripts committed to git.
- German-only V1: assume single-speaker German self-talk.
- Durable state: every processing step writes structured records to SQLite.
- Idempotent commands: reruns should be safe.
- Review gate: no automatic practice generation without approval.
- Future-compatible: keep schema and repository boundaries friendly to later Supabase/Postgres sync.

