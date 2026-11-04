# Brief — model answers survive small wording drift

**Status:** done
**Last verified:** 2026-11-04
**Branch:** `fix/model-answer-match` (cut from `main` at this brief's commit)
**BACKLOG item:** S3 `model-answer-near-miss` (in **Doing**)

Written for an agent on the VPS in opencode; reviewed and merged on the laptop.
Repo: `~/projects/self-talk-coach`.

## Environment (VPS)

Your shell tool does not keep `export`s or activations between calls. Call the repo's
venv by its path in every command, from the repo root:

```
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check src tests
```

Install nothing. No network calls, no `.env` changes, no real database, no
`stc` CLI runs — tests only.

## Baseline (before any edit)

Run both commands above and record the summary lines. Laptop on 2026-11-04
(`main`): **202 passed**; ruff **2 errors**, both pre-existing I001 (import order) —
leave those two alone. Any test failure in the baseline: stop and report it.

## Problem

`_model_answers` in `src/self_talk_coach/conversation/report.py` (line ~105) puts a
prepared answer under a question only when the partner turn's `seed` is **exactly** a
key of `prepared` (the questionnaire: question text → model answer). The scenario bank
the partner asks from and the questionnaire word the same questions slightly
differently, so real sessions lose answers. Real examples (conversation 13 matched 7
of 10):

| asked (`seed`) | questionnaire key |
|---|---|
| `Sind Sie bereit umzuziehen?` | `Sind Sie bereit, umzuziehen?` |
| `Erzählen Sie mir bitte etwas über sich.` | `Erzählen Sie etwas über sich.` |

## Do

In `report.py`, add one small pure helper that resolves a seed to a prepared key,
and use it in `_model_answers` instead of `seed in prepared`:

1. **Normalise** a question: `casefold()`, replace every character that is not a
   letter, digit or whitespace with a space, split on whitespace. Keep umlauts and
   `ß` as letters (`str.isalnum()` is fine for this).
2. **Exact after normalising:** if exactly one prepared key has the same token
   *sequence* as the seed, that is the match.
3. **Otherwise, word subset:** a prepared key matches when its token *set* has at
   least 3 tokens and is a subset of the seed's token set. Use it only when
   **exactly one** prepared key qualifies; zero or several → no match (never guess).
4. No `difflib`, no similarity ratio, no new dependency. Reason: "Was sind Ihre
   Stärken?" and "Was sind Ihre Schwächen?" score about 0.85 with `difflib` and would
   show the wrong model answer; the subset rule cannot pair them because
   `stärken` ≠ `schwächen`.

Keep everything else as it is: grouping of follow-up answers by seed, asked order,
unanswered questions shown with `–`, the returned tuple `(heading, learner answers,
model answer)`. The heading stays the seed **as asked**; the model answer is
`prepared[<matched key>]`. A seed that matches nothing is left out, as today.

## Tests (in `tests/conversation/test_report.py`, beside the existing model-answer tests)

Use the existing `_interview_setup` / `_deps` / `build_report` pattern; read
`test_model_answers_group_followups_quote_paragraphs_and_keep_unanswered_questions`
first and copy its setup. Add:

- comma/case drift matches: seed `Sind Sie bereit umzuziehen?`, prepared key
  `Sind Sie bereit, umzuziehen?` → the answer appears under the asked heading;
- extra words match: seed `Erzählen Sie mir bitte etwas über sich.`, prepared key
  `Erzählen Sie etwas über sich.` → matches;
- no cross-match: seed `Was sind Ihre Stärken?`, prepared keys
  `Was sind Ihre Schwächen?` only → no `## Musterantworten` entry for it;
- ambiguous subset is no match: seed `Was sind Ihre Stärken und Schwächen?`, prepared
  keys `Was sind Ihre Stärken?` and `Was sind Ihre Schwächen?` → neither shown;
- short keys never subset-match: prepared key `Warum?` does not attach to seed
  `Warum möchten Sie bei uns arbeiten?`.

Seeds come from partner turns; if `_interview_setup` hard-codes its seeds, write a
small local setup for the new tests that stores the seeds you need the same way
(read how `_interview_setup` stores turns — do not invent a new DB helper).

**Fail-before:** run the five new tests against the unchanged `_model_answers`
(`git stash` the `report.py` change, run them, `git stash pop`) and record which
fail. Expect the first two to fail before and pass after; the last three pass both
times (they guard against over-matching).

## Acceptance

- `.venv/bin/python -m pytest -q -p no:cacheprovider` → 202 + your new tests, all pass.
- `.venv/bin/ruff check src tests` → the same 2 pre-existing errors, no new ones.
- Diff touches only `src/self_talk_coach/conversation/report.py`,
  `tests/conversation/test_report.py` and this brief.

Commit: `fix: match model answers across punctuation and extra-word drift`.

## Off limits

Every other file — in particular `cli.py`, `report_render.py`, `report_metrics.py`,
the question banks, `.env`, `BACKLOG.md`, `STATE.md`. No push, no `/save-session`, no
branch other than `fix/model-answer-match`.

## Report (append under `## Run report` and commit it)

Baseline lines; fail-before result per new test; final pytest and ruff lines; commit
SHAs; anything not done and why.

## Run report

Executed on the VPS on 2026-11-04, on `fix/model-answer-match`, starting at
`6ef323f`. The working tree was clean before execution.

### Baseline (before any edit)

- `.venv/bin/python -m pytest -q -p no:cacheprovider` → `202 passed in 21.24s`.
- `.venv/bin/ruff check src tests` → `Found 2 errors.` / `[*] 2 fixable with --fix.`
  Both were pre-existing I001 findings: `src/self_talk_coach/conversation/session.py:3`
  and `tests/conversation/test_partner.py:226`.

### Fail-before evidence

Added the five tests first, then ran them against the unchanged production code:

```bash
.venv/bin/python -m pytest -v -p no:cacheprovider tests/conversation/test_report.py -k model_answer_match
```

| New test | Before fix | After fix (full suite) |
|---|---|---|
| `test_model_answer_match_comma_and_case_drift` | FAILED: expected Musterantworten section absent | PASSED |
| `test_model_answer_match_extra_words` | FAILED: expected Musterantworten section absent | PASSED |
| `test_model_answer_match_no_cross_match` | PASSED | PASSED |
| `test_model_answer_match_ambiguous_subset` | PASSED | PASSED |
| `test_model_answer_match_short_key_not_subset` | PASSED | PASSED |

Fail-before summary: `2 failed, 3 passed, 11 deselected in 1.30s`.
The comma test also uses an uppercase prepared key to exercise casefolding.

### Implementation and final verification

- Added a pure `_prepared_key` resolver: Unicode-aware normalization, unique
  exact token-sequence match first, then a unique subset with at least three
  distinct tokens. Absent seeds return no match.
- Kept the asked seed as heading and grouping key; the resolved prepared key
  selects the model answer. Existing ordering, follow-up grouping and unanswered
  question tests pass.
- `.venv/bin/python -m pytest -q -p no:cacheprovider` → `207 passed in 30.02s`.
- `.venv/bin/ruff check src tests` → `Found 2 errors.` / `[*] 2 fixable with --fix.`
  Exactly the same two pre-existing I001 findings; no new findings.
- `bash scripts/lint-arch.sh` → `lint-arch: PASS — all checks clean`.
- `git diff --check` → clean.
- Self-reviewed the entire implementation/test diff against this brief; no
  additional findings. No fresh-agent review was performed (project engineering
  rules reserve subagents for explicit user requests).

### Commits and execution notes

- Fix commit: `5557168` — `fix: match model answers across punctuation and extra-word drift`.
- Run-report commit: the separate commit adding this section, titled
  `docs: record model-answer match run report` (its SHA is available in `git log`;
  a commit cannot record its own SHA in its contents).
- Ruling: ran fail-before before editing `report.py`, rather than stashing a
  production edit afterward; this proves the same unchanged-code condition
  directly and avoids unnecessary stash operations.
- Ruling: used this brief as the execution record and the existing clean target
  branch, without creating a worktree, scratch ledger or another plan; the brief
  restricts changes to three files and prohibits any other branch.
- Nothing in the requested implementation or acceptance checks was left undone.
  The two existing lint errors were left alone as instructed. No installs,
  network calls, real-database access, CLI runs, pushes or `/save-session` runs.

## Laptop review (2026-11-04)

Merged as `505ad00`. Clean worktree, `PYTHONPATH=src` (the venv's editable install points at the main checkout, so a worktree run without it tests main's code): 207 passed; ruff the same 2 I001. Fail-before with main's `report.py`: the two drift tests fail, the three guards pass. Real data, read-only (`mode=ro`) with the real questionnaire: conversations 12/13/14 match 6/9/2 (was 4/7/2). The one remaining miss is "beruflichen Hintergrund" vs "beruflichen Werdegang" — a synonym, correctly not guessed.
