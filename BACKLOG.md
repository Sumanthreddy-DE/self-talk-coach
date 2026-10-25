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

_(none)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- first-language-analysis - Generate pending correction and upgrade candidates from stored transcript segments. Plan: `docs/superpowers/plans/2026-06-02-first-language-analysis.md` (paused 2026-09-28, not started).
- review-queue - Add commands to list, show, approve, reject, and defer learning candidates.
- question-banks-missing - Conversation partner needs question banks the Myself banks lack: McDonald's shift/colleague scenario, telc B1 Sprechen cards (Kontakt aufnehmen, Präsentation, gemeinsam planen), larger free-talk topic bank. Draft → user approval before committing. Existing banks read in place via `.env` path (PII, never copied into repo): `Myself/German-Learning/question-bank.md`, `Myself/Interview-Prep/interview-questionnaire-de.md`. First task after conversation-partner setup. 2026-10-07/08: McDonald's (customers, manager, colleagues, workload, friendly customers) and cold-call role-plays done in `Myself/German-Learning/scenario-bank.md`; still missing: telc B1 Sprechen cards, free-talk bank.
- llm-provider-reliability - dlabkeys gateway grants credits daily; on 2026-10-05 the day's credits ran out (429 "hobbyist plan has expired … Free tier") after spikes + tests. gpt-6-luna/sol listed but unavailable. Free-tier `space-bunny` returned empty content in 2/3 turns. Decide: renewed dlabkeys vs official DeepSeek API (config-only switch). Consider a startup preflight call so `stc talk` fails fast instead of falling back every turn. 2026-10-06: credits back, DeepSeek V4 Pro + Sonnet 5 answer in ~2.5 s; `glm-5-3` returned empty content on a 20-token probe.
- web-ui - Browser frontend for the conversation partner after terminal v1 (also the cheapest path to phone use over LAN). Candidate: Chainlit (Apache-2.0, 12.5k★, community-maintained since 2025-05). Its cookbook `openai-whisper` example (mic → whisper → LLM → ElevenLabs) matches our loop, but the cookbook has no license (ideas only) and was last pushed 2025-08. Needs: hidden partner text, help-ladder timers, freeze-time capture in the browser.
- plan-location - Plans/spec live in `docs/superpowers/` (blocked for new files by harness hook). Decide: move M1/M2 plans to `docs/exec-plans/completed/`, M3 plan + spec to `docs/exec-plans/`. Separate decision from the 2026-09-28 status triage.
- mein-tag-live-check - First live run 2026-10-25 (conversation 15, via `scripts/mein-tag.bat`, 1 answer): no correction spoken, follow-up 11 words, help ladder reached step 3, report without Freeze section — pass. Still untested: English words taken up in German / English → Deutsch section (no English used). Miner noise: imperative "erzähl" listed as new word (out-of-context lemma stays "erzähl"). *(found 2026-10-24, self-talk-coach session)*
- demo-clip - LinkedIn/README demo not cut yet. Source: Snipping Tool recording of conversation 13 (Interview: Core, 2026-10-24). Clipchamp: keep turns 0–4 + the printed report, cut salary (45.000 €), Reutlingen and "Geld" parts; 1080p mp4, <10 MB, 60–90 s. Upload by dragging into a GitHub issue comment, put the user-attachments link at the top of README. Then write the LinkedIn post. *(found 2026-10-24, self-talk-coach session)*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- interview-questionnaire-format - `Myself/Interview-Prep/interview-questionnaire-de.md` has one `##` heading per question (with model answers), so `parse_bank` reads it as 11 junk seeds. Needs its own parser before the session report can show "what you could have said". *(found 2026-10-08, self-talk-coach session)*
- anki-export - Approved practice items → Anki `.apkg` (genanki), planned in the core design (`stc export anki`). Design to reuse: weekend-MVP blueprint S5 — structured enrich prompt (DE definition, EN translation, gender/separable-prefix, example from the learner's own sentence), prompt caching with the 1024-token prefix minimum (assert `cache_creation_input_tokens > 0` then `cache_read_input_tokens > 0`), `--max-cards` cost cap.
- stale-state-doing - `STATE.md` Doing/Resume still say `feat/conversation-loop` awaits merge, but `main` already contains it (57e8348). Next session here: refresh Doing + Resume here from git log. *(found 2026-10-08, claude-lab session)*
- mein-tag-switch-keys - In Mein Tag, w/f reset the partner's memory and reopen; disable or hide them in that mode if it bites.


---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-06-01, 2026-10-07, 2026-10-08, 2026-10-10, 2026-10-24)

- report-llm-timeout - Report LLM timeout 90 -> 180 s; conversation 12 (13 turns) took ~32 s (5f32ec1)
- interviewer-mode - Sections named "Interview…": partner is a Personalerin using "Sie" (replies, recasts, starters, check, nudges, pardon), questions in bank order, answers up to 120 s with a visible cut-off line (5f32ec1, 750b8f7)
- report-case-noise - Report no longer lists capitalisation/punctuation as errors: prompt rule + code guard in verify_findings (750b8f7)
- vocab-miner-noise-filters - Partly: inflected forms of baseline words count as known ("Verstehe" -> verstehen). freq/NER filters and ignore.txt still not built; reopen if junk shows (750b8f7)
- check-uses-up-seed - Comprehension checks consumed a bank question; interview skipped Schwächen/fünf Jahre and wrapped to the first question (2eb9b18)
- tts-failure-crashes-session - Voice failure prints the reason and the partner text, turn stored without audio, conversation goes on; any crash marks the conversation aborted; conversation 11 set to aborted (7db247a)
- partner-turn-length - After a recast only the new question is spoken (code guard), prompt asks for recasts <= 12 words and no comment; live probe: one-question replies, recasts 8-16 words (see commit)
- talk-launcher - `scripts/talk.bat`: double-click opens the repo root and runs `stc talk` (start menu), args pass through, window stays open at the end; tested from another cwd
- word-list - New words get English meanings (same report LLM call) and one-sentence examples, and collect in `data/neue-woerter.md` with checkboxes that survive reruns (1c044b4)
- vocab-miner - `mine.py`: spaCy lemmas (NOUN/VERB/ADJ/ADV, no stopwords) outside the B1 baseline and not used by the learner; partner `out_of_baseline_ratio` per turn. Missing `de_core_news_lg` → report section skipped with a visible reason (0abd635)
- report-rescue-phrases - Session report lists rescue phrases used (report LLM, quote-verified) and missed chances (ladder ≥ starter, no rescue phrase); never counted as listening failures (da997c2)
- mein-tag-mode - `stc talk --mein-tag` / start menu `m`: follow-up-only partner, ladder 15/25/35 s, 180 s turns, no recast, no comprehension check, English taken up in German; report without Freeze section (2ab5e89)
- mixed-language-stt - Tested 2026-10-08 with `scripts/spikes/s6_multi_language.py` (43 files): `multi` kept 3/10 S1 errors (de 10/10) and turned 8/28 real learner turns into English/Hindi/Spanish nonsense; `de` already writes English words as English (9/10 on synthetic mixed speech). Decision: keep `language=de`. Optional: learner records `s6 record` for an own-accent English check.
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
