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
- web-ui - Browser frontend for the conversation partner after terminal v1 (also the cheapest path to phone use over LAN). Candidate: Chainlit (Apache-2.0, 12.5k★, community-maintained since 2025-05). Its cookbook `openai-whisper` example (mic → whisper → LLM → ElevenLabs) matches our loop, but the cookbook has no license (ideas only) and was last pushed 2025-08. Needs: hidden partner text, help-ladder timers, freeze-time capture in the browser.
- plan-location - Plans/spec live in `docs/superpowers/` (blocked for new files by harness hook). Decide: move M1/M2 plans to `docs/exec-plans/completed/`, M3 plan + spec to `docs/exec-plans/`. Separate decision from the 2026-09-28 status triage.

---

## Open — S3 (tech debt, deprecations, low-impact polish)

- uncommitted-backfill-headers - `docs/exec-plans/active/2026-05-28-weekend-mvp.md` and `docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md` carry uncommitted 2026-09-07 backfill headers (Status active / done). Verify against disk (weekend-mvp is likely paused now), then commit. No code-block damage in these two — checked 2026-09-28.
- venv-missing - `.venv` deleted in the 2026-08-27 move; recreate and re-run pytest (43 tests, last green 2026-06-02) before any new work.

---

## Doing

_(items currently being worked — move from Open when started, back to Open if paused.)_

---

## Done this session (2026-06-01)

- transcription-storage - Planned and implemented ffmpeg/faster-whisper transcription into SQLite transcripts and transcript_segments tables.

---

## Archived (older sweeps, compressed)

_(empty — populates over time as one-line entries per sweep.)_
