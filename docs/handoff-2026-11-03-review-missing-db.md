# review-missing-db — VPS handoff

Branch: `fix/review-missing-db`

## Changes

- `src/self_talk_coach/cli.py`: added `_require_review_database(paths: AppPaths) -> None`, called before `connect()` in list, show and the shared decision path. All five review commands now emit the specified missing-database diagnostic to stderr, exit 1 and create nothing when the database is absent.
- `tests/test_review.py`: added five parameterized missing-database cases checking exit code, diagnostic, stderr and absence of the typo workspace. Updated the existing empty-list positive control to initialize its database through `stc init` first.
- `docs/handoff-2026-11-03-review-missing-db.md`: this handoff.

## Baseline (before edits)

Ran the brief's commands first, at `d71ff07`:

```text
$ .venv/bin/python -m pytest -q
........................................................................ [ 38%]
........................................................................ [ 77%]
..........................................                               [100%]
186 passed in 23.45s
```

`.venv/bin/ruff check src tests` exited 1 with exactly two pre-existing findings:

```text
I001 src/self_talk_coach/conversation/session.py:3:1
I001 tests/conversation/test_partner.py:226:5
Found 2 errors.
[*] 2 fixable with `--fix`.
```

## Fail before / pass after

Before production changes, ran:

```bash
.venv/bin/python -m pytest -q tests/test_review.py -k 'missing_database or empty_list'
```

Result: **5 failed, 1 passed, 25 deselected in 1.62s**. List incorrectly exited 0; show/approve/reject/defer emitted `candidate 1 not found` instead of the missing-database diagnostic. The initialized empty-list positive control passed.

After the fix, `.venv/bin/python -m pytest -q tests/test_review.py` passed: **31 passed in 6.24s**.

## Final verification

Final pytest output (only four lines were emitted, so these are all available lines rather than five):

```text
........................................................................ [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
191 passed in 15.55s
```

- `.venv/bin/ruff check src tests`: exit 1, exactly the same two baseline I001 findings above; no new findings.
- `bash scripts/lint-arch.sh`: `lint-arch: PASS — all checks clean`.
- `git diff --check`: passed.
- Self-reviewed the complete code/test diff against the brief; no additional findings. No independent reviewer was run.

## Decision and scope rulings

- Chose the validation-only helper `_require_review_database` over returning a connection: this keeps existing connection handling intact and makes the guard's limited responsibility explicit.
- Used the requested branch in the existing clean checkout. Kept progress in session todos and this handoff, without extra workspace/ledger files, to honor the brief's file restrictions.
- The handoff cannot contain its own literal commit SHA without changing that SHA. Its commit is identified below by its unique subject and a command resolving the full SHA; both literal SHAs are reported in the final session response. Cost: the handoff commit requires one Git lookup when reading this document alone.

## Commits

1. Tests + fix: `1eada46a319b838943e99512639fdd861e40f65e` — `review-missing-db: reject missing databases before review commands`.
2. Handoff: the commit introducing this file — `review-missing-db: document verification and handoff`. Resolve its full SHA with:

```bash
git log -1 --format=%H -- docs/handoff-2026-11-03-review-missing-db.md
```

## Anything not done

No implementation work remains. The two known Ruff findings remain as required. No push was performed.
