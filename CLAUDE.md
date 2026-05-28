# self-talk-coach

[One sentence: what this system does.]

## Navigation

| Resource | Purpose |
|---|---|
| `ARCHITECTURE.md` | Domain model, layers, dependency rules |
| `docs/design-docs/core-beliefs.md` | Non-negotiable operating principles |
| `docs/design-docs/index.md` | All design docs + verification status |
| `docs/exec-plans/active/` | In-progress execution plans |
| `docs/exec-plans/completed/` | Finished plans (historical record) |
| `docs/references/` | External API docs, vendor llms.txt |

## Stack

- **Language**: 
- **Framework**: 
- **Database**: 
- **Package manager**: 

## Dev commands

```bash
# Dev:    
# Test:   
# Lint:   
# Build:  
```

## Rules (project overrides)

- **Session start**: At the start of the first message in each session, read `ARCHITECTURE.md` and `docs/design-docs/core-beliefs.md`. If either still contains placeholder text (`[Domain]`, `self-talk-coach`, blank sections) → trigger the appropriate action: draft `ARCHITECTURE.md` by scanning `src/`, package config files, and README, then confirm with user before writing; OR ask user the 4 core-beliefs questions before any significant work. Also read `docs/design-docs/index.md` and flag any row with status "⚠ needs review" or "✗ outdated".
- **exec-plans**: Plans save to `docs/exec-plans/active/YYYY-MM-DD-<slug>.md`. This overrides the write-plan skill default (`docs/superpowers/plans/`). Move to `docs/exec-plans/completed/` when task is done.
- **lint**: Before committing, run `bash scripts/lint-arch.sh`. Do not suppress violations without an inline comment explaining why.
- **design-docs/index.md**: Add a row whenever a new design doc is created. Keep Status column current (✓ current / ⚠ needs review / ✗ outdated).
