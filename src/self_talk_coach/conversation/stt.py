"""Learner speech-to-text via Deepgram Nova-3 (ADR 0005). Keeps learner errors verbatim."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import requests

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PARAMS: dict[str, str] = {
    "model": "nova-3",
    "language": "de",
    "punctuate": "true",
    "smart_format": "false",
    # Opt out of Deepgram's Model Improvement Program: audio kept only while processing.
    "mip_opt_out": "true",
}


@dataclass(frozen=True)
class Word:
    word: str
    start: float
    end: float
    confidence: float


@dataclass(frozen=True)
class LearnerTranscript:
    text: str
    words: tuple[Word, ...]
    model: str

    def words_json(self) -> str:
        return json.dumps([asdict(w) for w in self.words], ensure_ascii=False)


class LearnerTranscriber(Protocol):
    model_name: str

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript: ...


class DeepgramTranscriber:
    model_name = "deepgram:nova-3:de"

    def __init__(self, api_key: str, post: Callable[..., Any] = requests.post, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._post = post
        self._timeout = timeout

    def transcribe(self, wav_bytes: bytes) -> LearnerTranscript:
        resp = self._post(
            DEEPGRAM_URL,
            params=DEEPGRAM_PARAMS,
            headers={"Authorization": f"Token {self._api_key}", "Content-Type": "audio/wav"},
            data=wav_bytes,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        alt = resp.json()["results"]["channels"][0]["alternatives"][0]
        words = tuple(
            Word(
                word=w.get("punctuated_word") or w["word"],
                start=float(w["start"]),
                end=float(w["end"]),
                confidence=float(w["confidence"]),
            )
            for w in alt.get("words", [])
        )
        return LearnerTranscript(text=alt.get("transcript", ""), words=words, model=self.model_name)
