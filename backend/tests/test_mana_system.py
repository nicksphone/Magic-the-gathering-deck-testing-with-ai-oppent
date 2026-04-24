from __future__ import annotations

from game_state.state import Zone
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.mana import can_pay_with_pool_and_lands


def test_can_pay_known_mana_cost_with_untapped_lands() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    # Put a UU spell in hand with known mana cost.
    cid = state.players[1].hand[0]
    state.cards[cid].name = "Counterspell"
    state.cards[cid].types = ["Instant"]
    state.cards[cid].mana_cost = "{U}{U}"

    # Ensure player has at least two islands on battlefield.
    p1 = state.players[1]
    for _ in range(2):
        lid = p1.library.pop()
        p1.battlefield.append(lid)
        state.cards[lid].zone = Zone.BATTLEFIELD
        state.cards[lid].types = ["Land"]
        state.cards[lid].name = "Island"

    assert can_pay_with_pool_and_lands(state, 1, "{U}{U}") is True


def test_cast_spell_rejects_if_cost_unpaid() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1

    cid = state.players[1].hand[0]
    state.cards[cid].name = "Big Spell"
    state.cards[cid].types = ["Sorcery"]
    state.cards[cid].mana_cost = "{5}{U}{U}"

    before_hand = len(state.players[1].hand)
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.players[1].hand) == before_hand
