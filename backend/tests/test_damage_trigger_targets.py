"""Targeted damage triggers choose a legal recipient when put on the stack."""

import pytest
from pydantic import ValidationError

from api_contracts import TriggerTargetChoice
from effects.handlers import sacrifice
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


def _game(*, human=True):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=603)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.trigger_order_choice_required = human
    state.trigger_order_choice_players = {1} if human else set()
    cards = [
        CardInstance(
            "devil", "Mayhem Devil", 1, 1, Zone.BATTLEFIELD, ["Creature"],
            type_line="Creature — Devil", power=3, toughness=3,
            oracle_text="Whenever a player sacrifices a permanent, this creature deals 1 damage to any target.",
        ),
        CardInstance("chalice", "Everflowing Chalice", 1, 1, Zone.BATTLEFIELD, ["Artifact"]),
        CardInstance(
            "elf", "Llanowar Elves", 2, 2, Zone.BATTLEFIELD, ["Creature"],
            type_line="Creature — Elf Druid", power=1, toughness=1, oracle_text="{T}: Add {G}.",
        ),
    ]
    for card in cards:
        state.cards[card.id] = card
        state.players[card.controller].battlefield.append(card.id)
    sacrifice(state, 1, {"target_card_id": "chalice"})
    return state


def test_human_mayhem_devil_can_target_creature_after_snapshot():
    state = deserialize_match_snapshot(serialize_match_snapshot(_game()))
    assert state.pending_trigger_order["phase"] == "targets"
    rules = RulesEngine()
    moves = rules.legal_moves(state, 1)
    assert {m.get("target_player") for m in moves if "target_player" in m} == {1, 2}
    assert "elf" in {m.get("target_card_id") for m in moves}
    assert not rules.legal_moves(state, 2)

    action = {"type": "choose_trigger_target", "stack_id": moves[0]["stack_id"], "target_card_id": "elf"}
    state = checked_action(state, rules, 1, action)
    assert state.pending_trigger_order is None
    assert state.stack[-1].payload.get("target_player") is None
    assert state.stack[-1].payload["target_card_id"] == "elf"
    assert resolve_top_of_stack(state)
    assert state.cards["elf"].zone == Zone.GRAVEYARD
    assert state.players[2].life == 20


def test_human_mayhem_devil_can_target_a_player_and_reject_bad_choice():
    state = _game()
    rules = RulesEngine()
    before = serialize_match_snapshot(state)
    stack_id = state.stack[-1].id
    with pytest.raises(ActionRejected):
        checked_action(state, rules, 2, {"type": "choose_trigger_target", "stack_id": stack_id, "target_player": 2})
    with pytest.raises(ActionRejected):
        checked_action(state, rules, 1, {"type": "choose_trigger_target", "stack_id": stack_id, "target_card_id": "chalice"})
    assert serialize_match_snapshot(state) == before

    state = checked_action(state, rules, 1, {"type": "choose_trigger_target", "stack_id": stack_id, "target_player": 1})
    assert state.stack[-1].payload["target_player"] == 1
    assert state.stack[-1].payload.get("target_card_id") is None
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 19
    assert state.players[2].life == 20


def test_human_mayhem_devil_can_target_planeswalker_loyalty():
    state = _game()
    walker = CardInstance(
        "teferi", "Teferi, Hero of Dominaria", 2, 2, Zone.BATTLEFIELD,
        ["Planeswalker"], loyalty=4,
    )
    state.cards[walker.id] = walker
    state.players[2].battlefield.append(walker.id)
    rules = RulesEngine()
    assert "teferi" in {move.get("target_card_id") for move in rules.legal_moves(state, 1)}
    state = checked_action(state, rules, 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_card_id": walker.id,
    })
    assert resolve_top_of_stack(state)
    assert state.cards[walker.id].loyalty == 3
    assert state.players[2].life == 20


def test_trigger_fizzles_if_creature_target_leaves_before_resolution():
    state = _game()
    rules = RulesEngine()
    state = checked_action(state, rules, 1, {
        "type": "choose_trigger_target", "stack_id": state.stack[-1].id, "target_card_id": "elf",
    })
    state.players[2].battlefield.remove("elf")
    state.players[2].graveyard.append("elf")
    state.cards["elf"].zone = Zone.GRAVEYARD
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 20
    assert any("does not resolve" in line for line in state.log)


def test_unattended_damage_trigger_has_one_legal_target_and_no_pause():
    state = _game(human=False)
    assert state.pending_trigger_order is None
    assert len(state.stack) == 1
    payload = state.stack[-1].payload
    assert payload.get("__trigger_target_choice") is True
    assert (payload.get("target_player") in {1, 2}) != (payload.get("target_card_id") in {"elf", "devil"})


def test_trigger_target_request_requires_exactly_one_recipient():
    for target in ({}, {"target_player": 1, "target_card_id": "elf"}, {"target_player": 3}):
        with pytest.raises(ValidationError):
            TriggerTargetChoice.model_validate({"type": "choose_trigger_target", "stack_id": "trigger", **target})
    assert TriggerTargetChoice.model_validate({"type": "choose_trigger_target", "stack_id": "trigger", "target_player": 2}).target_player == 2
