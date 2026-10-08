# self-talk-coach Backlog

Living list of open issues, deferred work, and known caveats. Updated each session.

**Severity rubric**
- **S1** — blocker / data loss / broken demo. Fix before next ship.
- **S2** — UX gap, missing polish, deferred decision.
- **S3** — tech debt, deprecations, low-impact polish, dead code.

**Conventions**
- New issue → append to correct severity section.
- Mention by short slug in commit body (e.g. "Closes: my-issue-slug").
- On close → move to **Done this session** with commit SHA.
- End of session → user sweeps **Done** → **Archived** (one-line compress).
- Last swept: **2026-05-28** (initialised).

---

## Open — S1 (blocker / broken demo)

_(none yet)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- first-language-analysis - Generate pending correction and upgrade candidates from stored transcript segments. Plan: `docs/superpowers/plans/2026-06-02-first-language-analysis.md` (paused 2026-09-28, not started).
- review-queue - Add commands to list, show, approve, reject, and defer learning candidates.
- question-banks-missing - Conversation partner needs question banks the Myself banks lack: McDonald's shift/colleague scenario, telc B1 Sprechen cards (Kontakt aufnehmen, Präsentation, gemeinsam planen), larger free-talk topic bank. Draft → user approval before committing. Existing banks read in place via `.env` path (PII, never copied into repo): `Myself/German-Learning/question-bank.md`, `Myself/Interview-Prep/interview-questionnaire-de.md`. First task after conversation-partner setup.
- partner-turn-length - Since phrase seeds became role-plays (2026-10-07), partner turns often run 3–4 sentences (scene-setting + answer + question) despite the 1–2 sentence rule; long turns are hard by ear. Also soft recast paraphrases slip past the echo guard ("Hm, du weißt also nicht genau, warum …?", word overlap < 0.6). Watch in daily use; options: max-sentence trim in code, or tighter prompt.
- report-rescue-phrases - Session report (Phase 2) must classify learner turns like "Ich habe das nicht verstanden, kannst du das nochmal sagen?" as rescue phrases used (freeze strategy), not as listening failures. Seen 2026-10-05: learner used one to buy time.
- llm-provider-reliability - dlabkeys gateway grants credits daily; on 2026-10-05 the day's credits ran out (429 "hobbyist plan has expired … Free tier") after spikes + tests. gpt-6-luna/sol listed but unavailable. Free-tier `space-bunny` returned empty content in 2/3 turns. Decide: renewed dlabkeys vs official DeepSeek API (config-only switch). Consider a startup preflight call so `stc talk` fails fast instead of falling back every turn. 2026-10-06: credits back, DeepSeek V4 Pro + Sonnet 5 answer in ~2.5 s; `glm-5-3` returned empty content on a 20-token probe.
- web-ui - Browser frontend for the conversation partner after terminal v1 (also the cheapest path to phone use over LAN). Candidate: Chainlit (Apache-2.0, 12.5k★, community-maintained since 2025-05). Its cookbook `openai-whisper` example (mic → whisper → LLM → ElevenLabs) matches our loop, but the cookbook has no license (ideas only) and was last pushed 2025-08. Needs: hidden partner text, help-ladder timers, freeze-time capture in the browser.
- vocab-miner - Session report (Phase 2) promises "new useful words (existing miner against the baseline)", but no miner exists: `src/self_talk_coach/mine.py` is a stub. Build it for the report. Design to reuse: weekend-MVP blueprint S4 (`docs/exec-plans/active/2026-05-28-weekend-mvp.md`, abandoned): spaCy POS filter NOUN/VERB/ADJ/ADV, drop stopwords/PER/LOC/ORG, lowercase compare, `freq >= 2` against STT noise, keep best example sentence + timestamp, optional `resources/ignore.txt` filler list.
- plan-location - Plans/spec live in `docs/superpowers/` (blocked for new files by harness hook). Decide: move M1/M2 plans to `docs/exec-plans/completed/`, M3 plan + spec to `docs/exec-plans/`. Separate decision from the 2026-09-28 status triage.

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- anki-export - Approved practice items → Anki `.apkg` (genanki), planned in the core design (`stc export anki`). Design to reuse: weekend-MVP blueprint S5 — structured enrich prompt (DE definition, EN translation, gender/separable-prefix, example from the learner's own sentence), prompt caching with the 1024-token prefix minimum (assert `cache_creation_input_tokens > 0` then `cache_read_input_tokens > 0`), `--max-cards` cost cap.
- stale-state-doing - `STATE.md` Doing/Resume still say `feat/conversation-loop` awaits merge, but `main` already contains it (57e8348). Next session here: refresh Doing + Resume here from git log. *(found 2026-10-08, claude-lab session)*


---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-06-01, 2026-10-07)

- readme-stale - README rewritten for `stc talk` + self-talk library, MIT LICENSE added; repo made public 2026-10-07 (5589d14)
- bank-phrase-vs-question - Phrase sections set in config (`STC_PHRASE_SECTIONS`, default Daily Life In Germany; Office German), seeds sent as role-play impulses. s5 eval 3 runs: partner never says the phrase itself (was 2/3 office openings), no invented learner claims. Bank files untouched.
- uncommitted-backfill-headers - Weekend-MVP blueprint → abandoned (designs carried to `vocab-miner`, `anki-export`); core-design spec → done. Committed 2026-10-07.
- recast-reply-duplicate - Prompt rule + code guard `_drop_recast_echo` (reply sentence ≥ 60 % recast words, W-questions exempt); s5 eval: 0 spoken echoes (was 6/6).
- partner-repeat-request - Prompt rule: "Wie bitte?" → last question again, simpler, seed ignored; s5 eval 3/3.
- talk-keys-during-playback - SPACE/q/r/s interrupt partner speech, `t` reads along; verified live 2026-10-07 (36b436d).
- talk-median-freeze - Freeze summary used the upper element for even counts (1e875a9).
- venv-missing - `.venv` recreated during conversation-partner work; 90 tests green 2026-10-07.

- transcription-storage - Planned and implemented ffmpeg/faster-whisper transcription into SQLite transcripts and transcript_segments tables.

---

## Archived (older sweeps, compressed)

_(empty — populates over time as one-line entries per sweep.)_
