from self_talk_coach.conversation.mein_tag import MEIN_TAG, MeinTagDeck


def test_deck_opens_once_then_only_follow_ups() -> None:
    deck = MeinTagDeck()
    first, second, third = deck.next(), deck.next(), deck.next()
    assert first.section == MEIN_TAG and "Tag" in first.text
    assert second == third and "Folgefrage" in second.text
    assert deck.options() == [MEIN_TAG] and deck.label == MEIN_TAG
    assert deck.switch() == MEIN_TAG and deck.choose(0) == MEIN_TAG


def test_switch_reopens_because_the_partner_forgets() -> None:
    deck = MeinTagDeck()
    opening = deck.next()
    deck.next()
    deck.switch()  # session resets the partner's memory on w/f, so the next seed must open again
    assert deck.next() == opening
