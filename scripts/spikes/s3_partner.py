"""S3: same 10 learner lines through candidate partner LLMs; measure latency, tokens, JSON validity."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/spikes/s3"

SYSTEM = """Du bist ein Gesprächspartner aus Baden-Württemberg. Du sprichst mit einem Deutschlerner (Niveau B1).
Regeln:
- Kurze Antworten: 1–2 Sätze. Umgangssprachlich, natürlich, Sprachniveau B1.
- Kein Lob, keine Floskeln wie "Super!" oder "Toll gemacht!".
- Wenn der Lerner einen Fehler macht, wiederhole den Satz einmal korrekt im Feld "recast" (ohne Erklärung), sonst null.
- Stelle danach eine Frage zum vorgegebenen Thema, als natürliche Folgefrage oder als plötzlicher Themenwechsel.
- "starter_phrase": ein Satzanfang, mit dem der Lerner antworten könnte.
- "simpler_rephrase": dieselbe Frage einfacher formuliert.
Antworte NUR mit JSON: {"reply": str, "recast": str|null, "starter_phrase": str, "simpler_rephrase": str, "topic_jump": bool}"""

# (learner line as a live transcript might contain it, next topic seed chosen by code)
SCRIPT = [
    ("Hallo, ich heiße Sumanth und ich wohne in Reutlingen.", "Arbeit"),
    ("Ich arbeite bei McDonald's in Mössingen, meistens Spätschicht.", "Spätschicht"),
    ("Gestern ich habe bis Mitternacht gearbeitet.", "Schlaf und Freizeit"),
    ("Am Wochenende ich gehe mit meine Freunde in die Stadt.", "Lieblingsessen"),
    ("Ich koche gern indisches Essen, Biryani zum Beispiel.", "Vorstellungsgespräch: Stärken"),
    ("Meine Stärke ist, ich lerne schnell und ich bin zuverlässig.", "Vorstellungsgespräch: Schwächen"),
    ("Äh... meine Schwäche... ich spreche noch nicht so gut Deutsch.", "Hypothetisch: Lottogewinn"),
    ("Ich würde eine Reise nach Indien machen und meine Familie besuchen.", "Wohnung"),
    ("Meine Wohnung ist klein aber die Miete ist billig.", "Pläne in fünf Jahren"),
    ("In fünf Jahren ich möchte als Ingenieur arbeiten.", "Abschied"),
]

FENCE = re.compile(r"^\s*`{3}(?:json)?\s*|\s*`{3}\s*$")


class PartnerTurn(BaseModel):
    reply: str
    recast: str | None
    starter_phrase: str
    simpler_rephrase: str
    topic_jump: bool


def run_model(client: OpenAI, model: str) -> dict:
    messages = [{"role": "system", "content": SYSTEM}]
    rows = []
    for learner, seed in SCRIPT:
        messages.append({"role": "user", "content": f"Lerner: {learner}\nNächstes Thema: {seed}"})
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.8, max_tokens=400)
        except Exception as exc:  # noqa: BLE001 — spike: record and move on
            print(f"[{model}] API error: {type(exc).__name__}: {str(exc)[:200]}")
            messages.pop()
            continue
        seconds = time.perf_counter() - start
        if not getattr(resp, "choices", None):
            print(f"[{model}] empty response (no choices): {str(resp)[:200]}")
            messages.pop()
            continue
        raw = resp.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": raw})
        try:
            turn = PartnerTurn.model_validate_json(FENCE.sub("", raw))
            valid, spoken = True, f"{turn.recast or ''} {turn.reply}".strip()
        except ValidationError:
            valid, spoken = False, raw
        usage = resp.usage
        rows.append({
            "learner": learner, "seed": seed, "raw": raw, "valid_json": valid, "seconds": round(seconds, 2),
            "in_tokens": usage.prompt_tokens if usage else None,
            "out_tokens": usage.completion_tokens if usage else None,
            "tts_chars": len(spoken),
        })
        print(f"[{model}] {seconds:4.1f}s valid={valid} | {spoken[:140]}")
    n = max(len(rows), 1)
    summary = {
        "model": model,
        "turns": len(rows),
        "valid_rate": sum(r["valid_json"] for r in rows) / n,
        "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "avg_in_tokens": sum(r["in_tokens"] or 0 for r in rows) / n,
        "avg_out_tokens": sum(r["out_tokens"] or 0 for r in rows) / n,
        "avg_tts_chars": sum(r["tts_chars"] for r in rows) / n,
        "rows": rows,
    }
    print(f"==> {model}: {len(rows)} turns, valid {summary['valid_rate']:.0%}, {summary['avg_seconds']}s, "
          f"in {summary['avg_in_tokens']:.0f} / out {summary['avg_out_tokens']:.0f} tok, {summary['avg_tts_chars']:.0f} chars\n")
    return summary


def main() -> None:
    load_dotenv(ROOT / ".env")
    client = OpenAI(base_url=os.environ["GATEWAY_BASE_URL"], api_key=os.environ["GATEWAY_API_KEY"], timeout=60, max_retries=0)
    OUT.mkdir(parents=True, exist_ok=True)
    for m in sys.argv[1:]:
        summary = run_model(client, m)
        (OUT / f"results-{m}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
