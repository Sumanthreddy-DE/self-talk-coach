"""S2: same German sentences through Azure voices and ElevenLabs; check bytes + rate control."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
import requests
from dotenv import load_dotenv

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s2"
SENTENCES = [
    "Erzählen Sie mir bitte etwas über sich.",
    "Und warum möchtest du gerade bei uns arbeiten?",
    "Ah, du hast gestern bis Mitternacht gearbeitet? Das ist ja echt spät.",
    "Lass dir ruhig Zeit. Wir haben keinen Stress.",
    "Stell dir vor, du gewinnst morgen zehntausend Euro. Was machst du damit?",
]


def azure_config() -> speechsdk.SpeechConfig:
    cfg = speechsdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
    cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm)
    return cfg


def list_azure_german_voices() -> None:
    synth = speechsdk.SpeechSynthesizer(speech_config=azure_config(), audio_config=None)
    result = synth.get_voices_async("de-DE").get()
    for v in result.voices:
        print(v.short_name, v.gender.name)


def azure_tts(text: str, voice: str, rate: str = "0%") -> bytes:
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
        f'<voice name="{voice}"><prosody rate="{rate}">{text}</prosody></voice></speak>'
    )
    synth = speechsdk.SpeechSynthesizer(speech_config=azure_config(), audio_config=None)
    result = synth.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"Azure TTS failed: {result.reason} {result.cancellation_details}")
    return result.audio_data


def elevenlabs_tts(text: str, model_id: str) -> bytes:
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": text, "model_id": model_id, "language_code": "de"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def main() -> None:
    load_dotenv()
    if sys.argv[1:] == ["--list"]:
        list_azure_german_voices()
        return
    voices = sys.argv[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    for voice in voices:
        for i, s in enumerate(SENTENCES, start=1):
            (OUT / f"azure-{voice}-{i:02d}.wav").write_bytes(azure_tts(s, voice))
        (OUT / f"azure-{voice}-slower-02.wav").write_bytes(azure_tts(SENTENCES[1], voice, rate="-25%"))
    if os.environ.get("ELEVENLABS_API_KEY"):
        for model_id in ("eleven_flash_v2_5", "eleven_multilingual_v2"):
            for i, s in enumerate(SENTENCES, start=1):
                (OUT / f"eleven-{model_id}-{i:02d}.mp3").write_bytes(elevenlabs_tts(s, model_id))
    total_chars = sum(len(s) for s in SENTENCES)
    print(f"Done. Files in {OUT}. Characters per engine/voice: {total_chars}")


if __name__ == "__main__":
    main()
