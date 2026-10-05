# Conversation Partner — Phase 0 Spikes Implementation Plan

**Status:** done
**Last verified:** 2026-10-05

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer the five open questions (S0–S4) from the design spec with measured evidence before any production code is written.

**Architecture:** Throwaway scripts under `scripts/spikes/`, sharing one small audio helper. Outputs (audio, JSON results) go to `data/spikes/` (gitignored). Results and the decisions they force are written back into the spec's `## Spike results` section. No `src/` changes in this phase.

**Tech Stack:** Python 3.12, faster-whisper (existing), sounddevice + soundfile (mic/playback), azure-cognitiveservices-speech (TTS), requests (ElevenLabs REST, existing dep), anthropic (existing) + openai SDK (OpenAI-compatible gateway).

**Spec:** `docs/exec-plans/active/2026-10-04-conversation-partner-design.md`

## Global Constraints

- Windows 11, Git Bash, no NVIDIA GPU — faster-whisper runs `device="cpu"`, `compute_type="int8"`.
- Python via `.venv/Scripts/python` (venv recreated in Task 1). Never system Python.
- Nothing under `data/` is ever committed (`.gitignore` has `data/`, `*.wav`).
- API keys only from `.env` (python-dotenv); never printed, never committed.
- Installing packages into `.venv` is confirmed with the user once, at Task 1 Step 3, before running.
- ElevenLabs: buy $1 Starter only at Task 4; cancel renewal the same day.
- Spikes are exploratory scripts: no TDD. The existing 43-test suite must stay green.
- `bash scripts/lint-arch.sh` before each commit (project rule).
- Execution order: Task 1 (S0) → Task 2 (S4) → Task 3 (S1) → Task 4 (S2) → Task 5 (S3) → Task 6. S4 runs before S1 because S1 records with S4's helper.

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Add `spike` optional-dependency group |
| `.env.example` | Add spike/partner env var names |
| `scripts/spikes/_audio.py` | Toggle-key recording, playback, device listing — shared by S4 and S1 |
| `scripts/spikes/s4_audio_keys.py` | S4: headset record/playback + key test |
| `scripts/spikes/s1_record.py` | S1: record the 10 error sentences |
| `scripts/spikes/s1_whisper.py` | S1: transcribe with small/medium (+ initial_prompt), score kept errors, time it |
| `scripts/spikes/s2_tts.py` | S2: Azure voices + ElevenLabs on the same sentences, bytes + rate check |
| `scripts/spikes/s3_partner.py` | S3: 10-exchange scripted run per LLM; latency, tokens, JSON validity, cost projection |
| `docs/exec-plans/active/2026-10-04-conversation-partner-design.md` | Gets `## Spike results` section (Task 6) |

---

### Task 1: S0 — recreate venv, confirm suite green, add spike deps

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies]`)
- Modify: `.env.example`

**Interfaces:**
- Produces: working `.venv` with `self_talk_coach` installed editable plus `spike` extras; env var names used by Tasks 4–5: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `GATEWAY_BASE_URL`, `GATEWAY_API_KEY`.

- [ ] **Step 1: Create the venv**

Run: `py -3.12 -m venv .venv`
Expected: `.venv/Scripts/python.exe` exists.

- [ ] **Step 2: Install project + dev deps, run existing suite**

Run: `.venv/Scripts/python -m pip install -e ".[dev]" && .venv/Scripts/python -m pytest -q`
Expected: last line `43 passed`. If not 43 or any failure → stop, report output, run /diagnose before continuing.

- [ ] **Step 3: Add the `spike` extras group**

In `pyproject.toml`, under `[project.optional-dependencies]` after the `dev` list, add:

```toml
spike = [
    "sounddevice>=0.4.6",
    "soundfile>=0.12",
    "azure-cognitiveservices-speech>=1.38",
    "openai>=1.40",
]
```

Ask the user before installing (Global Constraints), then run: `.venv/Scripts/python -m pip install -e ".[dev,spike]"`
Expected: installs without error; `.venv/Scripts/python -c "import sounddevice, soundfile, azure.cognitiveservices.speech, openai; print('ok')"` prints `ok`.

- [ ] **Step 4: Add env var names to `.env.example`**

Append to `.env.example`:

```bash

