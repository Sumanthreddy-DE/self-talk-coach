"""S1 part 1: learner reads 10 sentences that each contain one typical B1 error."""

from __future__ import annotations

from pathlib import Path

from _audio import record_toggle, save_wav

OUT = Path(__file__).resolve().parents[2] / "data/spikes/s1"

# (sentence as spoken, substring that survives only if whisper KEEPS the error)
SENTENCES: list[tuple[str, str]] = [
    ("Ich habe gestern nach Hause gegangen.", "habe gestern nach hause gegangen"),
    ("Gestern ich habe viel gearbeitet.", "gestern ich habe"),
    ("Ich arbeite in die Küche.", "in die küche"),
    ("Ich habe einen Frage.", "einen frage"),
    ("Weil ich habe keine Zeit, ich komme nicht.", "weil ich habe"),
    ("Das ist der Auto von meinem Kollegen.", "der auto"),
    ("Ich bin seit zwei Jahre in Deutschland.", "seit zwei jahre in"),
    ("Ich gehe mit meine Freunde ins Kino.", "mit meine freunde"),
    ("Mein Chef hat gesagt, dass ich muss früher kommen.", "dass ich muss"),
    ("Ich habe mit dem Bus gefahrt.", "gefahrt"),
]


def main() -> None:
    for i, (sentence, _) in enumerate(SENTENCES, start=1):
        samples = record_toggle(f"[{i}/10] Read exactly, mistake included:  {sentence}")
        save_wav(samples, OUT / f"sentence-{i:02d}.wav")


if __name__ == "__main__":
    main()
