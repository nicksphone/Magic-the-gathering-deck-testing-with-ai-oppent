from __future__ import annotations

from game_state.state import MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def test_stack_resolves_after_priority_passes() -> None:
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    cid = state.players[1].hand[0]
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.stack) >= 1
    assert state.priority_player == 1
    engine.take_action(state, 1, {"type": "pass_priority"})
    engine.take_action(state, 2, {"type": "pass_priority"})
    assert len(state.stack) == 0


def test_casting_player_retains_priority_for_additional_spell() -> None:
    deck_a = [
        {"quantity": 30, "card_name": "Lightning Bolt"},
        {"quantity": 30, "card_name": "Mountain"},
    ]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1

    p1 = state.players[1]
    # Deterministically stage resources: two Mountains in play, two Bolts in hand.
    for land_idx in range(2):
        land = next(cid for cid in list(p1.library) if state.cards[cid].name == "Mountain")
        p1.library.remove(land)
        p1.battlefield.append(land)
        state.cards[land].zone = Zone.BATTLEFIELD
        state.cards[land].tapped = False
        state.cards[land].summoning_sick = False

    bolts: list[str] = []
    for _ in range(2):
        bolt = next(cid for cid in list(p1.library) if state.cards[cid].name == "Lightning Bolt")
        p1.library.remove(bolt)
        p1.hand.append(bolt)
        state.cards[bolt].zone = Zone.HAND
        bolts.append(bolt)

    engine.take_action(state, 1, {"type": "cast_spell", "card_id": bolts[0]})
    assert state.priority_player == 1
    assert len(state.stack) == 1

    engine.take_action(state, 1, {"type": "cast_spell", "card_id": bolts[1]})
    assert state.priority_player == 1
    assert len(state.stack) == 2
