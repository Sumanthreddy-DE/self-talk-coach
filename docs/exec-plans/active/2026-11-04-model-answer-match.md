# Brief — model answers survive small wording drift

**Status:** active
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
