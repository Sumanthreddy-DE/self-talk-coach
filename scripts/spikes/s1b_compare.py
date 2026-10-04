"""S1b: same 10 recordings through more transcribers — local large-v3 and Azure Speech STT (lexical form)."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from s1_record import SENTENCES

DIR = Path(__file__).resolve().parents[2] / "data/spikes/s1"


def normalize(text: str) -> str:
    return re.sub(r"[^\wäöüß ]", "", text.lower()).strip()


def whisper_large(path: Path) -> str:
    from faster_whisper import WhisperModel

    global _large
    if "_large" not in globals():
        _large = WhisperModel("large-v3", device="cpu", compute_type="int8")
    segments, _ = _large.transcribe(str(path), language="de", vad_filter=True)
    return " ".join(s.text.strip() for s in segments)


def azure_stt(path: Path) -> str:
    import azure.cognitiveservices.speech as speechsdk

    cfg = speechsdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
    cfg.speech_recognition_language = "de-DE"
    cfg.output_format = speechsdk.OutputFormat.Detailed
    recognizer = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=speechsdk.audio.AudioConfig(filename=str(path)))
    parts: list[str] = []
    done = threading.Event()

    def on_recognized(evt) -> None:
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            nbest = json.loads(evt.result.json).get("NBest") or [{}]
            parts.append(nbest[0].get("Lexical") or evt.result.text)

    recognizer.recognized.connect(on_recognized)
    recognizer.session_stopped.connect(lambda _evt: done.set())
    recognizer.canceled.connect(lambda _evt: done.set())
    recognizer.start_continuous_recognition()
    done.wait(timeout=60)
    recognizer.stop_continuous_recognition()
    return " ".join(parts)


ENGINES = {"large-v3": whisper_large, "azure": azure_stt}


def main() -> None:
    load_dotenv()
    results = []
    for name in sys.argv[1:]:
        engine = ENGINES[name]
        kept = 0
        rows = []
        for i, (sentence, marker) in enumerate(SENTENCES, start=1):
            start = time.perf_counter()
            text = engine(DIR / f"sentence-{i:02d}.wav")
            seconds = time.perf_counter() - start
            is_kept = marker in normalize(text)
            kept += is_kept
            rows.append({"spoken": sentence, "heard": text, "kept": is_kept, "seconds": round(seconds, 2)})
            print(f"{name:8} {'KEPT ' if is_kept else 'FIXED'} {seconds:5.2f}s | {text}")
        print(f"==> {name}: kept {kept}/10, avg {sum(r['seconds'] for r in rows) / 10:.2f}s/sentence\n")
        results.append({"engine": name, "kept": kept, "rows": rows})
    (DIR / f"results-{'-'.join(sys.argv[1:])}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
