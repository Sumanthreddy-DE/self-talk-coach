"""S2b: keyless TTS candidates — edge-tts (Microsoft neural voices, unofficial) and local Piper Thorsten."""

from __future__ import annotations

import asyncio
import time
import wave
from pathlib import Path

import edge_tts
from piper import PiperVoice
from piper.config import SynthesisConfig

from s2_tts import SENTENCES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/spikes/s2"
PIPER_MODEL = ROOT / "models/piper/de_DE-thorsten-high.onnx"
EDGE_VOICES = ["de-DE-KatjaNeural", "de-DE-ConradNeural", "de-DE-SeraphinaMultilingualNeural", "de-DE-FlorianMultilingualNeural"]


async def edge(text: str, voice: str, path: Path, rate: str = "+0%") -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def piper(voice: PiperVoice, text: str, path: Path, length_scale: float = 1.0) -> None:
    with wave.open(str(path), "wb") as wav:
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=length_scale))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for v in EDGE_VOICES:
        start = time.perf_counter()
        for i, s in enumerate(SENTENCES, start=1):
            asyncio.run(edge(s, v, OUT / f"edge-{v}-{i:02d}.mp3"))
        asyncio.run(edge(SENTENCES[1], v, OUT / f"edge-{v}-slower-02.mp3", rate="-25%"))
        print(f"edge {v}: {(time.perf_counter() - start) / 6:.2f}s/sentence")

    voice = PiperVoice.load(str(PIPER_MODEL))
    start = time.perf_counter()
    for i, s in enumerate(SENTENCES, start=1):
        piper(voice, s, OUT / f"piper-thorsten-{i:02d}.wav")
    print(f"piper thorsten: {(time.perf_counter() - start) / 5:.2f}s/sentence")
    piper(voice, SENTENCES[1], OUT / "piper-thorsten-slower-02.wav", length_scale=1.3)
    print(f"Done. Files in {OUT}")


if __name__ == "__main__":
    main()
