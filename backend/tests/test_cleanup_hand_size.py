from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_cleanup_discards_down_to_seven_by_default() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = RulesEngine()

    player = state.players[1]
    while len(player.hand) < 9 and player.library:
        cid = player.library.pop()
        player.hand.append(cid)
        state.cards[cid].zone = Zone.HAND

    state.active_player = 1
    state.priority_player = 1
    state.step = Step.END_STEP

    engine.next_step(state)  # enter cleanup

    assert state.step == Step.CLEANUP
    assert len(player.hand) == 7
    assert len(player.graveyard) == 2


def test_cleanup_keeps_over_seven_with_no_max_hand_size_effect() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = RulesEngine()

    player = state.players[1]
    while len(player.hand) < 9 and player.library:
        cid = player.library.pop()
        player.hand.append(cid)
        state.cards[cid].zone = Zone.HAND

    effect_card = player.hand.pop()
    player.battlefield.append(effect_card)
    state.cards[effect_card].zone = Zone.BATTLEFIELD
    state.cards[effect_card].types = ["Artifact"]
    state.cards[effect_card].oracle_text = "You have no maximum hand size."

    state.active_player = 1
    state.priority_player = 1
    state.step = Step.END_STEP

    engine.next_step(state)  # enter cleanup

    assert state.step == Step.CLEANUP
    assert len(player.hand) == 8
