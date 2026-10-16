"""Sacrifice triggers inspect the battlefield immediately before the sacrifice."""
from tests.rules_printed_facts_e4 import canonical_card, canonical_deck_entry, raw_card, set_printed

import pytest

from effects.handlers import sacrifice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.keyword_actions import finish_mechanic_choice, resolve_annihilator
from rules_engine.stack_engine import resolve_top_of_stack


def _state(*, exile_instead=False, human=False):
    deck = [canonical_deck_entry('Island', 60)]
    state = MatchFactory.from_decks(deck, deck, seed=673)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {1} if human else set()
    cards = [canonical_card("Mayhem Devil", id="devil", owner=1, controller=1, zone=Zone.BATTLEFIELD)]
    if exile_instead:
        cards.append(canonical_card("Rest in Peace", id="rip", owner=2, controller=2, zone=Zone.BATTLEFIELD))
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


@pytest.mark.parametrize("exile_instead", [False, True])
def test_sacrificed_watcher_triggers_from_its_last_battlefield_state(exile_instead):
    state = _state(exile_instead=exile_instead)
    sacrifice(state, 1, {"target_card_id": "devil"})
    assert state.cards["devil"].zone == (Zone.EXILE if exile_instead else Zone.GRAVEYARD)
    assert [item.source_card_id for item in state.stack] == ["devil"]
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 19


def test_human_targets_departed_sacrifice_watcher_after_snapshot():
    state = _state(human=True)
    sacrifice(state, 1, {"target_card_id": "devil"})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.pending_trigger_order["phase"] == "targets"
    rules = RulesEngine()
    assert {move.get("target_player") for move in rules.legal_moves(state, 1)} == {1, 2}
    state = checked_action(state, rules, 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_player": 2,
    })
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 19


def test_simultaneously_sacrificed_watcher_sees_each_annihilator_sacrifice():
    state = _state()
    elf = canonical_card("Llanowar Elves", id="elf", owner=1, controller=1, zone=Zone.BATTLEFIELD)
    state.cards[elf.id] = elf
    state.players[1].battlefield.append(elf.id)
    resolve_annihilator(state, 2, {"target_player": 1, "amount": 2})
    assert finish_mechanic_choice(state, 1, {"card_ids": ["devil", "elf"]})
    assert state.cards["devil"].zone == state.cards["elf"].zone == Zone.GRAVEYARD
    assert [item.source_card_id for item in state.stack] == ["devil", "devil"]
