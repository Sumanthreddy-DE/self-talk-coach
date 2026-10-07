import io
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from self_talk_coach.conversation.audio_store import encode_opus, wav_bytes


def test_wav_bytes_roundtrip() -> None:
    samples = np.zeros(1600, dtype="float32")
    data = wav_bytes(samples)
    decoded, sr = sf.read(io.BytesIO(data))
    assert data[:4] == b"RIFF"
    assert sr == 16000
    assert len(decoded) == 1600


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_encode_opus_writes_file(tmp_path: Path) -> None:
    tone = (0.1 * np.sin(np.linspace(0, 2000, 16000))).astype("float32")
    dest = tmp_path / "sub" / "turn-001.opus"
    encode_opus(wav_bytes(tone), dest)
    assert dest.is_file()
    assert dest.stat().st_size > 100


def test_encode_opus_raises_on_failure(tmp_path: Path) -> None:
    class Failed:
        returncode = 1
        stderr = b"boom"

    with pytest.raises(RuntimeError, match="boom"):
        encode_opus(b"x", tmp_path / "a.opus", run=lambda *a, **k: Failed())
