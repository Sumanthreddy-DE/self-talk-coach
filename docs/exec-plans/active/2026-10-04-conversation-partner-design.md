# Conversation partner — design spec

**Status:** active
**Last verified:** 2026-10-04
**Origin:** brainstorm 2026-10-04 (started in claude-lab, finished here) → research brief `docs/references/2026-10-04-voice-partner-research.md` → grill-with-docs (CONTEXT.md + ADR 0004 updated).

## Goal

Train German speaking under surprise. The learner (B1, telc B1 2026-09-04: Hören/Lesen weakest) freezes when asked sudden, random questions — even in English. The partner asks unpredictable questions by voice, helps without answering for him, and trains listening on purpose.

Success, measured week over week from stored data:
- median **freeze time** falls
- **listening aid** use per partner turn falls
- recurring errors in the **session report** shrink

Terms used below are defined in `CONTEXT.md` (conversation, partner, turn, scenario card, freeze time, help ladder, rescue phrase, listening aid, recast, session report, live transcript, review transcript).

## Scope

**v1 (laptop, Windows, terminal):**
- `stc talk` starts a conversation: free talk or a scenario card.
- Toggle push-to-talk key: press to start speaking, press to stop.
- Partner speaks; its text is hidden. Keys during/after a partner turn: replay, slower, show text.
- Help ladder on silence: 4 s nudge (fixed phrase), 8 s starter phrase, 12 s simpler rephrase — all by voice, pre-generated, never shown before the learner speaks.
- Comprehension check every 4th partner turn: "Erzähl kurz nach, was ich gerade gesagt habe." (retelling).
- Partner recasts learner errors in passing; no grammar explanation during the conversation.
- Every turn saved immediately: text, both audio sides (Opus), timings, events.
- `stc report <id>` (auto-run at conversation end): review transcription + Claude analysis → session report; errors land in `learning_candidates`.

**Not in v1:** local LLM/TTS, phone, voice-activity detection, barge-in, voice cloning, Supabase/sync, question banks beyond the existing Myself ones (BACKLOG `question-banks-missing`).

## Stack

| Slot | v1 | Swap later |
|---|---|---|
| STT (live) | faster-whisper, CPU int8; `small` or `medium` — decided by spike S1 | RealtimeSTT for first-word VAD |
| STT (review) | faster-whisper `medium` (existing M2 code), word timestamps + probabilities | `large-v3` overnight |
| LLM | Claude, `claude-haiku-4-5-20251001` default; Sonnet for comparison; prompt caching on system prompt | local via same interface |
| TTS | Azure Neural German (`de-DE-*Neural`), free tier 0.5M chars/month | ElevenLabs ($1 starter for ear test only), OmniVoice/Piper local |
| Storage | existing SQLite + `data/` media root | — |
| Audio I/O | `sounddevice` (mic + playback) — confirmed by spike S4 | — |
| Encoding | ffmpeg → Opus (ffmpeg already a dependency) | — |

Architecture rationale: ADR 0004 (own loop, not Pipecat/LiveKit). Whether RealtimeTTS wraps Azure or we call the Azure SDK directly is decided in spike S2: we need the synthesized audio as bytes (to store and replay) and a rate control (for "slower"); RealtimeTTS is primarily a stream-to-speaker library.

## Components

Each module has one job and is testable with fakes.

| Module | Responsibility | Depends on |
|---|---|---|
| `conversation/audio_io.py` | Record mic to buffer between toggle presses; play audio bytes; non-blocking key reads (`msvcrt` on Windows). | sounddevice |
| `conversation/stt.py` | `LiveTranscriber` protocol; faster-whisper impl on in-memory audio. Reuses `transcribe.py` model loading. | transcribe.py |
| `conversation/partner.py` | Build prompt, call Claude, parse `PartnerTurn` (pydantic). | anthropic, question_bank |
| `conversation/tts.py` | `Speaker` protocol: `synthesize(text, rate) -> bytes`. Azure impl. | Azure SDK or RealtimeTTS |
| `conversation/question_bank.py` | Parse Markdown banks (numbered lists under `##` sections) into seeds; pick next seed at random with no-repeat across conversations; boost seeds the learner froze on. | — |
| `conversation/help_ladder.py` | Pure state machine: given elapsed silence, return next ladder step. Timings configurable (default 4/8/12 s). | — |
| `conversation/session.py` | Orchestrates one conversation loop; writes each turn to DB before the next one starts. | all above, db |
| `conversation/report.py` | Post-conversation: review-transcribe learner audio, Claude analysis, write `learning_candidates`, render Markdown report. | transcribe.py, anthropic, db |
| `cli.py` | `stc talk [--scenario <name>]`, `stc report <conversation_id>`. Keeps ≥2 Typer commands (landmine in STATE.md). | session, report |

