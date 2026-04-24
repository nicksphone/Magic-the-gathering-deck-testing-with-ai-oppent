from __future__ import annotations

from effects.handlers import deal_damage
from game_state.state import MatchFactory, Zone


def test_deal_damage_to_creature_reduces_toughness() -> None:
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
    assert creature.toughness == 1
