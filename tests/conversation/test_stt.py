import json

from self_talk_coach.conversation.stt import DEEPGRAM_PARAMS, DeepgramTranscriber

RESPONSE = {
    "results": {"channels": [{"alternatives": [{
        "transcript": "Ich habe einen Frage.",
        "words": [
            {"word": "ich", "punctuated_word": "Ich", "start": 0.1, "end": 0.3, "confidence": 0.99},
            {"word": "habe", "start": 0.3, "end": 0.5, "confidence": 0.98},
            {"word": "einen", "start": 0.5, "end": 0.8, "confidence": 0.91},
            {"word": "frage", "punctuated_word": "Frage.", "start": 0.8, "end": 1.2, "confidence": 0.97},
        ],
    }]}]}
}


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return RESPONSE


def test_deepgram_request_and_parse() -> None:
    seen = {}

    def fake_post(url, params, headers, data, timeout):
        seen.update(url=url, params=params, headers=headers, data=data, timeout=timeout)
        return FakeResponse()

    stt = DeepgramTranscriber("KEY", post=fake_post)
    result = stt.transcribe(b"RIFFfake")

    assert seen["url"] == "https://api.deepgram.com/v1/listen"
    assert seen["params"] == DEEPGRAM_PARAMS
    assert DEEPGRAM_PARAMS["mip_opt_out"] == "true"
    assert DEEPGRAM_PARAMS["smart_format"] == "false"
    assert seen["headers"]["Authorization"] == "Token KEY"
    assert seen["data"] == b"RIFFfake"
    assert result.text == "Ich habe einen Frage."
    assert [w.word for w in result.words] == ["Ich", "habe", "einen", "Frage."]
    assert result.model == "deepgram:nova-3:de"
    assert json.loads(result.words_json())[2] == {"word": "einen", "start": 0.5, "end": 0.8, "confidence": 0.91}
