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
- Last swept: **2026-11-18** (cockpit tags, prompt splits, `mein-tag-switch-keys` and `recast-length-watch` moved to Parked).

---

## Open — S1 (blocker / broken demo)

_(none)_

---

## Open — S2 (UX gap, polish, deferred decisions)

- **first-language-analysis** [later · you] — Decide whether stored self-talk transcript segments use the regex rule catalog or ADR 0006's LLM + quote check before rewriting stale plan `2026-06-02-first-language-analysis.md` and building `stc analyze`. *(found 2026-06-02; rechecked 2026-11-12)*
  Prompt:
    Generate pending correction and upgrade candidates from stored transcript segments (the self-talk recording library). Partly in place, built for conversations, not for transcripts: `CandidateType`/`CandidateStatus` (`domain.py`, 300b41d), `learning_candidates.transcript_segment_id` column, review queue shows a segment as the source (`get_candidate_source`, 28bef5e). Still missing: `analyze.py`, `stc analyze`, `AnalysisOutcome`, the segment query + idempotent insert (`list_completed_transcript_segments_for_analysis`, `insert_learning_candidate`, unique identity index), anything that writes `transcript_segment_id` or sets media status `analyzed`, tests. Plan `docs/superpowers/plans/2026-06-02-first-language-analysis.md` is stale before execution: its Task 1 redefines `CandidateType` with 8 values and `vocab_candidate` where code has 3 and `vocabulary`; decide first whether segments get the plan's regex rule catalog or the conversation report's LLM + quote check (ADR 0006).
- **question-banks-missing** [later · claude] — McDonald's and cold-call scenarios are done in `Myself/German-Learning/scenario-bank.md`; still missing: telc B1 Sprechen cards (Kontakt aufnehmen, Präsentation, gemeinsam planen) and a larger free-talk topic bank (draft → user approval). *(found 2026-10-05)*
- **llm-provider-reliability** [later · you] — Decide between renewed dlabkeys and official DeepSeek API for `stc talk` (`space-bunny` / `glm-5-3` returned empty replies; consider a startup preflight check so `stc talk` fails fast). *(found 2026-10-05)*
- **web-ui** [later · claude] — Browser frontend for the conversation partner after terminal v1 (candidate: Chainlit Apache-2.0; needs hidden partner text, help-ladder timers, freeze-time capture). *(found 2026-10-05)*
- **plan-location** [later · model] — Plans/spec live in `docs/superpowers/` (blocked for new files by harness hook). Move M1/M2 plans to `docs/exec-plans/completed/` and M3 plan + spec to `docs/exec-plans/` after confirming target paths. *(found 2026-09-28)*
- **mein-tag-live-check** [later · you] — First live run passed (2026-10-25, conversation 15); still untested: English words taken up in German / English → Deutsch section, plus imperative `"erzähl"` miner noise. *(found 2026-10-24, self-talk-coach session)*
- **anki-export-live-check** [later · you] — Run `.venv\Scripts\stc export anki` on the laptop DB, import `data/exports/anki/stc-<time>.apkg` into AnkiDroid on the phone, verify card count/formatting/umlauts, and decide the card-front question for `anki-export-enrich`. *(added 2026-11-12, self-talk-coach session)*
  Prompt:
    On the laptop, in the repo root: `git pull`, then `.venv\Scripts\stc export anki`; expect "Exported practice items: N" and a file `data/exports/anki/stc-<time>.apkg`. Copy it to the phone and import it in AnkiDroid (deck `self-talk-coach`). Check: card count = N, prompt/sentence/correction/explanation render, umlauts and quotes look right, vocabulary cards show only the explanation on the back. The run marks the items `exported`; if the import fails, rerun with `--all` to rebuild the package. Then decide the open card-front question in `anki-export-enrich`.
