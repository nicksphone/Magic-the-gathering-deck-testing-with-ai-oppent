from __future__ import annotations

from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


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


def test_stack_resolution_puts_instant_into_owners_graveyard() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    spell_id = "spell-owner-test"
    state.cards[spell_id] = CardInstance(
        id=spell_id,
        name="Borrowed Bolt",
        owner=2,
        controller=1,
        zone=Zone.STACK,
        types=["Instant"],
        oracle_text="Deal 3 damage to any target.",
    )
    state.stack.append(
        type("S", (), {"id": "stack-1", "source_card_id": spell_id, "controller": 1, "label": "Borrowed Bolt", "effect_key": "deal_damage", "payload": {"target_player": 2, "amount": 3}})()
    )

    resolve_top_of_stack(state)

    assert spell_id in state.players[2].graveyard
    assert spell_id not in state.players[1].graveyard
    assert state.cards[spell_id].zone == Zone.GRAVEYARD
