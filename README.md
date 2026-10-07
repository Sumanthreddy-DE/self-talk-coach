# self-talk-coach

Spoken German practice from the command line. A voice conversation partner that
waits when you freeze, plus a local library that transcribes your own German
self-talk videos.

> **Kurzfassung (DE):** `stc talk` führt ein gesprochenes Gespräch auf Deutsch.
> Du sprichst, Deepgram transkribiert, ein LLM antwortet als Gesprächspartner,
> edge-tts spricht die Antwort. Wenn du nach einer Frage stockst, hilft der Partner
> schrittweise weiter. Fehler greift er korrigiert wieder auf, ohne Grammatikvortrag.
> Dazu kommt eine lokale Mediathek: eigene Selbstgespräch-Videos importieren und mit
> faster-whisper offline transkribieren.

Built for one learner (me, around B1) who wants to speak more and freeze less.
It is a personal tool, shared as-is.

## What it does

### 1. Conversation partner: `stc talk`

One turn looks like this:

1. You press **SPACE**, speak German, press **SPACE** again.
2. Deepgram (`nova-3`, German) transcribes what you said.
3. An LLM partner answers in German through any OpenAI-compatible chat endpoint.
   If you made a mistake, it repeats your sentence back in corrected form, the way
   a native speaker would ask a follow-up question. No explanation, no lecture.
4. `edge-tts` reads the reply aloud (default voice `de-DE-SeraphinaMultilingualNeural`).

If you go quiet after a question, a **help ladder** steps in. The default timings
are 4, 8 and 12 seconds:

| After | The partner |
|---|---|
| 4 s | Nudges you ("Lass dir ruhig Zeit.") |
| 8 s | Offers a sentence starter |
| 12 s | Rephrases the question more simply |

Topics come from your own **question banks**: Markdown files with `## ` sections and
numbered questions. Pick a scenario at the start or switch mid-conversation. Sections
named in `STC_PHRASE_SECTIONS` hold sentences *you* should say; for those, the partner
role-plays a situation that invites the phrase instead of asking it as a question.

Keys during a conversation:

| Key | Action |
|---|---|
| `SPACE` | Start / stop speaking |
| `r` | Repeat the last reply |
| `s` | Repeat it slower |
| `t` | Show the reply as text |
| `f` | Scenario list |
| `w` | Next scenario |
| `q` | End the conversation |

Every turn is saved: text and timings in a local SQLite database, audio as Opus files
under `data/conversations/<id>/`. At the end you get the turn count and your median
"freeze" time, the pause before you started answering.

If the main model fails, the partner retries with the fallback model and the console
says so. If both fail, the session asks the scenario question directly rather than
stopping.

### 2. Self-talk library

Record yourself talking German, then turn the videos into searchable transcripts.
Transcription runs locally with `faster-whisper`; nothing leaves your machine.

```bash
stc init                                   # create data/ and the SQLite database
# drop videos into data/media/inbox/
stc import                                 # move them into the library, skip duplicates
stc transcribe                             # faster-whisper, default: medium, int8, CPU
stc export transcripts --format markdown   # or --format json
```

## Requirements

- Python 3.12+
- `ffmpeg` on `PATH` (audio extraction and Opus storage)
- **Windows** for `stc talk`: key handling uses `msvcrt`, so it needs a real Windows
  console. The library commands are not tied to Windows.
- A microphone and speakers
- For `stc talk`: a Deepgram API key and an OpenAI-compatible chat endpoint that
  serves the partner and fallback models

## Setup

```powershell
git clone https://github.com/Sumanthreddy-DE/self-talk-coach.git
cd self-talk-coach
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env
```

Fill in `.env`:

| Variable | Needed for | Default |
|---|---|---|
| `DEEPGRAM_API_KEY` | `stc talk` (required) | none |
| `GATEWAY_BASE_URL`, `GATEWAY_API_KEY` | `stc talk` (required) | none |
| `STC_QUESTION_BANKS` | `stc talk` (required): `;`-separated absolute paths to your Markdown banks, read in place | none |
| `STC_PARTNER_MODEL` | Main partner model | `deepseek-v4-pro` |
| `STC_FALLBACK_MODEL` | Used when the main model fails | `claude-sonnet-5` |
| `STC_TTS_VOICE` | edge-tts voice | `de-DE-SeraphinaMultilingualNeural` |
| `STC_LADDER_SECONDS` | Help-ladder timings | `4,8,12` |
| `STC_PHRASE_SECTIONS` | Bank sections that hold phrases to say | `Daily Life In Germany;Office German;Szenario` |

A question bank looks like this:

```markdown
## Daily
1. Was hast du heute schon gemacht?
2. Wie sieht dein typischer Morgen aus?

## Office German
1. Könnten Sie mir das bitte noch einmal erklären?
```

Optional: put a short description of yourself in `data/learner-profile.md` (level,
job, interests). The partner reads it and adapts.

Run from the repo root, since `data/` is relative:

```powershell
stc talk                     # choose a scenario from the menu
stc talk --scenario "Daily"  # or start in one directly
```

## Privacy

- `data/` (your audio, transcripts and database) is gitignored and never committed.
  The only sample in the repo, `samples/synthetic-transcript.json`, is hand-written,
  not a recording.
- `stc talk` sends your audio to Deepgram and the text to your chat endpoint.
  `stc transcribe` runs fully offline.

## Project layout

```
src/self_talk_coach/
├── cli.py                  # Typer entry point (`stc`)
├── conversation/           # stc talk: session loop, partner, STT, TTS, help ladder, banks
├── db.py, paths.py         # SQLite schema and the data/ layout
├── ingest.py, transcribe.py, transcript_export.py   # self-talk library
└── mine.py, enrich.py, anki.py   # vocab miner from the first MVP (not in the CLI yet)
resources/baseline-de-b1.txt      # ~4000 B1 lemmas from wordfreq (MIT), see resources/README.md
docs/adr/                         # design decisions, e.g. own turn loop over a voice-agent framework
```

Tests: `.venv\Scripts\python -m pytest`

## Status and next steps

Active personal project. Working today: the conversation partner and the self-talk
library. Next: an analysis pass over stored transcripts that suggests corrections and
better phrasings, then a review queue. The original idea, mining unknown words from
self-talk into Anki cards, lives in `mine.py` / `enrich.py` / `anki.py` and is not
wired into the CLI yet.

## License

MIT, see [LICENSE](LICENSE).
