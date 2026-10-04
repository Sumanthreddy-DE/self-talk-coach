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
