"""S5: replay real conversation situations through the live partner prompt; print spoken turns for review.

Checks by eye (temperature 0.8, so several runs per scenario):
- phrase seeds: partner never claims the learner said or wanted something absent from the conversation
- recast: the reply after a recast asks something new, it does not echo the recast again
- repeat request: "Wie bitte?" gets the last question again, simpler, not a new topic

Run from repo root: .venv/Scripts/python scripts/spikes/s5_partner_prompt.py [runs]
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from self_talk_coach.conversation.partner import OpenAIChatClient, Partner, build_system_prompt

ROOT = Path(__file__).resolve().parents[2]

DAILY = "Daily Life In Germany"
OFFICE = "Office German"
INTERVIEW = "Interview: Core"

# (name, opening (section, seed), [(learner text, (section, next seed)), ...]) — learner lines from real runs
SCENARIOS = [
    ("phrase-seeds (conversation 5)", (DAILY, "Ich suche diese Adresse."), [
        ("Ich suche Adresse von hier nach die Stuttgart Bad Ganztag. Wie kann ich da gehen?",
         (DAILY, "Ich habe eine Frage zu meiner Anmeldung.")),
        ("Ich weiß es nicht. Ich musste nur da gehen. Ich erinnere nicht, aber ich weiß es nicht, was ich da machen.",
         (DAILY, "Können Sie mir das per E-Mail schicken?")),
    ]),
    ("office phrase seeds", (OFFICE, "Bis wann soll ich das fertig machen?"), [
        ("Ich bin neu hier, ich arbeite seit Montag in diese Firma.", (OFFICE, "Können Sie das bitte noch einmal erklären?")),
    ]),
    ("recast duplicate", (INTERVIEW, "Erzählen Sie mir bitte etwas über sich."), [
        ("Ich habe Maschinenbau studiert und jetzt ich suche eine Arbeit in Deutschland.",
         (INTERVIEW, "Warum möchten Sie in Deutschland arbeiten?")),
    ]),
    ("repeat request", (DAILY, "Ich möchte einen Termin vereinbaren."), [
        ("Wie bitte? Kannst du das nochmal sagen?", (OFFICE, "Was ist heute die wichtigste Aufgabe?")),
    ]),
]


PHRASE_SECTIONS = (DAILY, OFFICE)  # mirrors the STC_PHRASE_SECTIONS default


def _call(fn, *args, section: str):
    # Lets the same script run before and after Partner learned about sections and phrase seeds.
    params = inspect.signature(fn).parameters
    kwargs = {}
    if "section" in params:
        kwargs["section"] = section
    if "phrase" in params:
        kwargs["phrase"] = section in PHRASE_SECTIONS
    return fn(*args, **kwargs)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    profile_path = ROOT / "data/learner-profile.md"
    profile = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else None
    client = OpenAIChatClient(os.environ["GATEWAY_BASE_URL"].strip(), os.environ["GATEWAY_API_KEY"].strip())
    model = os.environ.get("STC_PARTNER_MODEL", "deepseek-v4-pro")
    for name, (open_section, open_seed), exchanges in SCENARIOS:
        for run in range(1, runs + 1):
            print(f"\n=== {name} — run {run}")
            partner = Partner(client, model, model, build_system_prompt(profile))
            reply = _call(partner.opening, open_seed, section=open_section)
            print(f"  [seed {open_seed!r}]\n  P: {reply.turn.spoken_text()}")
            for learner, (section, seed) in exchanges:
                reply = _call(partner.respond, learner, seed, section=section)
                print(f"  L: {learner}\n  [seed {seed!r}]")
                print(f"  P: recast={reply.turn.recast!r}\n     reply={reply.turn.reply!r}")
                print(f"     spoken={reply.turn.spoken_text()!r}")


if __name__ == "__main__":
    main()