### `PartnerTurn` (one Claude call per partner turn)

```json
{
  "reply": "Und warum möchtest du gerade bei uns arbeiten?",
  "recast": "Ah, du hast gestern gearbeitet.",
  "starter_phrase": "Ich möchte bei Ihnen arbeiten, weil …",
  "simpler_rephrase": "Warum willst du hier arbeiten?",
  "topic_jump": false
}
```

`recast` is null when no recast is needed; it is spoken before `reply`. `starter_phrase` and `simpler_rephrase` are stored but only spoken if the help ladder reaches them.

### Partner prompt rules

- Persona: native speaker from Baden-Württemberg, colloquial, short turns (1–2 sentences), real follow-ups.
- **No flattery**: no "Super!", "Toll gemacht!", no praise after answers (research: AI partners read as "sycophantic and corporate").
- Language level: B1, occasional slight stretch. Measured, not enforced (see Metrics).
- Next question topic comes from the code-picked seed ("ask about X — as a natural follow-up or a sudden topic jump"); Claude phrases it, does not choose it.
- Learner profile (B1, lives Reutlingen, late shifts at McDonald's Mössingen, job-interview goal) + last conversation's summary in the cached system prompt. Profile lives in `data/learner-profile.md` (gitignored, never committed — PII; repo is planned to go public).

### Question banks

Read in place, never copied into the repo (PII; repo is planned to go public):
- `Myself/German-Learning/question-bank.md` (50 questions: interview core/profile/behavioral, office German, daily life)
- `Myself/Interview-Prep/interview-questionnaire-de.md` (60 interview questions with the learner's own model answers — used in the session report as "what you could have said")

Paths via `.env` (`STC_QUESTION_BANKS=path1;path2`). A scenario card = one `##` section (or a named group of sections). Free talk = all daily-life/office sections. Missing banks: BACKLOG `question-banks-missing`.

## Data model

New tables (migration in `db.py`, same style as existing `CREATE TABLE IF NOT EXISTS`):

**`conversations`** — id, started_at, ended_at, scenario (nullable = free talk), stt_model, llm_model, tts_voice, status (`active` / `completed` / `aborted`), report_status (`pending` / `done` / `failed`).

**`turns`** — id, conversation_id, turn_index, speaker (`learner` / `partner`), audio_path (`data/conversations/<id>/turn-007.opus`), text (partner text or learner live transcript), review_text (learner only), review_words_json (word, start, end, probability), seed (partner only), partner_turn_json (full `PartnerTurn`), freeze_seconds (learner only), ladder_step_reached (0–3), replay_count, slower_count, show_text_count, comprehension_check (bool), out_of_baseline_ratio (partner only), created_at.

**`learning_candidates`** — add nullable `turn_id` (FK `turns`). Session-report errors use `producer='conversation'`. M3 (first-language-analysis) and the review queue then serve self-talk and conversations alike.

A conversation contains exactly two voices — learner and AI partner. No real third person is ever recorded (CONTEXT.md boundary).

## Data flow (one exchange)

1. Partner turn: question bank picks seed → Claude returns `PartnerTurn` → TTS synthesizes `recast + reply` → play → save partner turn (text, audio, seed, JSON).
2. Timer starts at playback end. Help ladder fires by elapsed silence until the learner presses the toggle key. Listening-aid keys available throughout; each press logged.
3. Learner presses toggle → records → presses toggle → freeze time stored → live transcript → save learner turn.
4. Live transcript + recent turns → next Claude call. Loop.
5. Every 4th partner turn is a comprehension check (retell); retelling scored in the report, not live.
6. `q` ends the conversation → report runs.

## Session report

Built after the conversation, from review transcripts only:
- Top 3 recurring errors with original → corrected, linked to turns (written to `learning_candidates`)
- Freeze time per question, median, and change vs last 5 conversations
- Help-ladder steps reached; rescue phrases used / missed opportunities
- Listening aids used, per partner turn; hard partner sentences (replayed or show-text) listed for review
- Comprehension checks: retelling accuracy (Claude judges vs the partner's actual text)
- New useful words (existing miner against the baseline)
- For interview seeds: the learner's own model answer from the questionnaire
- Saved as Markdown under `data/conversations/<id>/report.md` and printed

## Error handling

- Every turn committed to DB before the next step → crash or `Ctrl+C` loses at most the in-flight turn; conversation marked `aborted`, report still runnable.
- Claude call fails → retry once → fallback: speak the raw seed question.
- TTS fails → retry once → print partner text (logged as forced show-text, not counted as a listening aid).
- Empty/garbage live transcript → partner says "Wie bitte? Kannst du das nochmal sagen?" (no Claude call).
- Missing API keys or bank paths → fail fast at `stc talk` start with the exact `.env` variable name.
- Report failure → `report_status='failed'`, `stc report <id>` reruns it.

## Metrics (all derived from `turns`)

freeze time (median per conversation), ladder step distribution, listening aids per partner turn, comprehension-check accuracy, partner `out_of_baseline_ratio` (share of lemmas outside `resources/baseline-de-b1.txt` — tighten the prompt if consistently high), tokens + TTS characters per conversation (cost tracking).

## Phase 0 — spikes (gate before building)

Each is a throwaway script under `scripts/spikes/` with results written into this spec.

- **S0 venv:** recreate `.venv`, `pip install -e .[dev]`, run pytest (expect 43 green).
- **S1 whisper error preservation:** learner records ~10 sentences with deliberate typical errors (verb tense auxiliary, case endings, verb position, gender). Transcribe with `small` and `medium` int8 on CPU. Record per model: errors kept vs silently fixed, seconds per turn. Picks the live model. If both fix most errors → test `initial_prompt` with learner-style text, then reconsider STT before building.
- **S2 TTS:** same 5 German sentences via Azure (2–3 voices) and ElevenLabs ($1 starter — cancel after buying). Learner picks by ear. Also confirm: bytes output + rate control (Azure SSML prosody) with RealtimeTTS vs direct SDK.
- **S3 latency + cost:** one scripted 10-exchange run; record STT/Claude/TTS seconds per turn, input/output tokens, TTS characters. Project monthly cost at 30–60 min/day against the ~€5/month target. Verify current Claude Haiku pricing from the live pricing page, not memory.
- **S4 Windows audio + keys:** mic record and playback with the learner's headset via sounddevice; toggle key and listening-aid keys via msvcrt in Windows Terminal.

## Testing

- Unit: help ladder state machine, question-bank parser + picker (no-repeat, freeze boost), `PartnerTurn` parsing (valid / malformed JSON), DB migration + turn persistence, metrics, report assembly — all with fakes for STT/LLM/TTS/audio.
- Integration: `session.py` loop driven by a scripted fake learner (pre-recorded audio + timed key events) and fake partner/speaker — verifies freeze times, ladder firing, persistence order.
- Manual: spikes S1–S4; one real 10-minute conversation before calling v1 done.
- `bash scripts/lint-arch.sh` before each commit (project rule).

## Configuration (`.env`, never committed)

`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `STC_TTS_VOICE`, `STC_LIVE_STT_MODEL`, `STC_QUESTION_BANKS`, `STC_LADDER_SECONDS=4,8,12`. `.env.example` gains these names with empty values.

## Open after v1

- Listening "Stage 1" (text auto-shown after audio) if A proves too hard early on.
- First-word VAD (RealtimeSTT) to replace key-press freeze proxy.
- Local model swaps per slot; phone version; Supabase sync.
- Exam mode (no help ladder) for interview rehearsal.