# Conversation partner (spikes + v1)
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
# ElevenLabs — ear test only (spike S2)
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
# OpenAI-compatible multi-model gateway (spike S3)
GATEWAY_BASE_URL=
GATEWAY_API_KEY=
```

- [ ] **Step 5: Lint, re-run suite, commit**

Run: `bash scripts/lint-arch.sh && .venv/Scripts/python -m pytest -q`
Expected: `lint-arch: PASS`, `43 passed`.

```bash
git add pyproject.toml .env.example && git commit -m "chore: add spike deps group and partner env vars"
```

---

### Task 2: S4 — headset recording, playback, terminal keys

**Files:**
- Create: `scripts/spikes/_audio.py`
- Create: `scripts/spikes/s4_audio_keys.py`

**Interfaces:**
- Produces (used by Task 3):
  - `SAMPLE_RATE: int = 16000`
  - `record_toggle(prompt: str) -> numpy.ndarray` — waits for SPACE, records mono float32 at 16 kHz until SPACE again, returns samples
  - `save_wav(samples: numpy.ndarray, path: pathlib.Path) -> None`
  - `play(samples: numpy.ndarray, samplerate: int) -> None` — blocking

- [ ] **Step 1: Write the shared helper**

`scripts/spikes/_audio.py`:

```python
"""Shared mic/playback helpers for spikes. Windows-only key handling (msvcrt)."""

from __future__ import annotations

import msvcrt
import queue
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000


def wait_key(allowed: str) -> str:
    """Block until one of the allowed keys is pressed; return it lowercased."""
    while True:
        ch = msvcrt.getwch().lower()
        if ch in allowed:
            return ch


def record_toggle(prompt: str) -> np.ndarray:
    print(f"{prompt}  [SPACE = start]")
    wait_key(" ")
    chunks: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
        chunks.put(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback):
        print("  ● recording …  [SPACE = stop]")
        wait_key(" ")
    parts = []
    while not chunks.empty():
        parts.append(chunks.get())
    samples = np.concatenate(parts)[:, 0] if parts else np.zeros(0, dtype="float32")
    print(f"  ■ {len(samples) / SAMPLE_RATE:.1f}s recorded")
    return samples


def save_wav(samples: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples, SAMPLE_RATE)


def play(samples: np.ndarray, samplerate: int) -> None:
    sd.play(samples, samplerate)
    sd.wait()
```

- [ ] **Step 2: Write the S4 script**

`scripts/spikes/s4_audio_keys.py`:

```python
"""S4: confirm headset mic + playback + terminal keys work on this laptop."""

from __future__ import annotations

import time
from pathlib import Path

import sounddevice as sd

from _audio import SAMPLE_RATE, play, record_toggle, save_wav, wait_key

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s4"


def main() -> None:
    print("Devices:\n", sd.query_devices())
    print(f"Default in/out: {sd.default.device}")
    samples = record_toggle("Say one German sentence into the headset.")
    save_wav(samples, OUT / "mic-test.wav")
    print("Playing back …")
    play(samples, SAMPLE_RATE)

    print("\nKey test: press r, s, t (each once), then q.")
    seen: list[tuple[str, float]] = []
    start = time.perf_counter()
    while True:
        key = wait_key("rstq")
        seen.append((key, round(time.perf_counter() - start, 2)))
        print(f"  key={key!r} at {seen[-1][1]}s")
        if key == "q":
            break
    print("Keys seen:", seen)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it with the headset (user present)**

Run from repo root in **Windows Terminal** (msvcrt needs a real console; Git Bash mintty may not deliver keys): `cd scripts/spikes && ../../.venv/Scripts/python s4_audio_keys.py`
Expected: device list shows the headset; playback is the user's voice, clear, no clipping; `Keys seen` lists r, s, t, q with increasing times.
If keys don't arrive → retry in Windows Terminal/PowerShell; record which terminal works.

