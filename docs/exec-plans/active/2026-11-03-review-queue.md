# review-queue — task brief

**Status:** active
**Last verified:** 2026-11-03

BACKLOG S2 `review-queue`. Written for an agent working on the VPS in opencode;
reviewed and merged on the laptop. Spec: Milestone 4 and "Review Workflow" in
`docs/superpowers/specs/2026-05-31-local-first-german-learning-core-design.md`
(read it, do not edit it).

## Goal

```text
stc review list   [--status pending|deferred|approved|rejected|all] [--data-root PATH]
stc review show    <id> [--data-root PATH]
stc review approve <id> [--note TEXT] [--data-root PATH]
stc review reject  <id> [--note TEXT] [--data-root PATH]
stc review defer   <id> [--note TEXT] [--data-root PATH]
```

The invariant from the spec: **analysis suggestion != approved practice.** A
practice item exists only after `approve`.

## Decided — do not change these

1. **Statuses.** Add `CandidateStatus` (StrEnum) to `domain.py`: `pending`,
   `approved`, `rejected`, `deferred`. The column `learning_candidates.status`
   already exists with default `'pending'` and no CHECK; no schema migration.
2. **Transitions.** From `pending` or `deferred` → `approved`, `rejected` or
   `deferred`. The same action on a candidate already in that state is a no-op:
   exit 0, print `candidate <id> already <status>`, write nothing.
   `approved` and `rejected` are final: any other action on them exits 1 with
   `candidate <id> is <status>; review decisions are final`. Unknown id exits 1.
3. **Approve** creates exactly one `practice_items` row: `practice_type` =
   candidate_type, `front` = original_text, `back` = suggested_text if non-empty
   else original_text, `notes` = explanation, `export_status` left at default.
4. **History.** Every state change writes one `review_events` row: `action` in
   `approve` / `reject` / `defer`, `note` from `--note` (else NULL),
   `practice_item_id` set on approve. Set `updated_at = datetime('now')` on the
   candidate. Status change, practice item and event go in **one transaction**.
5. **list** default shows `pending` and `deferred`; `--status` picks one status
   or `all`. Columns: id, status, type, producer, original, suggestion (each text
   cut to 60 characters). Order: pending before deferred, then candidate_type,
   then id. No rows → `No candidates.`, exit 0.
6. **show** prints every candidate field, then the source: if `turn_id` is set →
   conversation id, turn_index and the turn's `text`; else if
   `transcript_segment_id` is set → the segment's `text` with start/end seconds;
   else `source: none`. Then the review history (oldest first).
7. **Report reruns must not destroy decisions.** `replace_conversation_candidates`
   (`db.py`, near the end) deletes *every* candidate of the conversation before
   inserting the new set, and `practice_items` cascade on that delete — so today a
   second `stc report <id>` after an approval would silently delete the practice
   item. Change it: delete only `status = 'pending'` rows; keep approved,
   rejected and deferred ones; skip inserting a new candidate when a kept one has
   the same `turn_id`, `candidate_type`, `original_text` and `suggested_text`.
   Keep its docstring's promise (reruns never duplicate) true.
8. **Layering.** SQL lives in `db.py` functions. The CLI is a sub-app in `cli.py`:
   `review_app = typer.Typer(help=...)`, `app.add_typer(review_app, name="review")`,
   each command takes `--data-root` exactly like `report_command`, opens with
   `connect(paths.db_path)` + `init_db(conn)`, and contains no SQL.

## Not decided — your call, record it in the handoff

Function names and signatures in `db.py`, output formatting beyond the columns
above, how errors travel from `db.py` to the CLI (exception type or return value).

## Tests

New file `tests/test_review.py`. Seed data with `insert_conversation`,
`insert_turn` and `replace_conversation_candidates` (see
`tests/conversation/test_report_db.py` for the pattern), on a `tmp_path` DB.

- db level: each allowed transition; each no-op (no event written); each final-state
  error; approve creates exactly one practice item and one event; a failure inside
  approve leaves no partial rows (e.g. force an error after the status update).
- rerun (decision 7): approve one candidate, defer another, leave a third pending,
  call `replace_conversation_candidates` again with the same three → practice item
  still there, approved and deferred rows unchanged, no duplicates, the pending
  one replaced. **Run this test against the current code first and confirm it
  fails**; report that in the handoff.
- CLI with `typer.testing.CliRunner` and `--data-root tmp_path`: `list` (default
  and `--status all`), `show`, `approve` twice (second is a no-op, exit 0),
  `reject` after `approve` (exit 1).

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

Both must be clean at every commit. The baseline before you start is whatever
`pytest -q` printed when the user set up the VPS — failures that existed then
are not yours; list them in the handoff, do not fix them.

## Rules

- Commits: (1) enum + db functions + their tests, (2) rerun fix + its test,
  (3) CLI + its tests. Message prefix `review-queue:`.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, anything under
  `docs/superpowers/`, or `data/`. No `/save-session`. No push.
- No real data: `data/` is not on the VPS and must stay out of git.
- End: write `docs/handoff-2026-11-03-review-queue.md` — files changed, the last 5
  lines of the final pytest run, ruff result, all commit SHAs, the rerun test's
  fail-before result, every "your call" decision with one line of why, anything
  not done. Commit it.
