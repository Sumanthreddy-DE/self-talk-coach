# Execution plans

Plans are first-class artifacts — versioned in the repo, not in external tools.

## Directories

- **active/** — in-progress plans. Filename: `YYYY-MM-DD-<slug>.md`
- **completed/** — finished plans. Move here when done. Keep as historical record.

## Plan format

Use the `write-plan` skill to generate. Minimal structure:

```markdown
# Plan: [Feature name]

## Goal
[What success looks like.]

## Steps
- [ ] Step 1
- [ ] Step 2

## Decision log
<!-- Decisions made during execution, with rationale -->
```
