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
