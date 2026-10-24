# self-talk-coach

Spoken German practice from the command line. A voice conversation partner that
waits when you freeze, plus a local library that transcribes your own German
self-talk videos.

> **Kurzfassung (DE):** `stc talk` führt ein gesprochenes Gespräch auf Deutsch.
> Du sprichst, Deepgram transkribiert, ein LLM antwortet als Gesprächspartner,
> edge-tts spricht die Antwort. Wenn du nach einer Frage stockst, hilft der Partner
> schrittweise weiter. Fehler greift er korrigiert wieder auf, ohne Grammatikvortrag.
> Nach jedem Gespräch kommt ein Bericht: deine häufigsten Fehler mit Korrektur, Freeze-Zeiten,
> Hörverstehen und neue Wörter mit Bedeutung. Im Vorstellungsgespräch siezt dich der Partner.
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

**Job interview.** Sections whose name starts with `Interview` (for example
`## Interview: Core`) turn the partner into an HR interviewer. It says "Sie" in every
question, correction and hint, asks the questions in the order of your bank, and lets an
answer run up to 120 s instead of 60 s.

**Comprehension check.** Every 4th partner turn asks no question. The partner tells you
something with two concrete details (team size, a city, a number) and asks you to retell
it. The report scores the retelling 0–2.

**Mein Tag.** `stc talk --mein-tag` (or `m` in the start menu) is free talk about your day.
The partner only asks short follow-up questions, never corrects you while you talk,
gives German words back for any English you use, and waits about 15 s before helping.

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
under `data/conversations/<id>/`.

### 2. Session report

When a conversation ends, one LLM call (default `claude-sonnet-5`) reads the transcript and
`stc talk` prints a report, saved as `data/conversations/<id>/report.md`:

| Section | What it shows |
|---|---|
| Top-Fehler | Your most frequent error types, each with your sentence and the corrected one |
| Besser formulieren | Correct but unnatural sentences, said more naturally |
| Englisch → Deutsch | English words you used, with the German word |
| Freeze | Seconds before each answer, median, change against your last conversations |
| Hörhilfen | How often you used replay, slower or text, and which partner sentences were hard |
| Rettungssätze | Phrases you used to buy time, and where help came but you used none |
| Verständnis-Checks | Score per comprehension check and what you left out |
| Neue Wörter | Partner words outside a ~4000-word B1 list that you have not used yourself, with an English meaning |

Every quoted sentence is checked against what you actually said; a finding whose quote is
not in your turn is dropped, and the console says how many. Capitalisation and punctuation
come from speech-to-text, so they are never reported as errors. If the report call fails,
you still get the numbers, and `stc report <id>` runs it again.

New words also collect in one file, `data/neue-woerter.md`, newest conversation first:

```markdown
## Gespräch 13 — 2026-10-24 — Interview: Core
- [ ] **Vollzeitstelle** — full-time position · „… und suchen jetzt eine Vollzeitstelle?“
- [ ] **mittelständisch** — medium-sized (company) · „Wir sind ein mittelständisches Unternehmen …“
```

Tick a word (`[x]`) once you have taken it into your own list; ticks survive a rerun.

If the main model fails, the partner retries with the fallback model and the console
says so. If both fail, the session asks the scenario question directly rather than
stopping.

### 3. Self-talk library

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
| `STC_MEIN_TAG_LADDER_SECONDS` | Help-ladder timings in Mein Tag | `15,25,35` |
| `STC_REPORT_MODEL` | Model for the session report | `claude-sonnet-5` |
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
stc talk                                # choose a scenario from the menu
stc talk --scenario "Interview: Core"   # or start in one directly
stc talk --mein-tag                     # free talk about your day
stc report 13                           # rebuild the report of conversation 13
```

The new-word list needs the spaCy German model once:
`.venv\Scripts\python -m spacy download de_core_news_lg`. Without it the report skips
that section and says why.

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
├── conversation/           # stc talk: session loop, partner, STT, TTS, help ladder, banks, report
├── db.py, paths.py         # SQLite schema and the data/ layout
├── ingest.py, transcribe.py, transcript_export.py   # self-talk library
├── mine.py                 # new-word miner used by the report
└── enrich.py, anki.py      # Anki export from the first MVP (not in the CLI yet)
resources/baseline-de-b1.txt      # ~4000 B1 lemmas from wordfreq (MIT), see resources/README.md
docs/adr/                         # design decisions, e.g. own turn loop over a voice-agent framework
```

Tests: `.venv\Scripts\python -m pytest`

## Status and next steps

Active personal project. Working today: the conversation partner with job-interview
mode, comprehension checks, the session report with the new-word list, and the
self-talk library. Tested live on two job-interview conversations (2026-10-24);
Mein Tag is built and unit-tested but has not had a live run yet.

Known gaps: partner turns sometimes run three sentences, which is long by ear; if the
text-to-speech service fails, the session stops instead of falling back to text.
Next: a review queue for the stored corrections, then Anki export (`enrich.py` /
`anki.py`, not wired into the CLI yet).

## License

MIT, see [LICENSE](LICENSE).
