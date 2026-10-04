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
