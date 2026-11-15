"""Fixture birth checks; real browser/HTTP execution is a separate acceptance run."""
from copy import deepcopy

import pytest

from card_data.seed_cards import SEED_CARD_DATA
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.battle_payment_browser_fixture import midgame, unsupported_midgame
from tests.test_battle_product_acceptance import resolve_until


@pytest.mark.parametrize("seat", [1, 2])
def test_declared_midgame_preserves_stock_and_offers_both_real_spells(seat):
    before = deepcopy(SEED_CARD_DATA)
    state, ids = midgame(seat)
    assert len(state.cards) == 120 and state.winner is None
    assert all(sum(card.owner == player for card in state.cards.values()) == 60 for player in (1, 2))
    assert len(state.players[seat].battlefield) == 9
    assert not state.players[3-seat].battlefield
    assert state.cards[ids["battle"]].printed_defense == "3"
    assert state.cards[ids["battle"]].zone == Zone.HAND
    assert all(state.cards[cid].zone == Zone.HAND for cid in ids["pacts"])
    assert len(set(ids["pacts"])) == 2
    spells = {move["card_id"] for move in RulesEngine().legal_moves(state, seat)
              if move["type"] == "cast_spell"}
    assert {ids["battle"], *ids["pacts"]} <= spells
    assert SEED_CARD_DATA == before


@pytest.mark.parametrize("seat", [1, 2])
def test_declared_midgame_pact_has_a_real_search_and_schedules_its_debt(seat):
    state, ids = midgame(seat)
    rules = RulesEngine()
    state = checked_action(state, rules, seat,
                           {"type": "cast_spell", "card_id": ids["pacts"][0]})
    state = resolve_until(state, lambda s: s.pending_mechanic_choice is not None)
    pending = state.pending_mechanic_choice
    assert pending["kind"] == "search_library" and pending["player_id"] == seat
    chosen = next(cid for cid in pending["options"] if state.cards[cid].name == "Grizzly Bears")
    state = checked_action(state, rules, seat, {"type": "choose_mechanic", "card_ids": [chosen]})
    assert state.cards[chosen].zone == Zone.HAND
    assert len(state.delayed_triggers) == 1
    assert state.delayed_triggers[0]["effect_key"] == "deferred_upkeep_payment"
    assert state.delayed_triggers[0]["payload"]["mana_cost"] == "{2}{G}{G}"


@pytest.mark.parametrize("seat", [1, 2])
def test_explicit_unknown_view_reaches_the_generic_choice_boundary(seat):
    state, _ = unsupported_midgame(seat)
    moves = RulesEngine().legal_moves(state, seat)
    assert len(moves) == 1
    assert moves[0]["type"] == "choose_mechanic"
    assert moves[0]["kind"] == "diagnostic_unknown"
    assert moves[0]["player_id"] == seat