- [ ] **Step 4: Record result, commit**

Write in a scratch note (copied into the spec in Task 6): headset device name/index, terminal that delivered keys, any audio issue.

```bash
bash scripts/lint-arch.sh && git add scripts/spikes/_audio.py scripts/spikes/s4_audio_keys.py && git commit -m "spike(s4): headset record/playback and key test"
```

---

### Task 3: S1 — does whisper keep learner errors?

**Files:**
- Create: `scripts/spikes/s1_record.py`
- Create: `scripts/spikes/s1_whisper.py`

**Interfaces:**
- Consumes: `record_toggle`, `save_wav` from `scripts/spikes/_audio.py`
- Produces: `data/spikes/s1/sentence-NN.wav` (10 files), `data/spikes/s1/results.json`

- [ ] **Step 1: Write the recording script**

`scripts/spikes/s1_record.py`:

```python
"""S1 part 1: learner reads 10 sentences that each contain one typical B1 error."""

from __future__ import annotations

from pathlib import Path

from _audio import record_toggle, save_wav

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s1"

# (sentence as spoken, substring that survives only if whisper KEEPS the error)
SENTENCES: list[tuple[str, str]] = [
    ("Ich habe gestern nach Hause gegangen.", "habe gestern nach hause gegangen"),
    ("Gestern ich habe viel gearbeitet.", "gestern ich habe"),
    ("Ich arbeite in die Küche.", "in die küche"),
    ("Ich habe einen Frage.", "einen frage"),
    ("Weil ich habe keine Zeit, ich komme nicht.", "weil ich habe"),
    ("Das ist der Auto von meinem Kollegen.", "der auto"),
    ("Ich bin seit zwei Jahre in Deutschland.", "seit zwei jahre in"),
    ("Ich gehe mit meine Freunde ins Kino.", "mit meine freunde"),
    ("Mein Chef hat gesagt, dass ich muss früher kommen.", "dass ich muss"),
    ("Ich habe mit dem Bus gefahrt.", "gefahrt"),
]


def main() -> None:
    for i, (sentence, _) in enumerate(SENTENCES, start=1):
        samples = record_toggle(f"[{i}/10] Read exactly, mistake included:  {sentence}")
        save_wav(samples, OUT / f"sentence-{i:02d}.wav")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Learner records the 10 sentences**

Run (Windows Terminal): `cd scripts/spikes && ../../.venv/Scripts/python s1_record.py`
Expected: 10 files `data/spikes/s1/sentence-01.wav` … `-10.wav`, each 2–6 s.

- [ ] **Step 3: Write the transcription/scoring script**

`scripts/spikes/s1_whisper.py`:

```python
"""S1 part 2: which whisper config keeps learner errors, and how fast is it on CPU?"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from faster_whisper import WhisperModel

from s1_record import SENTENCES

DIR = Path(__file__).resolve().parents[2] / "data/spikes/s1"
LEARNER_PROMPT = "Äh, also, heute ich bin früh aufgestanden und dann, ähm, ich habe zu Arbeit gefahren."
CONFIGS = [
    ("small", None),
    ("medium", None),
    ("small", LEARNER_PROMPT),
    ("medium", LEARNER_PROMPT),
]


def normalize(text: str) -> str:
    return re.sub(r"[^\wäöüß ]", "", text.lower()).strip()


def main() -> None:
    results = []
    models: dict[str, WhisperModel] = {}
    for size, prompt in CONFIGS:
        model = models.setdefault(size, WhisperModel(size, device="cpu", compute_type="int8"))
        kept = 0
        rows = []
        for i, (sentence, marker) in enumerate(SENTENCES, start=1):
            start = time.perf_counter()
            segments, _ = model.transcribe(
                str(DIR / f"sentence-{i:02d}.wav"),
                language="de",
                vad_filter=True,
                initial_prompt=prompt,
            )
            text = " ".join(s.text.strip() for s in segments)
            seconds = time.perf_counter() - start
            is_kept = marker in normalize(text)
            kept += is_kept
            rows.append({"spoken": sentence, "heard": text, "kept": is_kept, "seconds": round(seconds, 2)})
            print(f"{size:6} prompt={bool(prompt)!s:5} {'KEPT ' if is_kept else 'FIXED'} {seconds:5.2f}s | {text}")
        avg = sum(r["seconds"] for r in rows) / len(rows)
        print(f"==> {size} prompt={bool(prompt)}: kept {kept}/10, avg {avg:.2f}s/sentence\n")
        results.append({"model": size, "initial_prompt": bool(prompt), "kept": kept, "avg_seconds": round(avg, 2), "rows": rows})
    (DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

Note: "FIXED" also covers plain mishearing — read the `heard` column before concluding whisper "corrected" anything.

- [ ] **Step 4: Run it**

Run: `cd scripts/spikes && ../../.venv/Scripts/python s1_whisper.py`
Expected: 40 printed rows, 4 summary lines `==> <model> prompt=<bool>: kept N/10, avg X.XXs/sentence`, and `data/spikes/s1/results.json`. First run downloads `small` and `medium` models (~0.5 GB + ~1.5 GB).

- [ ] **Step 5: Decide and commit**

Decision rule (record in scratch note for Task 6):
- Live model = the config with the most `kept`; ties → faster one. Seconds per sentence is informational (user accepted multi-second latency).
- If the best config keeps < 6/10 → the session report cannot rely on whisper for grammar errors; stop and discuss STT alternatives with the user before Phase 1.

```bash
bash scripts/lint-arch.sh && git add scripts/spikes/s1_record.py scripts/spikes/s1_whisper.py && git commit -m "spike(s1): whisper learner-error preservation test"
```

---

### Task 4: S2 — which voice does the learner want to hear?

**Files:**
- Create: `scripts/spikes/s2_tts.py`

**Interfaces:**
- Produces: `data/spikes/s2/<engine>-<voice>-NN.(wav|mp3)`; decision: TTS engine + voice; confirmation that Azure SDK returns bytes and supports SSML rate (decides RealtimeTTS: needed or not).

- [ ] **Step 1: User gets keys (user action)**

- Azure: create a free Speech resource (F0 tier) in the Azure portal; put key + region in `.env` as `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`.
- ElevenLabs: buy the $1 Starter month, **cancel renewal immediately** (keeps the month), create an API key → `ELEVENLABS_API_KEY`; pick a German-capable voice in the Voice Library → its id into `ELEVENLABS_VOICE_ID`.

- [ ] **Step 2: Write the TTS script**

`scripts/spikes/s2_tts.py`:

```python
"""S2: same German sentences through Azure voices and ElevenLabs; check bytes + rate control."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
import requests
from dotenv import load_dotenv

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s2"
SENTENCES = [
    "Erzählen Sie mir bitte etwas über sich.",
    "Und warum möchtest du gerade bei uns arbeiten?",
    "Ah, du hast gestern bis Mitternacht gearbeitet? Das ist ja echt spät.",
    "Lass dir ruhig Zeit. Wir haben keinen Stress.",
    "Stell dir vor, du gewinnst morgen zehntausend Euro. Was machst du damit?",
]


