from self_talk_coach.conversation.report_metrics import (
    answer_pairs,
    freeze_per_question,
    freeze_trend,
    listening_summary,
    missed_rescue,
)


def _p(i, text, ladder=0, replay=0, slower=0, shown=0):
    return {"turn_index": i, "speaker": "partner", "text": text, "freeze_seconds": None,
            "ladder_step_reached": ladder, "replay_count": replay, "slower_count": slower, "show_text_count": shown}


def _l(i, text, freeze):
    return {"turn_index": i, "speaker": "learner", "text": text, "freeze_seconds": freeze,
            "ladder_step_reached": 0, "replay_count": 0, "slower_count": 0, "show_text_count": 0}


TURNS = [
    _p(0, "Wo arbeitest du?", replay=1),
    _l(1, "Bei McDonald's.", 2.0),
    _p(2, "Seit wann?", ladder=2),
    _l(3, "Seit zwei Jahre.", 9.0),
    _p(4, "Und wie ist der Chef?", ladder=3, slower=1, shown=1),
    _l(5, "Kannst du das nochmal sagen?", 13.0),
    _p(6, "Ich frage, wie dein Chef ist."),
]


def test_answer_pairs_and_freeze_per_question() -> None:
    assert [(p["turn_index"], a["turn_index"]) for p, a in answer_pairs(TURNS)] == [(0, 1), (2, 3), (4, 5)]
    assert freeze_per_question(TURNS) == [("Wo arbeitest du?", 2.0), ("Seit wann?", 9.0), ("Und wie ist der Chef?", 13.0)]


def test_freeze_trend_against_previous_medians() -> None:
    previous = [[_l(1, "a", 10.0), _l(3, "b", 12.0)], [_l(1, "c", 14.0)], [_p(0, "nur Partner")]]
    trend = freeze_trend(TURNS, previous)
    assert trend.current == 9.0
    assert trend.previous == 12.5  # median of 11.0 and 14.0; conversation without freezes skipped
    assert trend.compared == 2
    assert trend.delta == -3.5
    assert freeze_trend(TURNS, []).delta is None


def test_listening_summary_counts_aids_and_lists_hard_sentences() -> None:
    summary = listening_summary(TURNS)
    assert summary.partner_turns == 4 and summary.aids == 3 and summary.per_turn == 0.75
    assert summary.hard == ["Wo arbeitest du?", "Und wie ist der Chef?"]


def test_missed_rescue_when_help_came_and_no_rescue_phrase() -> None:
    # turn 5 used a rescue phrase, so only "Seit wann?" (ladder 2, answer turn 3) is a missed chance
    assert missed_rescue(TURNS, rescue_turns={5}) == ["Seit wann?"]
