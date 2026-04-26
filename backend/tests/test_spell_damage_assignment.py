from __future__ import annotations

from effects.handlers import deal_damage, prevent_damage
from game_state.state import MatchFactory, Zone


def test_deal_damage_to_creature_marks_damage_not_toughness() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)

    # Put a creature on battlefield for player 2.
    p2 = state.players[2]
    cid = p2.hand[0]
    p2.hand.remove(cid)
    p2.battlefield.append(cid)
    creature = state.cards[cid]
    creature.zone = Zone.BATTLEFIELD
    creature.types = ["Creature"]
    creature.power = 2
    creature.toughness = 3

    deal_damage(state, 1, {"target_card_id": cid, "amount": 2})
    assert creature.toughness == 3
    assert int(creature.counters.get("__damage_marked", 0)) == 2


def test_prevent_damage_shield_reduces_player_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    life_before = state.players[2].life

    prevent_damage(state, 1, {"target_player": 2, "amount": 2})
    deal_damage(state, 1, {"target_player": 2, "amount": 3})

    assert state.players[2].life == life_before - 1


def test_prevent_damage_shield_reduces_creature_damage() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    p2 = state.players[2]
    cid = p2.hand[0]
    p2.hand.remove(cid)
    p2.battlefield.append(cid)
    creature = state.cards[cid]
    creature.zone = Zone.BATTLEFIELD
    creature.types = ["Creature"]
    creature.power = 2
    creature.toughness = 3

    prevent_damage(state, 1, {"target_card_id": cid, "amount": 2})
    deal_damage(state, 1, {"target_card_id": cid, "amount": 3})
    assert int(creature.counters.get("__damage_marked", 0)) == 1
