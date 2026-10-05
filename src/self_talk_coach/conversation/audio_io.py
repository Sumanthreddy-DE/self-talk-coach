"""Real hardware: Windows console keys, microphone, speakers, wall clock. Not unit-tested."""

from __future__ import annotations

import io
import msvcrt
import queue
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from self_talk_coach.conversation.audio_store import SAMPLE_RATE


class ConsoleKeys:
    def poll(self) -> str | None:
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
        return None

    def flush(self) -> None:
        while msvcrt.kbhit():
            msvcrt.getwch()


class MicRecorder:
    def __init__(self) -> None:
        self._chunks: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._chunks = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=lambda indata, frames, t, status: self._chunks.put(indata.copy()),
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        parts = []
        while not self._chunks.empty():
            parts.append(self._chunks.get())
        return np.concatenate(parts)[:, 0] if parts else np.zeros(0, dtype="float32")


class SpeakerPlayer:
    def play(self, audio: bytes) -> None:
        samples, samplerate = sf.read(io.BytesIO(audio), dtype="float32")
        sd.play(samples, samplerate)
        sd.wait()


class RealClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
