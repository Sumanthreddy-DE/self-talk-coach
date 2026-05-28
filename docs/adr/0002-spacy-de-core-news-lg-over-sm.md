# ADR 0002 – spaCy `de_core_news_lg` over `_sm`

**Status:** Accepted
**Date:** 2026-05-28

## Decision

Use spaCy German model `de_core_news_lg` for lemmatization and POS tagging, not `_sm` or `_md`.

## Why

- `_lg` lemmatizes casual register (filler words, separable verbs, compound nouns) noticeably better than `_sm` on informal monologue text
- Better named-entity recognition for the proper-noun filter (`Berlin`, `Mama`, friend names → excluded from vocab candidates)
- Disk cost (~500MB) is fine for a single-user local CLI
- One-time download, no runtime cost vs `_sm`

## Trade-off

- 5× larger than `_sm`, slower load time (~3s vs ~0.5s)
- Larger memory footprint at runtime

Acceptable: load once per CLI invocation, not a hot path.
