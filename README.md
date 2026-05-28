# self-talk-coach

> Persönliches Vokabelminer für deutschsprachige Selbstgespräche – aus eigenen Videos werden Anki-Karten.
> Personal vocab miner for German self-talk – your own videos become Anki cards.

---

## Deutsch

### Was es macht

`self-talk-coach` nimmt deine eigenen deutschsprachigen Selbstgespräch-Videos und baut daraus einen Anki-Deck mit unbekannten Vokabeln (B2+ relativ zu einer Goethe-B1-Basisliste).

Pipeline:

1. **Ingest** – Audio aus Videos extrahieren (ffmpeg, 16 kHz Mono)
2. **Transkribieren** – `faster-whisper` (Deutsch, `medium` + `int8` als Standard)
3. **Minen** – `spaCy de_core_news_lg` lemmatisiert, filtert gegen Goethe-B1-Wortliste
4. **Anreichern** – Claude API liefert Definition (DE+EN), Genus, Beispielsatz
5. **Exportieren** – `genanki` packt alles in eine `.apkg`-Datei

### Schnellstart

```bash
git clone https://github.com/Sumanthreddy-DE/self-talk-coach.git
cd self-talk-coach
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m spacy download de_core_news_lg

cp .env.example .env
# ANTHROPIC_API_KEY in .env einfügen

# Mit synthetischem Beispiel testen (kein echtes Audio nötig)
stc mine samples/
stc enrich --max-cards 5
stc pack
```

### Voraussetzungen

- Python 3.12+
- `ffmpeg` im PATH (Windows: `winget install ffmpeg`, macOS: `brew install ffmpeg`)
- Anthropic API-Schlüssel
- Optional: Anki / AnkiDroid zum Importieren des `.apkg`

### Konfiguration

| Variable | Standard | Zweck |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | – | Pflicht für `stc enrich` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Optionaler Override |

### Lizenz

MIT. Siehe `LICENSE`.

---

## English

### What it does

`self-talk-coach` ingests your own German self-talk videos and produces an Anki deck of unknown vocabulary (B2+ relative to a Goethe-B1 baseline list).

Pipeline: ffmpeg → faster-whisper → spaCy → Claude API → genanki.

### Quickstart

See "Schnellstart" above – commands are identical.

### Requirements

- Python 3.12+
- `ffmpeg` on PATH
- Anthropic API key
- Optional: Anki / AnkiDroid to import the `.apkg`

### License

MIT.

---

## Status

V1 weekend MVP. See `docs/exec-plans/01-weekend-mvp.md` for the construction plan.
