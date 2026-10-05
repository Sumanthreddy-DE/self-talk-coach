"""S1c: positive control — does the transcriber keep CORRECT speech correct (no invented errors)?

Usage: python s1c_control.py record      (learner reads 5 correct sentences)
       python s1c_control.py check       (Deepgram + whisper medium, exact-match check)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from dotenv import load_dotenv

DIR = Path(__file__).resolve().parents[2] / "data/spikes/s1c"
CORRECT = [
    "Ich bin gestern nach Hause gegangen.",
    "Gestern habe ich viel gearbeitet.",
    "Ich habe eine Frage.",
    "Ich gehe mit meinen Freunden ins Kino.",
    "Ich bin seit zwei Jahren in Deutschland.",
]


def normalize(text: str) -> str:
    return re.sub(r"[^\wäöüß ]", "", text.lower()).split().__str__()


def record() -> None:
    from _audio import record_toggle, save_wav

    for i, sentence in enumerate(CORRECT, start=1):
        samples = record_toggle(f"[{i}/5] Read correctly:  {sentence}")
        save_wav(samples, DIR / f"correct-{i:02d}.wav")


def check() -> None:
    from faster_whisper import WhisperModel

    from s1b_compare import deepgram_stt

    load_dotenv()
    medium = WhisperModel("medium", device="cpu", compute_type="int8")
    for name, engine in [
        ("deepgram", deepgram_stt),
        ("medium", lambda p: " ".join(s.text.strip() for s in medium.transcribe(str(p), language="de", vad_filter=True)[0])),
    ]:
        exact = 0
        for i, sentence in enumerate(CORRECT, start=1):
            heard = engine(DIR / f"correct-{i:02d}.wav")
            ok = normalize(heard) == normalize(sentence)
            exact += ok
            print(f"{name:8} {'SAME ' if ok else 'DIFF '} | {heard}")
        print(f"==> {name}: {exact}/5 written exactly as spoken\n")


if __name__ == "__main__":
    {"record": record, "check": check}[sys.argv[1]]()
