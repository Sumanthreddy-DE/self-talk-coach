"""Partner voice via edge-tts (Microsoft neural voices, unofficial endpoint). Returns MP3 bytes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

import edge_tts


class Voice(Protocol):
    name: str

    def synthesize(self, text: str, slower: bool = False) -> bytes: ...


class EdgeVoice:
    def __init__(
        self,
        voice_name: str,
        slower_rate: str = "-25%",
        communicate: Callable[..., Any] = edge_tts.Communicate,
    ) -> None:
        self.name = voice_name
        self._slower_rate = slower_rate
        self._communicate = communicate

    def synthesize(self, text: str, slower: bool = False) -> bytes:
        rate = self._slower_rate if slower else "+0%"
        return asyncio.run(self._collect(text, rate))

    async def _collect(self, text: str, rate: str) -> bytes:
        chunks: list[bytes] = []
        async for chunk in self._communicate(text, self.name, rate=rate).stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
