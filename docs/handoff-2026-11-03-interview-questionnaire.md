# Interview questionnaire — handoff

**Status:** done
**Last verified:** 2026-11-03

Branch: `feat/interview-questionnaire`. Starting HEAD: `b2eac0d`.

## Files changed

- `src/self_talk_coach/conversation/question_bank.py`: last-field optional
  `Seed.model_answer`, questionnaire parser, and per-file format detection.
- `tests/conversation/test_question_bank.py`: exact synthetic sample and six new
  test cases; existing tests unchanged. Covers full seed equality, merged variants,
  paragraphs, answer lists, interview sections, mixed-format loading, detection's
  two required heading types, empty answers, boundaries, and duplicate isolation.
- `docs/handoff-2026-11-03-interview-questionnaire.md`: this handoff.

## Baseline (before edits)

`.venv/bin/python -m pytest -q`:

```text
........................................................................ [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
191 passed in 19.96s
```

`.venv/bin/ruff check src tests`: exit 1, exactly two known `I001` findings:
`src/self_talk_coach/conversation/session.py:3` and
`tests/conversation/test_partner.py:226` (`Found 2 errors.`, both fixable).

## Fail-before evidence

Before changing production code, ran:

```bash
.venv/bin/python -m pytest -q tests/conversation/test_question_bank.py -k questionnaire
```

Result: **4 failed, 2 passed, 9 deselected in 0.22s**. Three failures were
`ImportError` for the absent `parse_questionnaire`; the loading test failed because
`Seed` did not accept `model_answer`. The two negative-detection cases already passed,
as expected. All 15 question-bank tests passed after implementation.

## Final verification

Final `.venv/bin/python -m pytest -q` output (the run emitted four lines, reproduced
in full rather than inventing a fifth):

```text
........................................................................ [ 36%]
........................................................................ [ 73%]
.....................................................                    [100%]
197 passed in 19.61s
```

- `.venv/bin/ruff check src tests`: exit 1; the same two baseline `I001` findings,
  no new findings. Targeted Ruff check on both changed Python files passed.
- `bash scripts/lint-arch.sh`: PASS.
- `git diff --check`: PASS.
- Inline diff review against all eight decisions: no outstanding findings.
  No subagent review was run, per the agent rules; laptop review remains the
  planned independent review.

## Your-call decisions and rationale

- `_GROUP` and `_QUESTION` compiled multiline regexes serve detection and parsing:
  matching the exact specified prefixes prevents divergent format rules.
- `parse_questionnaire` collects each numbered group separately; private helper
  `_questionnaire_section` parses its questions: this prevents duplicate merging
  across group boundaries, including groups with identical display titles.
- `itertools.groupby` merges adjacent normalized question text: nonconsecutive
  repeats remain separate, and bank order is preserved without a global map.
- Answer trimming removes blank lines only, preserving indentation and inner
  whitespace; a whole-string `strip()` would alter answer text.
- Singleton answers keep their text without a variant label; merged answers prefix
  each nonempty version with its label when present. Empty versions contribute no
  answer text, and all-empty results stay `None`, honoring the empty-answer rule.
- Used the existing brief as the execution record and this handoff for decisions;
  no scratch ledger, worktree, or extra plan files were created because the brief
  expressly permits only this new file and the requested branch was already clean.

## Commits

1. `468b60b29f6aef6a0e90356e92581caa1fad1ff4` —
   `interview-questionnaire: parse question headings and model answers`.
2. This handoff is the following commit, titled
   `interview-questionnaire: document verification and handoff`; resolve its SHA
   with `git log -1 --format=%H -- docs/handoff-2026-11-03-interview-questionnaire.md`.
   A file cannot contain the SHA of its own enclosing commit.

## Anything not done

The real personal questionnaire was neither searched for nor read; validation
against it is reserved for the laptop review. `model_answer` is not consumed by
session, partner, or report code, as specified. No push performed. No unrelated
lint fixes, backlog/state/memory/data changes, or plan-status edits.
