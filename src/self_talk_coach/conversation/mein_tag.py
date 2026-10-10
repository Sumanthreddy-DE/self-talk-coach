"""Mein Tag: the learner narrates the day, the partner only asks short follow-up questions."""

from __future__ import annotations

from self_talk_coach.conversation.question_bank import Seed

MEIN_TAG = "Mein Tag"
MEIN_TAG_MAX_RECORD_SECONDS = 180.0  # the learner narrates; one turn may be long
OPENING = Seed(MEIN_TAG, "Wie war dein Tag heute? Erzähl mal.")
FOLLOW_UP = Seed(MEIN_TAG, "Kurze Folgefrage zu dem, was er gerade erzählt hat. Kein neues Thema.")


class MeinTagDeck:
    """Seeds for Mein Tag: one opening, then always a follow-up impulse. No scenarios to switch to."""

    label = MEIN_TAG
    current_option = 0

    def __init__(self) -> None:
        self._opened = False

    def next(self) -> Seed:
        if self._opened:
            return FOLLOW_UP
        self._opened = True
        return OPENING

    def options(self) -> list[str]:
        return [MEIN_TAG]

    def choose(self, option: int) -> str:
        self._opened = False  # the session resets the partner's memory on w/f: open again
        return MEIN_TAG

    def switch(self) -> str:
        return self.choose(0)
