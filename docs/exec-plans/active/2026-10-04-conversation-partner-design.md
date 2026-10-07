# Conversation partner — design spec

**Status:** active
**Last verified:** 2026-10-05
**Origin:** brainstorm 2026-10-04 (started in claude-lab, finished here) → research brief `docs/references/2026-10-04-voice-partner-research.md` → grill-with-docs (CONTEXT.md + ADR 0004 updated).

## Goal

Train German speaking under surprise. The learner (B1, telc B1 2026-09-04: Hören/Lesen weakest) freezes when asked sudden, random questions — even in English. The partner asks unpredictable questions by voice, helps without answering for him, and trains listening on purpose.

Success, measured week over week from stored data:
- median **freeze time** falls
- **listening aid** use per partner turn falls
- recurring errors in the **session report** shrink

Terms used below are defined in `CONTEXT.md` (conversation, partner, turn, scenario card, freeze time, help ladder, rescue phrase, listening aid, recast, session report, learner transcript).

## Scope

**v1 (laptop, Windows, terminal):**
- `stc talk` starts a conversation: free talk or a scenario card.
- Toggle push-to-talk key: press to start speaking, press to stop.
- Partner speaks; its text is hidden. Keys during/after a partner turn: replay, slower, show text, switch to the next scenario card (`w`, added 2026-10-07; the partner starts a fresh scene).
- Help ladder on silence: 4 s nudge (fixed phrase), 8 s starter phrase, 12 s simpler rephrase — all by voice, pre-generated, never shown before the learner speaks.
- Comprehension check every 4th partner turn: "Erzähl kurz nach, was ich gerade gesagt habe." (retelling).
- Partner recasts learner errors in passing; no grammar explanation during the conversation.
- Every turn saved immediately: text, both audio sides (Opus), timings, events.
- `stc report <id>` (auto-run at conversation end): report-LLM analysis of the stored transcripts → session report; errors land in `learning_candidates`.

**Not in v1:** local LLM/TTS, phone, voice-activity detection, voice barge-in (keyboard interrupt during partner speech IS in v1, added 2026-10-06), voice cloning, Supabase/sync, question banks beyond the existing Myself ones (BACKLOG `question-banks-missing`).

## Stack

| Slot | v1 | Swap later |
|---|---|---|
| STT | **Deepgram Nova-3** (`model=nova-3`, `language=de`, `smart_format=false`), cloud, ~0.9 s/turn; one pass serves live + report (word confidences in the same response). ADR 0005. | faster-whisper `medium` as offline fallback (keeps only 3/10 learner errors — not for the error report) |
| LLM | Via OpenAI-compatible gateway (`GATEWAY_BASE_URL`). Partner: **`deepseek-v4-pro`**; automatic fallback to **`claude-sonnet-5`** on error or > 15 s. Session report: `claude-sonnet-5`. | official Anthropic API, local model — same interface |
| TTS | **edge-tts `de-DE-SeraphinaMultilingualNeural`** (free, unofficial; ~3.2 s/sentence); runner-up `de-DE-KatjaNeural` (~0.6 s). Slower = `rate=-25%`. | **Piper `de_DE-thorsten-high`** local offline fallback (~1.6 s); ElevenLabs if quality demands |
| Storage | existing SQLite + `data/` media root | — |
| Audio I/O | `sounddevice` (mic + playback) — confirmed by spike S4 | — |
| Encoding | ffmpeg → Opus (ffmpeg already a dependency) | — |

Architecture rationale: ADR 0004 (own loop, not Pipecat/LiveKit). STT in the cloud: ADR 0005. RealtimeTTS dropped — edge-tts and Piper both return audio files/bytes with rate control directly.

## Components

Each module has one job and is testable with fakes.

| Module | Responsibility | Depends on |
|---|---|---|
| `conversation/audio_io.py` | Record mic to buffer between toggle presses; play audio bytes; non-blocking key reads (`msvcrt` on Windows). | sounddevice |
| `conversation/stt.py` | `LiveTranscriber` protocol; faster-whisper impl on in-memory audio. Reuses `transcribe.py` model loading. | transcribe.py |
| `conversation/partner.py` | Build prompt, call partner LLM (primary → fallback), parse `PartnerTurn` (pydantic). | openai SDK (gateway), question_bank |
| `conversation/tts.py` | `Speaker` protocol: `synthesize(text, rate) -> bytes`. edge-tts impl + Piper fallback impl. | edge-tts, piper-tts |
| `conversation/question_bank.py` | Parse Markdown banks (numbered lists under `##` sections) into seeds; pick next seed at random with no-repeat across conversations; boost seeds the learner froze on. | — |
| `conversation/help_ladder.py` | Pure state machine: given elapsed silence, return next ladder step. Timings configurable (default 4/8/12 s). | — |
| `conversation/session.py` | Orchestrates one conversation loop; writes each turn to DB before the next one starts. | all above, db |
| `conversation/report.py` | Post-conversation: report-LLM analysis of learner transcripts, write `learning_candidates`, render Markdown report. | openai SDK (gateway), db |
| `cli.py` | `stc talk [--scenario <name>]`, `stc report <conversation_id>`. Keeps ≥2 Typer commands (landmine in STATE.md). | session, report |

