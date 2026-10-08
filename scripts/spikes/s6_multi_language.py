"""S6: Deepgram Nova-3 `language=multi` vs `de` (BACKLOG mixed-language-stt).

Questions: does `multi` write the English parts of mixed speech as English, and does it still
keep learner grammar errors verbatim (ADR 0005)?

Usage: python s6_multi_language.py synth    (Seraphina speaks the MIXED sentences -> data/spikes/s6/synth-*.mp3)
       python s6_multi_language.py record   (learner reads the MIXED sentences -> data/spikes/s6/mixed-*.wav)
       python s6_multi_language.py check    (all sets through de and multi, writes results.json)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from s1_record import SENTENCES
from s1c_control import CORRECT

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data/spikes/s6"

# (sentence as spoken, English words that must come out as English, error substring that must survive)
MIXED: list[tuple[str, list[str], str]] = [
    ("Heute ich habe am Counter gearbeitet und es war really stressful.", ["really", "stressful"], "heute ich habe"),
    ("Mein Schichtleiter war sehr angry, weil ich habe die Order vergessen.", ["angry"], "weil ich habe"),
    ("Wie sagt man refund auf Deutsch?", ["refund"], "wie sagt man"),
    ("Ich habe mit dem Bus gefahrt, but the bus was late.", ["but", "the", "bus", "was", "late"], "gefahrt"),
    ("Der Kunde wollte einen Burger without onions, aber ich habe einen falsche gegeben.", ["without", "onions"], "einen falsche"),
]


def normalize(text: str) -> str:
    return re.sub(r"[^\wäöüß ]", "", text.lower()).strip()


def deepgram(data: bytes, content_type: str, language: str) -> tuple[str, list[str]]:
    resp = requests.post(
        "https://api.deepgram.com/v1/listen",
        params={"model": "nova-3", "language": language, "punctuate": "true", "smart_format": "false", "mip_opt_out": "true"},
        headers={"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}", "Content-Type": content_type},
        data=data,
        timeout=60,
    )
    resp.raise_for_status()
    alt = resp.json()["results"]["channels"][0]["alternatives"][0]
    langs = [f"{w['word']}/{w['language']}" for w in alt.get("words", []) if w.get("language", "de") != "de"]
    return alt["transcript"], langs


def synth() -> None:
    import edge_tts

    DIR.mkdir(parents=True, exist_ok=True)
    for i, (sentence, _, _) in enumerate(MIXED, start=1):
        edge_tts.Communicate(sentence, "de-DE-SeraphinaMultilingualNeural").save_sync(str(DIR / f"synth-{i:02d}.mp3"))
        print(f"synth-{i:02d}.mp3  {sentence}")


def record() -> None:
    from _audio import record_toggle, save_wav

    for i, (sentence, _, _) in enumerate(MIXED, start=1):
        samples = record_toggle(f"[{i}/5] Read exactly, English and mistake included:  {sentence}")
        save_wav(samples, DIR / f"mixed-{i:02d}.wav")


def check() -> None:
    load_dotenv(ROOT / ".env")
    results: dict[str, list[dict]] = {}

    def run(set_name: str, path: Path, content_type: str, spoken: str, markers: list[str], english: list[str]) -> None:
        row: dict = {"file": path.name, "spoken": spoken}
        for lang in ("de", "multi"):
            text, non_de = deepgram(path.read_bytes(), content_type, lang)
            heard = normalize(text)
            row[lang] = {
                "heard": text,
                "kept": all(m in heard for m in markers),
                "english": sum(e in heard.split() for e in english),
                "non_de_words": non_de,
            }
        results.setdefault(set_name, []).append(row)
        de, mu = row["de"], row["multi"]
        same = "SAME" if normalize(de["heard"]) == normalize(mu["heard"]) else "DIFF"
        print(f"[{set_name}] {path.name} {same}\n   de    : {de['heard']}\n   multi : {mu['heard']}  {mu['non_de_words']}")

    s1 = ROOT / "data/spikes/s1"
    for i, (sentence, marker) in enumerate(SENTENCES, start=1):
        run("s1-errors", s1 / f"sentence-{i:02d}.wav", "audio/wav", sentence, [marker], [])
    s1c = ROOT / "data/spikes/s1c"
    for i, sentence in enumerate(CORRECT, start=1):
        run("s1c-correct", s1c / f"correct-{i:02d}.wav", "audio/wav", sentence, [normalize(sentence)], [])
    for prefix, ctype in (("synth", "audio/mpeg"), ("mixed", "audio/wav")):
        for i, (sentence, english, marker) in enumerate(MIXED, start=1):
            path = DIR / f"{prefix}-{i:02d}.{'mp3' if prefix == 'synth' else 'wav'}"
            if path.exists():
                run(f"{prefix}-mixed", path, ctype, sentence, [marker], english)
    for path in sorted((ROOT / "data/conversations").glob("*/turn-*-learner.opus")):
        run("conversations", path, "audio/ogg", "", [], [])

    print("\n==> summary")
    for set_name, rows in results.items():
        for lang in ("de", "multi"):
            kept = sum(r[lang]["kept"] for r in rows)
            eng = sum(r[lang]["english"] for r in rows)
            print(f"{set_name:14} {lang:5} kept {kept}/{len(rows)}  english words {eng}")
        diff = sum(normalize(r["de"]["heard"]) != normalize(r["multi"]["heard"]) for r in rows)
        print(f"{set_name:14} de≠multi on {diff}/{len(rows)}")
    (DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    {"synth": synth, "record": record, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "check"]()
