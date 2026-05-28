# ADR 0003 – genanki over AnkiConnect

**Status:** Accepted
**Date:** 2026-05-28

## Decision

Export cards via `genanki` (offline `.apkg` builder) instead of `AnkiConnect` (HTTP plugin to a running Anki desktop instance).

## Why

- No running Anki required during pipeline execution
- Works headless on any machine; portable to AnkiDroid via file transfer
- `.apkg` is a stable, well-documented format
- Sumanth uses AnkiDroid on Android primarily; AnkiConnect is desktop-only

## Trade-off

- One-way: cannot update existing cards in-place from outside Anki
- Stable `model_id` partially mitigates this (re-imports update fields on matching IDs)

Acceptable for V1. AnkiConnect could be added as an alternative exporter later if in-place updates become needed.