### `PartnerTurn` (one partner-LLM call per partner turn)

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
- Next question topic comes from the code-picked seed ("ask about X — as a natural follow-up or a sudden topic jump"); the LLM phrases it, does not choose it.
- Learner profile (B1, lives Reutlingen, late shifts at McDonald's Mössingen, job-interview goal) + last conversation's summary in the cached system prompt. Profile lives in `data/learner-profile.md` (gitignored, never committed — PII; repo is planned to go public).

### Question banks

Read in place, never copied into the repo (PII; repo is planned to go public):
- `Myself/German-Learning/question-bank.md` (50 questions: interview core/profile/behavioral, office German, daily life)
- `Myself/Interview-Prep/interview-questionnaire-de.md` (60 interview questions with the learner's own model answers — used in the session report as "what you could have said")

Paths via `.env` (`STC_QUESTION_BANKS=path1;path2`). A scenario card = one `##` section (or a named group of sections). Free talk = all daily-life/office sections. Missing banks: BACKLOG `question-banks-missing`.

## Data model

New tables (migration in `db.py`, same style as existing `CREATE TABLE IF NOT EXISTS`):

**`conversations`** — id, started_at, ended_at, scenario (nullable = free talk), stt_model, llm_model, tts_voice, status (`active` / `completed` / `aborted`), report_status (`pending` / `done` / `failed`).

**`turns`** — id, conversation_id, turn_index, speaker (`learner` / `partner`), audio_path (`data/conversations/<id>/turn-007.opus`), text (partner text or learner transcript), words_json (learner only: Deepgram word, start, end, confidence), seed (partner only), partner_turn_json (full `PartnerTurn`), freeze_seconds (learner only), ladder_step_reached (0–3), replay_count, slower_count, show_text_count, comprehension_check (bool), out_of_baseline_ratio (partner only), created_at.

**`learning_candidates`** — add nullable `turn_id` (FK `turns`). Session-report errors use `producer='conversation'`. M3 (first-language-analysis) and the review queue then serve self-talk and conversations alike.

A conversation contains exactly two voices — learner and AI partner. No real third person is ever recorded (CONTEXT.md boundary).

## Data flow (one exchange)

1. Partner turn: question bank picks seed → partner LLM returns `PartnerTurn` → TTS synthesizes `recast + reply` → play → save partner turn (text, audio, seed, JSON).
2. Timer starts at playback end. Help ladder fires by elapsed silence until the learner presses the toggle key. Listening-aid keys available throughout; each press logged.
3. Learner presses toggle → records → presses toggle → freeze time stored → learner transcript (Deepgram) → save learner turn.
4. Learner transcript + recent turns → next partner-LLM call. Loop.
5. Every 4th partner turn is a comprehension check (retell); retelling scored in the report, not live.
6. `q` ends the conversation → report runs.

## Session report

Built after the conversation from the stored Deepgram transcripts (v1 is single-pass — see ADR 0005):
- Top 3 recurring errors with original → corrected, linked to turns (written to `learning_candidates`)
- Freeze time per question, median, and change vs last 5 conversations
- Help-ladder steps reached; rescue phrases used / missed opportunities
- Listening aids used, per partner turn; hard partner sentences (replayed or show-text) listed for review
- Comprehension checks: retelling accuracy (report LLM judges vs the partner's actual text)
- New useful words (existing miner against the baseline)
- For interview seeds: the learner's own model answer from the questionnaire
- Saved as Markdown under `data/conversations/<id>/report.md` and printed

## Error handling

- Every turn committed to DB before the next step → crash or `Ctrl+C` loses at most the in-flight turn; conversation marked `aborted`, report still runnable.
- Partner LLM fails or > 15 s → same turn to fallback model → if that fails too: speak the raw seed question.
- TTS fails → retry once → print partner text (logged as forced show-text, not counted as a listening aid).
- Deepgram fails → retry once → local faster-whisper `medium` transcribes the turn; turn flagged `stt_fallback` and excluded from error findings.
- Empty/garbage learner transcript → partner says "Wie bitte? Kannst du das nochmal sagen?" (no LLM call).
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

## Spike results (2026-10-05)

Plan: `2026-10-04-conversation-partner-phase0-spikes.md`. Raw outputs in `data/spikes/` (gitignored).

| Spike | Result | Decision |
|---|---|---|
| S0 venv | 43 passed. Fresh venv pulled `av` 19, which breaks faster-whisper 1.2.1 (`open(metadata_errors=)` removed) — M2 `stc transcribe` was broken in any fresh install; tests use fakes so missed it. | Pinned `av<19` in `pyproject.toml`. |
| S4 audio | Keys r/s/t/q delivered via msvcrt in Windows PowerShell. Default devices = laptop mic array + laptop speakers (no headset); recording level healthy (peak 0.42, no clipping). | msvcrt key handling; headset strongly recommended for real use (partner audio bleeds into laptop mic). |
| S1 STT | 10 sentences with deliberate B1 errors. Kept: whisper small 2/10 (2.9 s), medium 3/10 (8.7 s), medium+learner prompt 3/10, large-v3 3/10 (~17 s), **Deepgram Nova-3 10/10 (0.9 s)**. Whisper silently fixes case/ending errors (einen→eine, Jahre→Jahren, meine→meinen) at every size. Positive control (5 correct sentences): Deepgram 5/5 (incl. a real self-correction "einen eine"), medium 2/5. Azure STT not tested (account creation failed). | STT = Deepgram Nova-3 (ADR 0005). Self-corrections are kept → report can show them as progress. |
| S2 TTS | Azure dropped (account issues). Learner ear test: 1st `de-DE-SeraphinaMultilingualNeural`, 2nd `de-DE-KatjaNeural` (edge-tts); slower (-25%) still natural. Piper Thorsten generated as offline option. ElevenLabs not needed. | TTS = edge-tts Seraphina, Piper fallback. |
| S3 LLM | Gateway `api.dlabkeys.com/v1` (key reseller; 37 models listed). Haiku 4.5: 0% valid JSON, chatty, praises → out. Sonnet 5: 100% valid, median 3.7 s, ~1460/150 tokens. DeepSeek V4 Pro: 100% valid, median 3.9 s (max 4.5 s), ~800/90 tokens, most natural. gpt-6-luna listed but 404 upstream; gpt-6-sol timed out. Quota: 722 req/day Sonnet, 1300 req/day DeepSeek vs ~60–120 needed. | Partner = DeepSeek V4 Pro, fallback Sonnet 5; report = Sonnet 5. |

Findings carried into Phase 1:
- **Recast prompt bug:** models repeat the learner's sentence in first person ("Gestern habe *ich* …"), which sounds like the partner's own statement. Recast must be a second-person echo ("Ah, du *hast* gestern …").
- **Reseller risk:** listed models can be unavailable; partner must fall back automatically, and conversation content passes through a third party. Switching to official APIs is a config change.
- **Cost:** STT on Deepgram's $200 signup credit (per-minute price not captured — page renders dynamically); TTS free; LLM within prepaid gateway quota. €5/month target not exceeded by any measured component.
- **Privacy:** learner audio now leaves the laptop (Deepgram). Check Deepgram's data-retention / model-improvement opt-out in their docs before daily use.

**Phase 1 first conversation (2026-10-05 → 2026-10-07).** First real run 2026-10-05 (27 turns) found the SPACE-buffer bug and the silent LLM fallback; both fixed. Verification runs 2026-10-06/07 (conversations 5–9) on DeepSeek V4 Pro via dlabkeys: every turn answered by the primary model (no fallback), ~3 s per LLM turn, recasts are second-person, audio + turns stored per turn, help ladder reaches step 3 on silence, `r`/`t` counted. Bugs found and fixed: keys were ignored while the partner spoke (playback blocked on `sd.wait()`, keys flushed) → keyboard interrupt added, SPACE/q/r/s cut playback, `t` reads along, stop via `stream.abort()` (36b436d); freeze median took the upper element for even counts (1e875a9). Interrupt confirmed live with key-level instrumentation (SPACE → recording at 1.1 s, q → end at 2.2 s). Prompt issues → BACKLOG: partner attributes phrase seeds to the learner (`bank-phrase-vs-question`), recast + reply say the same thing twice (`recast-reply-duplicate`). GLM-5.3 on the gateway returned empty content on a 20-token probe — not a fallback candidate as-is.

## Testing

- Unit: help ladder state machine, question-bank parser + picker (no-repeat, freeze boost), `PartnerTurn` parsing (valid / malformed JSON), DB migration + turn persistence, metrics, report assembly — all with fakes for STT/LLM/TTS/audio.
- Integration: `session.py` loop driven by a scripted fake learner (pre-recorded audio + timed key events) and fake partner/speaker — verifies freeze times, ladder firing, persistence order.
- Manual: spikes S1–S4; one real 10-minute conversation before calling v1 done.
- `bash scripts/lint-arch.sh` before each commit (project rule).

## Configuration (`.env`, never committed)

`DEEPGRAM_API_KEY`, `GATEWAY_BASE_URL` (incl. `/v1`), `GATEWAY_API_KEY`, `STC_PARTNER_MODEL=deepseek-v4-pro`, `STC_FALLBACK_MODEL=claude-sonnet-5`, `STC_REPORT_MODEL=claude-sonnet-5`, `STC_TTS_VOICE=de-DE-SeraphinaMultilingualNeural`, `STC_QUESTION_BANKS`, `STC_LADDER_SECONDS=4,8,12`. (`ANTHROPIC_API_KEY` stays for the existing enrich stage.) `.env.example` gains these names with empty values.

## Open after v1

- Listening "Stage 1" (text auto-shown after audio) if A proves too hard early on.
- First-word VAD (RealtimeSTT) to replace key-press freeze proxy.
- Local model swaps per slot; phone version; Supabase sync.
- Exam mode (no help ladder) for interview rehearsal.
