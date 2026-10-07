"""Audio encoding helpers: in-memory WAV for STT, Opus files for storage."""

from __future__ import annotations

import io
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def wav_bytes(samples: np.ndarray, samplerate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples, samplerate, format="WAV")
    return buffer.getvalue()


def encode_opus(audio: bytes, dest: Path, run: Callable[..., Any] = subprocess.run) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", str(dest)],
        input=audio,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg opus encoding failed: {result.stderr.decode(errors='replace')}")
