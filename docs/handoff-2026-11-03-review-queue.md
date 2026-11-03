# Review queue — VPS handoff

Date: 2026-11-03  
Branch: `feat/review-queue`  
Exact model ID: `dlab/gpt-6-1-sol`

## Result

Implemented `stc review list`, `show`, `approve`, `reject`, and `defer` with
`--data-root`, status filtering, notes, source context and review history.
Approval alone creates practice material. Decisions, practice creation and
history writes are atomic; repeated actions write no rows. Final decisions
cannot be changed. Report reruns preserve decisions and practice items.

## Files changed

- `src/self_talk_coach/domain.py`: `CandidateStatus` StrEnum; no migration.
- `src/self_talk_coach/db.py`: review queries and transitions; safe report replacement.
- `src/self_talk_coach/cli.py`: review Typer sub-app, output and error handling.
- `tests/test_review.py`: 26 cases covering transitions, no-ops, final-state
  errors, missing IDs, practice mapping, rollback, report reruns and CLI behavior.
- `docs/handoff-2026-11-03-review-queue.md`: this handoff.

## Verification

The supplied baseline summary was an unfilled placeholder. Actual pre-change
run: `160 passed in 9.97s`; no pre-existing pytest failures.

Final `.venv/bin/python -m pytest -q` output has only four lines (all included):

```text
........................................................................ [ 38%]
........................................................................ [ 77%]
..........................................                               [100%]
186 passed in 19.33s
```

Full `.venv/bin/ruff check src tests`: **not clean**, exit 1, exactly the same
two pre-existing `I001` errors seen before implementation:

- `src/self_talk_coach/conversation/session.py:3` (partner import formatting).
- `tests/conversation/test_partner.py:226` (comprehension constants import formatting).

Ruff on all four changed Python files: `All checks passed!`.
`bash scripts/lint-arch.sh`: PASS. `git diff --check`: clean.

### Fail-before evidence

Before changing `replace_conversation_candidates`, ran:

```bash
.venv/bin/python -m pytest -q tests/test_review.py -k report_rerun
```

Result: `2 failed, 19 deselected in 0.75s`.

- `test_report_rerun_preserves_decisions_and_practice`: `assert len(items) == 1`
  failed with `assert 0 == 1`: rerun deleted the approved practice item.
- `test_report_rerun_failure_restores_previous_candidates`: previous candidates
  were absent after a forced insert failure (`[]` versus three original rows).

Both passed after the fix. Initial DB tests also failed before the new API
existed (19 failures); CLI tests failed before registration (5 failures,
`No such command 'review'`). Final suite above includes all of these tests.

## Implementation commits

1. `28bef5e430b2e18ddc2291650f8186f7be43d4c1` — enum, DB functions and tests.
2. `6b310835ef28b7e319eb73efb92a52e293f3440d` — rerun fix and regression tests.
3. `cca652dee96dc9ead1a7c118f06e313d846d354b` — CLI and integration tests.

This handoff is committed separately with prefix `review-queue:`. Its SHA is
the commit containing this file (self-referencing its own hash is not possible);
use `git log -1 --format=%H -- docs/handoff-2026-11-03-review-queue.md`.

## Your-call decisions and rulings

- DB API: `get_candidate`, `list_candidates`, `get_candidate_source`,
  `list_review_events`, `review_candidate`; SQLite rows retain existing storage
  conventions, and the mutation returns a bool to distinguish no-ops.
- Errors: `ReviewError(ValueError)` carries missing-ID/final-decision messages;
  CLI prints these on stderr and exits 1, keeping presentation outside DB code.
- List formatting: tab-separated six-column output, no ellipsis, truncated to
  60 characters; embedded tab/newline characters become spaces to keep one row
  per candidate. This avoids terminal-width-dependent wrapping and truncation.
- Show formatting: full `key: value` candidate fields, source fields and all
  event fields; event ordering is `created_at, id` for stable timestamp ties.
- Filter parsing: CLI `ReviewFilter` includes the four statuses plus `all`;
  omitted filter means pending/deferred and invalid input exits 2 via Typer.
- Transactions: savepoints, following `replace_transcript`, instead of a plain
  connection context inside DB functions; nested caller transactions remain
  intact while failed review operations roll back their own writes.
- Rerun replacement also uses a savepoint: a failed report insert must not lose
  existing candidates. This extends the requested fix to its failure path;
  transaction ownership remains with an outer caller if one exists.
- Rerun deduplication compares the four specified identity fields using SQL
  `IS` for nullable suggestions. It also suppresses duplicates within a new
  batch, fulfilling the rerun function's no-duplicates promise.
- Existing global Ruff errors were preserved instead of editing unrelated
  files. This is an explicit exception to the brief's clean-at-every-commit
  rule; the cost is that full-tree Ruff remains red until those imports are fixed.
- Review was an inline whole-diff self-review; no independent reviewer was
  dispatched because the loaded engineering rules restrict subagents to an
  explicit user request. Laptop review remains necessary before merging.

## Not done / remaining

- Full-tree Ruff is still blocked by the two baseline errors above.
- No real-data/live report run on the VPS; all added tests use temporary DBs.
- Laptop review and merge remain with the user. No push performed.
- Protected files (`BACKLOG.md`, `STATE.md`, memory, `docs/superpowers/`, `data/`)
  were not modified. No session-save operation was run.
