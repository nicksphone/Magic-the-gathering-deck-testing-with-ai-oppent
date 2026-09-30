"""Canonical Aftermath halves obey graveyard permission and stack departure."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.handlers import copy_spell, counter_spell
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.colors import card_color_symbols
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import add_to_stack, resolve_top_of_stack
from rules_engine.zone_actions import move_spell_from_stack


CARDS = {row["name"]: row for row in json.loads((Path(__file__).parent / "fixtures/aftermath_cards.json").read_text())}
SPLIT_CARDS = {row["name"]: row for row in json.loads((Path(__file__).parent / "fixtures/split_cards.json").read_text())}


def aftermath_state(name="Spring // Mind", zone=Zone.GRAVEYARD):
    raw = CARDS.get(name) or SPLIT_CARDS[name]
    deck = [{"quantity": 60, "card_name": name, **raw, "oracle_text": raw["card_faces"][0]["oracle_text"]}]
    state = MatchFactory.from_decks(deck, deck, seed=150)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool.update({"C": 4, "U": 2, "G": 1})
    card_id = state.players[1].hand[0]
    if zone != Zone.HAND:
        state.players[1].hand.remove(card_id)
        getattr(state.players[1], zone.value).append(card_id)
        state.cards[card_id].move_to_zone(zone)
    return state, card_id


def cast_mind(state, card_id):
    return checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "from_graveyard": True,
    })


def test_graveyard_offers_only_aftermath_half_at_its_printed_cost():
    state, card_id = aftermath_state()
    moves = [move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == card_id]
    assert [(move["card_name"], move["mana_cost"], move["from_graveyard"]) for move in moves] == [
        ("Mind", "{4}{U}{U}", True),
    ]
    assert moves[0]["cost_options"][0]["id"] == "aftermath"
    state.active_player = 2
    assert any(move.get("card_id") == card_id for move in RulesEngine().legal_moves(state, 1))


@pytest.mark.parametrize("zone", [Zone.HAND, Zone.EXILE])
def test_aftermath_half_rejected_outside_graveyard_without_mutation(zone):
    state, card_id = aftermath_state(zone=zone)
    if zone == Zone.EXILE:
        state.players[1].exile_play_until[card_id] = state.turn
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
            "from_exile": zone == Zone.EXILE,
        })
    assert serialize_match_snapshot(state) == before


def test_aftermath_resolution_draws_then_exiles_after_snapshot_restore():
    state, card_id = aftermath_state()
    hand_before = len(state.players[1].hand)
    state = cast_mind(state, card_id)
    assert state.stack[-1].label == "Mind"
    assert card_color_symbols(state.cards[card_id]) == {"U"}
    assert card_id not in state.players[1].graveyard
    assert state.players[1].mana_pool["C"] == state.players[1].mana_pool["U"] == 0
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand_before + 2
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.cards[card_id].name == "Spring // Mind"
    assert card_color_symbols(state.cards[card_id]) == {"G", "U"}
    assert card_id in state.players[1].exile and card_id not in state.players[1].graveyard
    assert not any(move.get("card_id") == card_id for move in RulesEngine().legal_moves(state, 1))


def test_countered_aftermath_exiles_and_restores_combined_identity():
    state, card_id = aftermath_state()
    state = cast_mind(state, card_id)
    hand_before = len(state.players[1].hand)
    counter_spell(state, 2, {"target_stack_id": state.stack[-1].id})
    assert state.stack == []
    assert len(state.players[1].hand) == hand_before
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.cards[card_id].name == "Spring // Mind"


@pytest.mark.parametrize("destination", [Zone.HAND, Zone.LIBRARY, Zone.GRAVEYARD])
def test_aftermath_replaces_every_requested_stack_destination(destination):
    state, card_id = aftermath_state()
    state = cast_mind(state, card_id)
    item = state.stack.pop()
    item.controller = state.cards[card_id].controller = 2
    assert move_spell_from_stack(state, item, destination) == Zone.EXILE
    assert card_id in state.players[1].exile and card_id not in state.players[2].exile
    assert state.cards[card_id].name == "Spring // Mind"


def test_all_illegal_aftermath_targets_exile_without_creating_a_copy():
    state, card_id = aftermath_state("Refuse // Cooperate")
    shock = CardInstance("target-shock", "Shock", 2, 2, Zone.STACK, ["Instant"],
                         mana_cost="{R}", oracle_text="Shock deals 2 damage to any target.")
    state.cards[shock.id] = shock
    target = add_to_stack(state, shock.id, 2, shock.name, "deal_damage", {"target_player": 1, "amount": 2})
    state.priority_player = 1
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "from_graveyard": True, "targets": {"target_stack_id": target.id},
    })
    counter_spell(state, 1, {"target_stack_id": target.id})
    assert resolve_top_of_stack(state)
    assert state.stack == [] and state.players[1].life == 20
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.cards[card_id].name == "Refuse // Cooperate"


def test_cooperate_retarget_choice_resumes_then_exiles_its_own_card():
    state, card_id = aftermath_state("Refuse // Cooperate")
    state.mechanic_choice_players = {1}
    shock = CardInstance("target-shock", "Shock", 2, 2, Zone.STACK, ["Instant"],
                         mana_cost="{R}", oracle_text="Shock deals 2 damage to any target.")
    state.cards[shock.id] = shock
    target = add_to_stack(state, shock.id, 2, shock.name, "deal_damage", {
        "target_player": 1, "amount": 2, "__announced_targets": {"target_player": 1},
    })
    state.priority_player = 1
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": 1,
        "from_graveyard": True, "targets": {"target_stack_id": target.id},
    })
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["kind"] == "copy_target"
    assert state.cards[card_id].zone == Zone.STACK
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 1, {
        "type": "choose_mechanic", "card_ids": ["target_player:2"],
    })
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.cards[shock.id].zone == Zone.STACK
    assert resolve_top_of_stack(state)
    assert state.players[2].life == 18 and state.players[1].life == 20
    assert resolve_top_of_stack(state)
    assert state.players[1].life == 18


def test_aftermath_insufficient_cost_rejected_without_mutation():
    state, card_id = aftermath_state()
    state.players[1].mana_pool["C"] = 3
    state.players[1].mana_pool["G"] = 0
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        cast_mind(state, card_id)
    assert serialize_match_snapshot(state) == before


def test_sorcery_aftermath_still_requires_own_main_phase_empty_stack():
    state, card_id = aftermath_state("Commit // Memory")
    assert any(move.get("card_id") == card_id for move in RulesEngine().legal_moves(state, 1))
    state.active_player = 2
    assert not any(move.get("card_id") == card_id for move in RulesEngine().legal_moves(state, 1))


def test_aftermath_waits_for_resumed_draw_choices_before_exiling():
    state, card_id = aftermath_state()
    dredger = CardInstance("stinkweed", "Stinkweed Imp", 1, 1, Zone.GRAVEYARD,
                           ["Creature"], oracle_text="Dredge 5")
    state.cards[dredger.id] = dredger
    state.players[1].graveyard.append(dredger.id)
    state = cast_mind(state, card_id)
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice["kind"] == "draw"
    assert state.cards[card_id].zone == Zone.STACK
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "draw"})
    assert state.cards[card_id].zone == Zone.STACK
    state = checked_action(state, RulesEngine(), 1, {"type": "choose_mechanic", "choice_id": "draw"})
    assert state.pending_mechanic_choice is None
    assert state.cards[card_id].zone == Zone.EXILE
    assert state.cards[card_id].name == "Spring // Mind"


def test_copy_of_aftermath_does_not_move_physical_original():
    state, card_id = aftermath_state()
    state = cast_mind(state, card_id)
    hand_before = len(state.players[1].hand)
    copy_spell(state, 2, {"target_stack_id": state.stack[-1].id})
    assert resolve_top_of_stack(state)
    assert state.cards[card_id].zone == Zone.STACK
    assert card_id not in state.players[1].exile
    assert resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand_before + 2
    assert state.cards[card_id].zone == Zone.EXILE


def test_ai_materializes_graveyard_half_using_same_legal_cost():
    state, card_id = aftermath_state()
    rules = RulesEngine()
    move = next(move for move in rules.legal_moves(state, 1) if move.get("card_id") == card_id)
    action = AIAgent(difficulty="master", archetype="Control")._materialize_action(state, move, 1)
    assert action["selected_face_index"] == 1 and action["from_graveyard"]
    state = checked_action(state, rules, 1, action)
    assert state.stack[-1].label == "Mind"


@pytest.mark.parametrize("step,active_player", [(Step.POSTCOMBAT_MAIN, 1), (Step.END_STEP, 2)])
def test_control_ai_uses_available_aftermath_draw_when_hand_is_empty(step, active_player):
    state, card_id = aftermath_state()
    state.players[1].library.extend(state.players[1].hand)
    for cid in state.players[1].hand:
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    state.players[1].hand.clear()
    state.active_player = active_player
    state.step = step
    rules = RulesEngine()
    decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, rules.legal_moves(state, 1), 1)
    assert decision.action["type"] == "cast_spell"
    assert decision.action["card_id"] == card_id and decision.action["selected_face_index"] == 1
    state = checked_action(state, rules, 1, decision.action)
    assert state.stack[-1].label == "Mind"
