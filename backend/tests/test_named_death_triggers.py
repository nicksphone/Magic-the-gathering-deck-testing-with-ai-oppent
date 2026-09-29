"""Printed card names in death triggers are self-references, not card-specific rules."""

import pytest

from effects.handlers import destroy_permanent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _state(*, human=False, shield=False):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=672)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {1} if human else set()
    cards = [
        CardInstance(
            "artist", "Blood Artist", 1, 1, Zone.BATTLEFIELD, ["Creature"],
            power=0, toughness=1,
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.",
        ),
        CardInstance("elf", "Llanowar Elves", 2, 2, Zone.BATTLEFIELD, ["Creature"], power=1, toughness=1,
                     oracle_text="{T}: Add {G}."),
    ]
    if shield:
        cards.append(CardInstance("leyline", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
                                  oracle_text="You have hexproof."))
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    return state


@pytest.mark.parametrize("dead_id", ["artist", "elf"])
def test_named_self_reference_triggers_for_own_or_other_creature_death(dead_id):
    state = _state()
    destroy_permanent(state, 2, {"target_card_id": dead_id})
    assert [item.source_card_id for item in state.stack] == ["artist"]
    assert state.stack[-1].payload["target_player"] == 2
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19


def test_human_chooses_target_for_named_death_trigger_after_snapshot():
    state = _state(human=True)
    destroy_permanent(state, 1, {"target_card_id": "elf"})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.pending_trigger_order["phase"] == "targets"
    rules = RulesEngine()
    moves = rules.legal_moves(state, 1)
    assert {move.get("target_player") for move in moves} == {1, 2}
    assert not rules.legal_moves(state, 2)
    with pytest.raises(ActionRejected):
        checked_action(state, rules, 2, {"type": "choose_trigger_target", "stack_id": state.stack[-1].id,
                                         "target_player": 2})
    state = checked_action(state, rules, 1, {"type": "choose_trigger_target", "stack_id": state.stack[-1].id,
                                            "target_player": 2})
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 21
    assert state.players[2].life == 19


def test_named_death_trigger_respects_player_hexproof_at_target_choice():
    state = _state(human=True, shield=True)
    destroy_permanent(state, 1, {"target_card_id": "elf"})
    assert {move.get("target_player") for move in RulesEngine().legal_moves(state, 1)} == {1}


def test_named_death_trigger_fizzles_entire_drain_if_target_becomes_illegal():
    state = _state(human=True)
    destroy_permanent(state, 1, {"target_card_id": "elf"})
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_player": 2,
    })
    shield = CardInstance("leyline", "Leyline of Sanctity", 2, 2, Zone.BATTLEFIELD, ["Enchantment"],
                          oracle_text="You have hexproof.")
    state.cards[shield.id] = shield
    state.players[2].battlefield.append(shield.id)
    assert resolve_top_of_stack(state)
    assert state.players[1].life == state.players[2].life == 20
    assert any("does not resolve because its target is illegal" in line for line in state.log)
