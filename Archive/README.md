# Archive

Frozen artefacts from earlier project phases. Not loaded by anything; kept for reference only.

## Layout (grow lazily — only create subfolders when first file arrives)

```
Archive/
├── phase-1/           # Phase 1 plan + design (when superseded)
├── phase-2/           # Phase 2 plan + design (when superseded)
├── phase-3/           # Phase 3 plan + design (when superseded)
├── brainstorming/     # Early exploration docs, deep-research dumps
├── memory/            # Deprecated auto-memory files (moved here, not deleted)
├── sessions/          # Stale `/save-session` .tmp files from old skill output location
```

## Conventions

- **Move-only.** Never delete. `git mv` for tracked files; plain `mv` for untracked.
- **Per-file index.** Add a one-liner here when you archive something (file → why archived → live replacement).
- **Pointer to live source-of-truth.** When a doc is superseded, name the live replacement in its archive entry.

## Source of truth (live, not here)

- Open issues: `<repo>/BACKLOG.md`
- Current plan: `<repo>/docs/exec-plans/<active-plan>.md`
- Live status: `~/.claude/projects/<cwd-slug>/memory/project_<name>.md`

## Archived files

_(populate as files move in)_
