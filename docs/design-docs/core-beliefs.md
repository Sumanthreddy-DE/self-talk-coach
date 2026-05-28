# Core beliefs: self-talk-coach

Operating principles for agents working in this repo. Override global defaults where listed.

## Non-negotiable

1. **Parse, don't validate** — external data parsed at system boundary (zod, pydantic, etc). No mid-logic narrowing on assumed shapes.
2. **No magic strings** — domain values in enums or const maps, never inline string literals.
3. **Fail loud** — throw/return errors explicitly. Never swallow with empty catch or `_ = err`.
4. **Repo-local truth** — every decision shaping the codebase lives here. Slack/Notion decisions → one-line entry in `ARCHITECTURE.md` decision log.

## Preferred

- Boring tech over clever (composability, stability, training-data coverage)
- Shared util packages over duplicated helpers
- Typed SDK over manual HTTP calls to external APIs
- Implement small well-understood utility > opaque third-party with hidden behavior

## Definition of done

- [ ] Tests pass (unit + integration)
- [ ] Lint + typecheck clean — zero new exemptions without inline comment explaining why
- [ ] Complex task: plan moved to `docs/exec-plans/completed/`
- [ ] Surprising decision: one-line entry added to `ARCHITECTURE.md` decision log
