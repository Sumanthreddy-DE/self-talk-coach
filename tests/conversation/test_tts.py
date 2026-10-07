from self_talk_coach.conversation.tts import EdgeVoice


class FakeCommunicate:
    calls: list[tuple[str, str, str]] = []

    def __init__(self, text: str, voice: str, rate: str = "+0%") -> None:
        FakeCommunicate.calls.append((text, voice, rate))

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"ID3a"}
        yield {"type": "audio", "data": b"bc"}


def test_edge_voice_collects_audio_and_sets_rate() -> None:
    FakeCommunicate.calls.clear()
    voice = EdgeVoice("de-DE-SeraphinaMultilingualNeural", communicate=FakeCommunicate)
    assert voice.synthesize("Hallo") == b"ID3abc"
    assert voice.synthesize("Hallo", slower=True) == b"ID3abc"
    assert FakeCommunicate.calls == [
        ("Hallo", "de-DE-SeraphinaMultilingualNeural", "+0%"),
        ("Hallo", "de-DE-SeraphinaMultilingualNeural", "-25%"),
    ]
    assert voice.name == "de-DE-SeraphinaMultilingualNeural"
