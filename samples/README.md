# samples/

Synthetic data for offline pipeline testing. None of this is real user data.

## synthetic-transcript.json

A hand-authored fake nightly self-talk in German, ~43 segments, ~5.5 minutes of
fake duration. Schema matches the real Whisper output produced in S2, so
downstream stages (mine, enrich, anki) can be tested against this file without
needing real audio.

The text is intentionally seeded with B2+ vocabulary that the mining pipeline
should surface, e.g. `beharrlich`, `verwirklichen`, `nachsichtig`,
`Pflichtgefühl`, `Modellinterpretierbarkeit`, `unvermeidlich`,
`Außenstehender`, `Verlässlichkeit`, `langwierig`, `Achtsamkeit`. If the miner
runs against this file and surfaces fewer than ~10 unknown lemmas, something is
broken.

### Usage

```
.venv/Scripts/python -m self_talk_coach.mine samples/ -o data/out/unknown.json
```

(Implemented in S4.)
