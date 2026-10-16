"""Sacrificing for an activated cost has the same departure events as other sacrifices."""
from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry, raw_card, set_printed

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _game(*, exile_instead=False):
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=671)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    cards = [
        canonical_card("Fanatical Firebrand", id="firebrand", owner=1, controller=1, zone=Zone.BATTLEFIELD, summoning_sick=False),
        canonical_card("Bastion of Remembrance", id="bastion", owner=1, controller=1, zone=Zone.BATTLEFIELD),
        canonical_card("Mayhem Devil", id="devil", owner=1, controller=1, zone=Zone.BATTLEFIELD),
    ]
    if exile_instead:
        cards.append(canonical_card("Rest in Peace", id="rip", owner=2, controller=2, zone=Zone.BATTLEFIELD))
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


@pytest.mark.parametrize("exile_instead", [False, True])
def test_self_sacrifice_cost_stages_sacrifice_and_only_actual_death_triggers(exile_instead):
    state = _game(exile_instead=exile_instead)
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": "firebrand", "ability_index": 0,
        "targets": {"target_player": 2},
    }, reject_invalid=True)
    assert state.cards["firebrand"].zone == (Zone.EXILE if exile_instead else Zone.GRAVEYARD)
    assert [item.source_card_id for item in state.stack].count("firebrand") == 1
    assert [item.source_card_id for item in state.stack].count("devil") == 1
    assert [item.source_card_id for item in state.stack].count("bastion") == (0 if exile_instead else 1)
    assert state.stack[0].source_card_id == "firebrand"
    assert all(item.source_card_id != "firebrand" for item in state.stack[1:])
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    while state.stack:
        assert resolve_top_of_stack(state)
    assert state.players[1].life == (20 if exile_instead else 21)
    assert state.players[2].life == (18 if exile_instead else 17)


def test_human_orders_death_and_sacrifice_cost_triggers_above_ability():
    state = _game()
    state.trigger_order_choice_required = True
    state.trigger_order_choice_players = {1}
    RulesEngine().take_action(state, 1, {
        "type": "activate_ability", "card_id": "firebrand", "ability_index": 0,
        "targets": {"target_player": 2},
    }, reject_invalid=True)
    pending = state.pending_trigger_order
    assert pending is not None
    assert {item["source_card_id"] for item in pending["groups"]["1"]} == {"bastion", "devil"}
    assert [item.source_card_id for item in state.stack] == ["firebrand"]
