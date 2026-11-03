# review-missing-db-silent — task brief

**Status:** active
**Last verified:** 2026-11-03

BACKLOG S3 `review-missing-db-silent`. Written for an agent working on the VPS in
opencode; reviewed and merged on the laptop. Branch: `fix/review-missing-db`.

## Problem

`stc review list --data-root <typo>` prints `No candidates.` and exits 0, because
every review command opens the DB with `connect(paths.db_path)`
(`src/self_talk_coach/cli.py`, `review_list_command` at line ~58, `review_show_command`
~81, `_review_decision` ~104), and `connect()` (`src/self_talk_coach/db.py:24`) runs
`path.parent.mkdir(parents=True, exist_ok=True)` before `sqlite3.connect`. A wrong
path silently creates a new empty workspace and looks like an empty queue.

## Decided — do not change these

1. **Scope: the five `stc review` commands only** (`list`, `show`, `approve`,
   `reject`, `defer`). Do **not** change `connect()` or `init_db()`: `init`,
   `import`, `report` and the rest rely on `connect()` creating the folders.
2. Before opening the DB, each review command checks `paths.db_path.exists()`. If it
   does not exist: print to **stderr**
   `no database at <db_path> -- check --data-root, or run: stc init --data-root <data_root>`
   (real paths filled in), exit code **1**, and create **nothing** — no folder, no file.
3. Put the check in one small helper in `cli.py` used by all three code paths
   (`review_list_command`, `review_show_command`, `_review_decision`). No SQL in it.
4. Existing behaviour with an existing DB is unchanged, including `No candidates.`
   with exit 0 on a real but empty queue.

## Not decided — your call, record it in the handoff

The helper's name and whether it returns the open connection or only validates.

## Tests

Add to `tests/test_review.py`, using the existing `CliRunner` helper there
(line ~167 passes `--data-root str(tmp_path)`).

- For each of `list`, `show 1`, `approve 1`, `reject 1`, `defer 1` with
  `--data-root tmp_path / "typo"`: exit code 1, the message is in the output, and
  `(tmp_path / "typo").exists()` is `False` afterwards.
- Positive control: a DB made with `stc init --data-root tmp_path`, then
  `review list` → exit 0 and `No candidates.`.
- **Run the new missing-DB tests against the current code first and confirm they
  fail**; report that in the handoff.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

Laptop baseline on 2026-11-03 (`main` at `afc0876`): **186 passed**; ruff reports
**2 pre-existing I001** (import order) in `src/self_talk_coach/conversation/session.py:3`
and `tests/conversation/test_partner.py:226`. Those two are not yours — do not fix
them; ruff must show no *new* finding. Run both commands once before you start and
put the output in the handoff.

## Rules

- One commit (tests + fix), message prefix `review-missing-db:`; a second commit
  for the handoff.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, anything under
  `docs/superpowers/`, or `data/`. No new files outside `src/`, `tests/` and the
  handoff. No `/save-session`. No push.
- No real data: `data/` is not on the VPS and must stay out of git.
- End: write `docs/handoff-2026-11-03-review-missing-db.md` — files changed, the
  last 5 lines of the final pytest run, ruff result, both commit SHAs, the
  fail-before result, the "your call" decision with one line of why, anything not
  done. Commit it.