- **demo-clip** [later · you] — Cut the 60–90 s LinkedIn/README demo clip from conversation 13 (keep turns 0–4 + report; remove salary, Reutlingen, and "Geld" parts; <10 MB 1080p mp4), embed at top of `README.md`, then write the LinkedIn post. *(found 2026-10-24, self-talk-coach session)*
- **interview-tag** [later · you] — Decide question-bank location (`Myself/` recommended vs per career-ops application folder) for daily German interview practice, then run a 5-day manual trial (`harness/sessions/self-talk-coach/2026-10-29-interview-practice-idea-session.tmp`). *(found 2026-10-29, self-talk-coach session)*

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- **anki-export-enrich** [later · claude] — After `anki-export-live-check` passes and the card-front question is settled, implement LLM card enrichment in `enrich.py` + `--max-cards` cap on `stc export anki`. *(found 2026-11-12)*
  Prompt:
    Step 2 of Anki export: enrich cards before export (DE definition, EN translation, gender/separable-prefix, example from the learner's own sentence) in `enrich.py` (still a 4-line stub), plus a `--max-cards` cost cap on `stc export anki`. Design to reuse: weekend-MVP blueprint S5 structured enrich prompt. Its prompt-caching rule (1024-token prefix, `cache_creation_input_tokens`/`cache_read_input_tokens` asserts) is Anthropic-specific; the partner runs on dlabkeys/DeepSeek, so redo caching for whichever provider enrichment uses. Open question: card front shows the learner's wrong sentence ("Korrigiere:"); switch to a cloze of the correct sentence if reviewing the wrong form hurts.

---

## Parked

- **mein-tag-switch-keys** [parked · you] — In Mein Tag, `w`/`f` reset the partner's memory and reopen; disable or hide them in that mode only if accidental resets happen. *(found 2026-10-10)*
- **recast-length-watch** [parked · you] — Recasts of long learner answers are 14–16 words against the 12-word prompt rule (live probe 2026-10-24 after `6e25e3c`); watch in daily use, add a code cap only if it hurts listening. *(found 2026-10-24, self-talk-coach session)*


---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-06-01, 2026-10-07, 2026-10-08, 2026-10-10, 2026-10-24)

- anki-export (step 1) — done 2026-11-12 (merge `8beb9d0`; `7df1d42`): `stc export anki` writes not-yet-exported approved `practice_items` to `data/exports/anki/stc-<time>.apkg` (prompt per type, sentence, correction, explanation; HTML-escaped; fixed model/deck ids and per-item guid so re-imports update), sets `export_status = exported` after the file is written, `--all` re-exports. No enrichment. 214 passed. Enrichment + `--max-cards` split out as `anki-export-enrich`.
- stale-state-doing — closed 2026-11-12 (backlog truth sweep, `chore/backlog-truth-sweep`). Doing had already been refreshed in `ee57705` (2026-10-08; `feat/conversation-loop` merged as `fa2d931`); what was still stale was Resume here (Interview-Tag deadline ~2026-10-31 passed) and the Pipeline M3 line. Both refreshed from git log (last code merge `505ad00`).
- model-answer-near-miss — closed 2026-11-04 (merge `505ad00`, VPS opencode GPT-6.1 Sol). Normalised exact match, then unique ≥3-word subset match (no similarity ratio). Real DB, read-only: conversations 12/13/14 now match 6/9/2 (was 4/7/2). Still unmatched by design: "…Ihren beruflichen Hintergrund" vs questionnaire "…Werdegang" (synonym; align the scenario-bank wording if it matters).
- report-model-answers — done 2026-11-03 (merge `4bd622e`; `7d0fef7`, handoff `9df8c3b`): interview reports end with `## Musterantworten` (question, **Du:** answers joined ` / `, model answer as quote); bank load failure → visible `[Hinweis]` line, report still built; reports without matches unchanged. Laptop check (read-only, real DB + real questionnaire): conversations 12/13/14 match 4/7/2 questions and render correctly. 202 passed. Built on the VPS by opencode with GPT-6.1 Sol.
- interview-questionnaire-format — done 2026-11-03 (merge `ecb55b2`; `468b60b`, handoff `5ae9e11`): `parse_questionnaire` + per-file detection in `load_banks`, `Seed.model_answer`. Real file on the laptop: 61 question headings → 60 seeds (Stärken A/B merged), 7 sections all `Interview: …`, every seed has a model answer, no `>` notes, no `★` or ` — ` left in question text; scenario bank unchanged (54 seeds). The brief's "56 → 55" was my miscount (regex skipped `5a.`/`5b.` ids). `model_answer` not used yet → next: show it in the session report. Built on the VPS by opencode with GPT-6.1 Sol, synthetic sample only. 197 passed.
- review-missing-db-silent — done 2026-11-03 (merge `dfb086c`; `1eada46`, handoff `2414dfa`): the five `stc review` commands exit 1 with a `no database at <path>` hint and create nothing when the DB is missing; `connect()` unchanged. 191 passed, ruff only the 2 known I001. Built on the VPS by opencode with GPT-6.1 Sol, reviewed on the laptop (live probe: typo path exit 1 and not created; real data root lists as before).
- review-queue — done 2026-11-03 (merge `2596830`; `28bef5e`, `6b31083`, `cca652d`, handoff `891c10f`): `stc review list|show|approve|reject|defer`, atomic decisions via savepoints, approved/rejected final, repeats write nothing. Also fixed a data-loss bug: `stc report` reruns deleted approved practice items (cascade); now only pending rows are replaced. 186 passed on VPS and laptop; rerun tests confirmed failing on the old function. Built on the VPS by opencode `dlab/gpt-6-1-sol`, reviewed on the laptop.
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
