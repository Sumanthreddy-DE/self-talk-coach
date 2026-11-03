# report-model-answers — task brief

**Status:** done
**Last verified:** 2026-11-03

BACKLOG S2 `report-model-answers`. Written for an agent working on the VPS in opencode;
reviewed and merged on the laptop. Branch: `feat/report-model-answers`.

## Goal

Since `ecb55b2`, interview questionnaires load with `Seed.model_answer`
(`src/self_talk_coach/conversation/question_bank.py`). Nothing uses it yet. After an
interview session, the report (`stc report <id>`, also built at the end of `stc talk`)
should show, per question, what the learner said next to the prepared model answer.

**Privacy:** the real questionnaire is personal and not in this repo. Do not search for
it or open it. Tests use synthetic seeds only.

## How the data connects (verified 2026-11-03)

- Each **partner** turn stores `seed` = the bank question's exact `Seed.text`
  (`session.py:193` `self._s.seed_text = seed`, `seed = picked.text` at line 176; written
  by `insert_turn(..., seed=s.seed_text)` at line 215). Follow-up partner turns on the
  same question carry the same seed.
- `answer_pairs(turns)` (`report_metrics.py:44`) gives (partner turn, learner turn that
  answered it) in order.
- `report_deps(conn, paths, cfg, status)` (`cli.py:390`) builds `ReportDeps`; `cfg` is
  the `TalkConfig` with `question_banks` (paths). Both report entry points call it
  (`cli.py:385` after `stc talk`, `cli.py:433` in `stc report`).
- `build_report` (`report.py:56`) fills `ReportData`; `render_report`
  (`report_render.py:44`) renders sections in order.

## Decided — do not change these

1. **ReportDeps** gets `model_answers: Mapping[str, str] = field(default_factory=dict)`
   (question text → model answer), placed after `status`. Existing callers and tests
   keep working without passing it.
2. **report_deps** fills it: `load_banks(cfg.question_banks)` → `{s.text: s.model_answer
   for s in seeds if s.model_answer}`. If `load_banks` raises (missing file, unreadable),
   use `{}` and call `status(f"[Hinweis] Musterantworten übersprungen: {exc}")` — the
   report must still be built, and the skip must be visible.
3. **build_report** computes a new `ReportData` field
   `model_answers: list[tuple[str, str, str]]` = (question, learner answers, model answer):
   for each distinct partner-turn `seed` that is a key of `deps.model_answers`, in order of
   first appearance, collect the `text` of every learner turn that `answer_pairs` pairs
   with a partner turn carrying that seed, joined with ` / `. A question asked but never
   answered gets `–` as learner text. Seeds not in the mapping are skipped. Mein-Tag
   conversations (`mein_tag` true) → empty list.
4. **render_report**: when the list is non-empty, append at the very end (after
   `## Neue Wörter`):

   ```text
   ## Musterantworten
   ### <question>
   **Du:** <learner answers>

   > <model answer line 1>
   > <model answer line 2>
   ```

   One `###` block per question, blank line between blocks. Every model-answer line gets
   the `> ` prefix; an empty line inside the answer becomes a bare `>`. When the list is
   empty, no heading at all (existing reports stay byte-identical).
5. Nothing else in the report changes. No LLM call, no DB schema change.

## Not decided — your call, record it in the handoff

Helper names and where the collection helper lives (`report.py` or `report_metrics.py`).

## Tests

- `tests/conversation/test_report.py` (see its `ReportDeps(...)` at line ~62 and
  `test_full_report_written_and_candidates_stored` for seeding turns): a conversation with
  two partner turns on seed A (one follow-up), one on seed B, one on seed C; learner
  answers to all but C; `model_answers` = {A: two-paragraph answer, C: one line} →
  report ends with `## Musterantworten`, A shows both learner answers joined by ` / `
  and the `>`-quoted answer including the bare `>` line, C shows `**Du:** –`, B absent.
- Same conversation with `model_answers={}` → no `## Musterantworten` and the report text
  equals what the current code produces (compare against a run without the field).
- `report_deps` with a `cfg` whose `question_banks` points to a missing file → returns deps
  with `{}` and the status callback received the `[Hinweis] Musterantworten übersprungen`
  line (use a list-appending status function; build a minimal `cfg` stand-in).
- **Run the new tests against the current code first and confirm they fail**; report
  that in the handoff.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

Laptop baseline on 2026-11-03 (`main` at `15a157f`): **197 passed**; ruff shows the
**2 known I001** findings (`src/self_talk_coach/conversation/session.py:3`,
`tests/conversation/test_partner.py:226`). Not yours; no new finding allowed.
Run both once before you start and put the output in the handoff.

## Rules

- Commits: (1) deps + data + render + tests, message prefix `report-model-answers:`;
  (2) the handoff.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, anything under
  `docs/superpowers/`, or `data/`. No new files except the handoff. No `/save-session`.
  No push.
- End: write `docs/handoff-2026-11-03-report-model-answers.md` — files changed, the last
  5 lines of the final pytest run, ruff result, commit SHAs, the fail-before result,
  every "your call" decision with one line of why, anything not done. Commit it.
