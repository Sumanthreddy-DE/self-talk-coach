# self-talk-coach — Session-End Checklist

Read this when wrapping up any working session. Keeps `BACKLOG.md`, the memory dir, and git history aligned. Run top-to-bottom; skip steps that genuinely don't apply.

---

## 1. BACKLOG sweep

In `BACKLOG.md`:

- [ ] For every item closed this session, check it has a commit SHA (or SHA range) recorded.
- [ ] Move closed items from **`## Done this session`** to **`## Archived`** as one-line compressed entries.
  - Compression pattern: `**YYYY-MM-DD · short topic** (N items) — see commits SHA1..SHAN. one-line scope summary.`
- [ ] Make sure `## Done this session` ends the session empty.
- [ ] Update the **`Last swept:`** date line at the top to today.
- [ ] If any new issues were discovered (and not fixed), add them to the right S1/S2/S3 section with an `*Opened YYYY-MM-DD.*` tag.

## 2. Memory: live one-line state

In `~/.claude/projects/<cwd-slug>/memory/` (the auto-memory dir): find the file whose role is "current state" or "roadmap pointer" and update its **one-line state** paragraph.

That's the only memory file that needs touching most sessions. Skip the others unless material project state changed (new env, new top-level module, test count jumped).

## 3. Memory: bigger refresh (rare — only when state actually shifted)

Touch the main `project_<name>.md` memory file ONLY if one of these is true:

- A new top-level module / package landed.
- Test count moved by more than a handful (note the new total).
- Env changed (new conda env, new language version, new core dep).
- A phase / milestone boundary just crossed.

If none apply: do not touch it. Stale claims are worse than missing ones.

## 4. Plan progress

In `docs/exec-plans/<active-plan>.md`:

- [ ] Tick the right `[ ]` → `[x]` for any milestone that shipped.
- [ ] Update the **`Status:`** line at the top if the position moved.

## 5. Commit + push

- [ ] One end-of-session commit: `chore: end-of-session sweep — <topic>` (or similar).
- [ ] `git push origin <branch>`. Hook may block; if so, resolve and push again. **Do not skip hooks.**

## 6. Save session

- [ ] Run `/save-session` (or invoke the `save-session` skill).
  Writes to `~/.claude/projects/<cwd-slug>/sessions/YYYY-MM-DD-<topic>-session.tmp`.
  NOT to `~/.claude/session-data/` — that path is from an older skill version; ignore.

## 7. Optional: open-questions for next session

If anything came up that needs a decision from you before next session, append it as a one-line bullet to the roadmap pointer memory file under a **`## Pending for next session`** heading (create if missing).

---

## What this file is NOT

- Not a hook. Nothing enforces it. Manual discipline.
- Not loaded by any tool. You (or me, when prompted "wrap up the session") read it.
- Not exhaustive. Trust judgement on whether a step adds value this session.

## How to invoke

End of session, say: **"wrap up the session"** or **"end-of-session sweep, follow `SESSION-END.md`"**. The assistant walks the checklist with you.
