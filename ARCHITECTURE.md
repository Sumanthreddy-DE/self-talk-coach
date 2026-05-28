# Architecture: self-talk-coach

## Domain

[What this system does in 2-3 sentences. Business context, not tech.]

## Layer model

Dependency direction flows top → bottom. Upper layers import lower; never reverse.

```
[Domain]
├── types/     — pure types, no logic, no imports from sibling layers
├── config/    — constants, env. Imports: types/
├── repo/      — data access. Imports: types/, config/
├── service/   — business logic. Imports: types/, config/, repo/
├── api/       — HTTP handlers. Imports: service/
└── ui/        — frontend. Imports: types/, api/ (via generated client)
```

Cross-cutting (auth, logging, telemetry) → inject via provider/DI, not direct import.

## Package map

```
src/
├── [domain]/   — [what it owns]
└── shared/     — types and utils shared across domains
```

## Enforced invariants

- No circular imports (enforced by: _add linter_)
- Layer boundaries respected (enforced by: _add linter_)
- Max file size: 800 lines
- No magic strings for domain values (enums/const maps only)

## Decision log

<!-- YYYY-MM-DD — decision — why (one line each) -->