def azure_config() -> speechsdk.SpeechConfig:
    cfg = speechsdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
    cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm)
    return cfg


def list_azure_german_voices() -> None:
    synth = speechsdk.SpeechSynthesizer(speech_config=azure_config(), audio_config=None)
    result = synth.get_voices_async("de-DE").get()
    for v in result.voices:
        print(v.short_name, v.gender.name)


def azure_tts(text: str, voice: str, rate: str = "0%") -> bytes:
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
        f'<voice name="{voice}"><prosody rate="{rate}">{text}</prosody></voice></speak>'
    )
    synth = speechsdk.SpeechSynthesizer(speech_config=azure_config(), audio_config=None)
    result = synth.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"Azure TTS failed: {result.reason} {result.cancellation_details}")
    return result.audio_data


def elevenlabs_tts(text: str, model_id: str) -> bytes:
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": text, "model_id": model_id, "language_code": "de"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def main() -> None:
    load_dotenv()
    if sys.argv[1:] == ["--list"]:
        list_azure_german_voices()
        return
    voices = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    for voice in voices:
        for i, s in enumerate(SENTENCES, start=1):
            (OUT / f"azure-{voice}-{i:02d}.wav").write_bytes(azure_tts(s, voice))
        (OUT / f"azure-{voice}-slower-02.wav").write_bytes(azure_tts(SENTENCES[1], voice, rate="-25%"))
    if os.environ.get("ELEVENLABS_API_KEY"):
        for model_id in ("eleven_flash_v2_5", "eleven_multilingual_v2"):
            for i, s in enumerate(SENTENCES, start=1):
                (OUT / f"eleven-{model_id}-{i:02d}.mp3").write_bytes(elevenlabs_tts(s, model_id))
    total_chars = sum(len(s) for s in SENTENCES)
    print(f"Done. Files in {OUT}. Characters per engine/voice: {total_chars}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: List real voice names, then synthesize**

Run: `cd scripts/spikes && ../../.venv/Scripts/python s2_tts.py --list`
Expected: list of `de-DE-…Neural` short names. Pick 3 (at least one female, one male, one "Multilingual"/HD if listed) — use names exactly as printed, never from memory.

Run: `../../.venv/Scripts/python s2_tts.py <voice1> <voice2> <voice3>`
Expected: 3×6 Azure `.wav` + 2×5 ElevenLabs `.mp3` in `data/spikes/s2/`, final `Done.` line. If ElevenLabs returns 4xx, check its current API docs for the endpoint/`language_code` field and fix the request — do not guess.

- [ ] **Step 4: Learner ear test**

User listens to all files (same sentence across engines back to back) and ranks: naturalness, clarity for a B1 listener, and whether the `-slower-02` file is still natural. Record the winner + runner-up.

Decision rules (scratch note for Task 6):
- Azure `audio_data` bytes + SSML `prosody rate` worked → Phase 1 calls the Azure SDK directly; **RealtimeTTS is dropped** (not needed).
- ElevenLabs wins clearly → note monthly cost from S3 TTS-character numbers before switching; Azure stays the free default otherwise.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && git add scripts/spikes/s2_tts.py && git commit -m "spike(s2): Azure vs ElevenLabs German voice ear test"
```

---

### Task 5: S3 — partner LLM quality, latency, cost

**Files:**
- Create: `scripts/spikes/s3_partner.py`

**Interfaces:**
- Produces: `data/spikes/s3/results.json`; per model: avg latency, tokens per exchange, JSON-valid rate, sample replies; monthly cost projection.

- [ ] **Step 1: User provides gateway details (user action)**

User names the gateway service; put its OpenAI-compatible base URL and key in `.env` (`GATEWAY_BASE_URL`, `GATEWAY_API_KEY`). List the exact model ids the gateway exposes: run `.venv/Scripts/python -c "import os,openai,dotenv;dotenv.load_dotenv();c=openai.OpenAI(base_url=os.environ['GATEWAY_BASE_URL'],api_key=os.environ['GATEWAY_API_KEY']);print('\n'.join(m.id for m in c.models.list()))"`
Expected: model id list. If the gateway is not OpenAI-compatible (error on `/models`) → stop and check its docs.

- [ ] **Step 2: Write the partner script**

`scripts/spikes/s3_partner.py`:

```python
"""S3: same 10 learner lines through candidate partner LLMs; measure latency, tokens, JSON validity."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s3"

SYSTEM = """Du bist ein Gesprächspartner aus Baden-Württemberg. Du sprichst mit einem Deutschlerner (Niveau B1).
Regeln:
- Kurze Antworten: 1–2 Sätze. Umgangssprachlich, natürlich, Sprachniveau B1.
- Kein Lob, keine Floskeln wie "Super!" oder "Toll gemacht!".
- Wenn der Lerner einen Fehler macht, wiederhole den Satz einmal korrekt im Feld "recast" (ohne Erklärung), sonst null.
- Stelle danach eine Frage zum vorgegebenen Thema, als natürliche Folgefrage oder als plötzlicher Themenwechsel.
- "starter_phrase": ein Satzanfang, mit dem der Lerner antworten könnte.
- "simpler_rephrase": dieselbe Frage einfacher formuliert.
Antworte NUR mit JSON: {"reply": str, "recast": str|null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": bool}"""

# (learner line as a live transcript might contain it, next topic seed chosen by code)
SCRIPT = [
    ("Hallo, ich heiße Sumanth und ich wohne in Reutlingen.", "Arbeit"),
    ("Ich arbeite bei McDonald's in Mössingen, meistens Spätschicht.", "Spätschicht"),
    ("Gestern ich habe bis Mitternacht gearbeitet.", "Schlaf und Freizeit"),
    ("Am Wochenende ich gehe mit meine Freunde in die Stadt.", "Lieblingsessen"),
    ("Ich koche gern indisches Essen, Biryani zum Beispiel.", "Vorstellungsgespräch: Stärken"),
    ("Meine Stärke ist, ich lerne schnell und ich bin zuverlässig.", "Vorstellungsgespräch: Schwächen"),
    ("Äh... meine Schwäche... ich spreche noch nicht so gut Deutsch.", "Hypothetisch: Lottogewinn"),
    ("Ich würde eine Reise nach Indien machen und meine Familie besuchen.", "Wohnung"),
    ("Meine Wohnung ist klein aber die Miete ist billig.", "Pläne in fünf Jahren"),
    ("In fünf Jahren ich möchte als Ingenieur arbeiten.", "Abschied"),
]


class PartnerTurn(BaseModel):
    reply: str
    recast: str | None
    starter_phrase: str
    simpler_rephrase: str
    topic_jump: bool


def run_model(client: OpenAI, model: str) -> dict:
    messages = [{"role": "system", "content": SYSTEM}]
    rows = []
    for learner, seed in SCRIPT:
        messages.append({"role": "user", "content": f"Lerner: {learner}\nNächstes Thema: {seed}"})
        start = time.perf_counter()
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.8, max_tokens=300)
        seconds = time.perf_counter() - start
        raw = resp.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": raw})
        try:
            turn = PartnerTurn.model_validate_json(raw.strip().removeprefix("```json").removesuffix("```").strip())
            valid, spoken = True, f"{turn.recast or ''} {turn.reply}".strip()
        except ValidationError:
            valid, spoken = False, raw
        usage = resp.usage
        rows.append({
            "learner": learner, "seed": seed, "raw": raw, "valid_json": valid, "seconds": round(seconds, 2),
            "in_tokens": usage.prompt_tokens if usage else None,
            "out_tokens": usage.completion_tokens if usage else None,
            "tts_chars": len(spoken),
        })
        print(f"[{model}] {seconds:4.1f}s valid={valid} | {spoken[:110]}")
    n = len(rows)
    summary = {
        "model": model,
        "valid_rate": sum(r["valid_json"] for r in rows) / n,
        "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "avg_in_tokens": sum(r["in_tokens"] or 0 for r in rows) / n,
        "avg_out_tokens": sum(r["out_tokens"] or 0 for r in rows) / n,
        "avg_tts_chars": sum(r["tts_chars"] for r in rows) / n,
        "rows": rows,
    }
    print(f"==> {model}: valid {summary['valid_rate']:.0%}, {summary['avg_seconds']}s, "
          f"in {summary['avg_in_tokens']:.0f} / out {summary['avg_out_tokens']:.0f} tok, {summary['avg_tts_chars']:.0f} chars\n")
    return summary


def main() -> None:
    load_dotenv()
    client = OpenAI(base_url=os.environ["GATEWAY_BASE_URL"], api_key=os.environ["GATEWAY_API_KEY"])
    OUT.mkdir(parents=True, exist_ok=True)
    results = [run_model(client, m) for m in sys.argv[1:]]
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

Note: average input tokens grow with conversation history; the 10-exchange average understates a 45-minute conversation. Phase 1 will cap history (summary + last N turns); the cost projection below uses the 10-turn average as a lower bound and 2× as an upper bound.

- [ ] **Step 3: Run 3 candidates**

Run: `cd scripts/spikes && ../../.venv/Scripts/python s3_partner.py <claude-haiku-id> <deepseek-v4-pro-id> <one-gpt-id>` (ids exactly as listed in Step 1)
Expected: 30 printed rows, 3 `==>` summary lines, `data/spikes/s3/results.json`.

- [ ] **Step 4: Learner reads the replies, cost projection**

User reads each model's replies (`raw` column): natural German? B1? flattering? good surprise questions? Rank the 3.

Look up current per-token prices for the 3 models on the gateway's live pricing page (and Azure S0 price if over free tier) — never from memory. Project monthly cost:

```
exchanges_per_month = 2 exchanges/min × 45 min × 30 days = 2700   (assumption; adjust from S4/S1 timing)
llm_cost  = 2700 × (avg_in_tokens × in_price + avg_out_tokens × out_price) / 1e6     (×1 lower, ×2 upper bound)
tts_chars = 2700 × avg_tts_chars   → Azure free up to 500,000 chars/month
```

Record: winner, its JSON-valid rate (must be ≥ 90% or Phase 1 needs a repair/retry step), avg latency, cost range vs €5/month target.

- [ ] **Step 5: Commit**

```bash
bash scripts/lint-arch.sh && git add scripts/spikes/s3_partner.py && git commit -m "spike(s3): partner LLM comparison, latency and cost"
```

---

### Task 6: Write results into the spec, decide Phase 1

**Files:**
- Modify: `docs/exec-plans/active/2026-10-04-conversation-partner-design.md` (add `## Spike results` before `## Testing`; update `## Stack` rows)
- Modify: `docs/exec-plans/active/2026-10-04-conversation-partner-phase0-spikes.md` (`**Status:** done`)

- [ ] **Step 1: Add the results section**

Add to the spec, filled with the measured values from the scratch notes:

```markdown
## Spike results (2026-MM-DD)

| Spike | Result | Decision |
|---|---|---|
| S0 venv | 43 passed / <n> | — |
| S4 audio | headset <name>, keys work in <terminal> | Phase 1 key handling via msvcrt in <terminal> |
| S1 whisper | small kept <n>/10 @ <s>s; medium <n>/10 @ <s>s; +prompt <…> | live STT = <model, prompt?> |
| S2 TTS | winner <engine/voice>; slower natural? <y/n>; Azure bytes+rate <ok?> | TTS = <…>; RealtimeTTS <dropped/kept> |
| S3 LLM | winner <model>, valid <x%>, <s>s, €<lo>–<hi>/month | partner LLM = <…> via <gateway/Anthropic> |
```

Update the spec's `## Stack` table rows (STT live, TTS, LLM) to the decided values.

- [ ] **Step 2: Mark this plan done, commit**

Set `**Status:** done` and `**Last verified:**` to today in this plan.

```bash
bash scripts/lint-arch.sh && git add docs/exec-plans/active/2026-10-04-conversation-partner-design.md docs/exec-plans/active/2026-10-04-conversation-partner-phase0-spikes.md && git commit -m "docs: record phase 0 spike results and decisions"
```

- [ ] **Step 3: Hand off**

Next: write the Phase 1 plan (storage + session loop) from the updated spec with superpowers:writing-plans. Only if every spike passed its decision rule; any failed rule → discuss with the user first.
