# interview-questionnaire-format — task brief

**Status:** active
**Last verified:** 2026-11-03

BACKLOG S3 `interview-questionnaire-format`. Written for an agent working on the VPS
in opencode; reviewed and merged on the laptop. Branch: `feat/interview-questionnaire`.

## Problem

`load_banks` (`src/self_talk_coach/conversation/question_bank.py:38`) parses every
file with `parse_bank` (line 22): `## ` lines are sections, `1. text` lines are
questions. The owner's interview questionnaire uses a different shape — one `##`
heading **per question**, a model answer under it — so today it yields junk: each
question heading becomes a section and the only "questions" are numbered list lines
inside model answers.

**Privacy:** the real questionnaire is personal and lives outside this repo. Do not
search for it, open it or copy it, on this machine or anywhere. Work only from the
synthetic sample below. The laptop review runs your parser over the real file.

## The questionnaire shape (exact)

```markdown
# Interview-Fragenbank — Name

**Stand:** 11 / 26 · **Kurzfassung** · **Hinweis:**

★ = wichtigste Fragen zuerst (ca. zehn)

---

## Wie nutze ich dieses Heft?

- Erst laut antworten, dann lesen.
- Platzhalter in eckigen Klammern ersetzen.

---

# 1. Kern (Core)

## 1.1 ★ Erzählen Sie etwas über sich.

Ich bin Ingenieur und arbeite gern mit Simulation.

---

## 1.2 Warum interessieren Sie sich für diese Stelle?

> Vorbereiten: `[Firmenname]`, `[Produkt]`

Die Stelle passt, weil `[Firmenname]` Berechnung und Software verbindet.

Zweiter Absatz der Antwort.

> **Merksatz (Kurzfassung):** Erst die Firma, dann ich.

---

## 1.3a ★ Was sind Ihre Stärken? — Version A (modern)

Schnelles Prototyping mit Python.

---

## 1.3b ★ Was sind Ihre Stärken? — Version B (klassisch)

Gründlichkeit und saubere Dokumentation.

---

# 5a. Berater-Flow (Karriereberater-Gespräch)

## 5a.1 Welche Branchen interessieren Sie?

Maschinenbau und Energie.

---

## 5.11 Haben Sie Fragen an uns?

Ja, zum Beispiel:

1. Wie sieht ein typischer Tag aus?
2. Wie ist das Team aufgebaut?

---

# 5b. AGG-sensible Fragen (Deflektion)

> **Hinweis:** Diese Fragen sind meist unzulässig.

## 5b.1 Planen Sie eine Familie?

Darauf möchte ich höflich nicht eingehen.

---

# Ende

**Vor dem Gespräch:**
1. Laut üben.
2. Ruhig bleiben.
```

Copy this sample into the test file as a string constant (no new data file). It
mirrors the real file's structure: a title, an unnumbered `##` usage section, numbered
`# N.` / `# Na.` groups, `## N.M` / `## N.Ma` / `## Na.M` question headings with an
optional `★`, `>` note lines, `---` separators, numbered lists inside answers, and an
unnumbered `# Ende` group at the end. (The real file has 56 question headings.)

## Decided — do not change these

1. **Detection.** `load_banks` picks the parser per file: a file that has at least one
   line matching `^# \d+[a-z]?\. ` **and** at least one matching
   `^## \d+[a-z]?\.\d+[a-z]? ` is a questionnaire → new `parse_questionnaire`;
   anything else → `parse_bank`, unchanged. Existing banks must parse exactly as today.
2. **Seed.** Add `model_answer: str | None = None` as the last field of the frozen
   `Seed` dataclass. Nothing else in `Seed` changes; `parse_bank` leaves it `None`.
3. **Sections.** A `# <id>. <title>` group sets the section to
   `Interview: <title>` (e.g. `Interview: Kern (Core)`), so `is_interview()` plays
   it as an interview ("Sie", bank order). Any unnumbered `# ` heading (`# Ende`, the
   title) ends the current group: nothing after it is read until the next numbered
   `# ` group. Unnumbered `## ` headings and everything before the first group are ignored.
4. **Question text.** From `## <id> [★] <text>`: drop the id, the `★` and the spaces
   around it; cut the text at the first ` — ` (space, em dash, space). So
   `1.3a ★ Was sind Ihre Stärken? — Version A (modern)` → `Was sind Ihre Stärken?`.
5. **Model answer.** The lines after the question heading up to the next `---`,
   `## ` or `# ` line, **minus** every line starting with `>`; leading/trailing blank
   lines stripped; inner text kept as written (paragraph breaks and numbered lists
   stay). An empty result → `model_answer=None`.
6. **Variants.** Consecutive headings in one section with the same question text
   (1.3a / 1.3b) become **one** seed. Its `model_answer` is each version's answer,
   prefixed by the part after ` — ` and a colon, joined by a blank line:
   `Version A (modern): Schnelles…\n\nVersion B (klassisch): Gründlichkeit…`.
7. **Expected result for the sample**, in order (section → question):
   `Interview: Kern (Core)` → 1.1, 1.2, merged 1.3;
   `Interview: Berater-Flow (Karriereberater-Gespräch)` → 5a.1, 5.11;
   `Interview: AGG-sensible Fragen (Deflektion)` → 5b.1.
   Six seeds. `# Ende` and its list produce nothing; the two numbered lines inside
   5.11's answer are part of that answer, not seeds. 1.2's answer contains both
   paragraphs and neither `>` line.
8. **Scope.** Parser + detection + `Seed.model_answer` only. Do **not** use
   `model_answer` anywhere yet (session, partner, report) — showing it in the report
   is a separate item.

## Not decided — your call, record it in the handoff

Helper names, regexes, and how you structure the parser internally.

## Tests

In `tests/conversation/test_question_bank.py` (existing tests there use `parse_bank`
and `load_banks` — keep them all passing, unchanged):

- `parse_questionnaire(SAMPLE)` returns exactly the six seeds of decision 7 (section,
  text, model_answer each checked; check the merged 1.3 answer and 1.2's two paragraphs
  in full).
- `load_banks` on a `tmp_path` file with the sample → same six seeds; on a file in
  the existing bank format → same result as `parse_bank` (detection does not misfire).
- `is_interview` is true for every section from the sample.
- **Run the questionnaire tests against the current code first and confirm they
  fail**; report that in the handoff.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

Laptop baseline on 2026-11-03 (`main` at `17a3b00`): **191 passed**; ruff reports the
**2 known I001** findings (`src/self_talk_coach/conversation/session.py:3`,
`tests/conversation/test_partner.py:226`). Not yours — leave them; no new finding.
Run both once before you start and put the output in the handoff.

## Rules

- Commits: (1) tests + parser + detection, message prefix `interview-questionnaire:`;
  (2) the handoff.
- Never edit `BACKLOG.md`, `STATE.md`, memory files, anything under
  `docs/superpowers/`, or `data/`. No new files except the handoff. No `/save-session`.
  No push.
- End: write `docs/handoff-2026-11-03-interview-questionnaire.md` — files changed,
  the last 5 lines of the final pytest run, ruff result, commit SHAs, the fail-before
  result, every "your call" decision with one line of why, anything not done. Commit it.
