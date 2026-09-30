"""A surviving spell copy keeps its cast surface after the card changes zones."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from effects.handlers import copy_spell, counter_spell, counter_spell_unless_pay
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


FIXTURES = Path(__file__).parent / "fixtures"
FACES = json.loads((FIXTURES / "modal_spell_faces.json").read_text())
SPLITS = {row["name"]: row for row in json.loads((FIXTURES / "split_cards.json").read_text())}
COUNTERS = {row["name"]: row for row in json.loads((FIXTURES / "copy_counters.json").read_text())}


def surviving_copy(name="Bonecrusher Giant // Stomp", face=1):
    raw = FACES.get(name) or SPLITS[name]
    deck = [{"quantity": 60, "card_name": name, **raw, "oracle_text": raw["card_faces"][0]["oracle_text"]}]
    state = MatchFactory.from_decks(deck, deck, seed=151)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    state.players[1].mana_pool.update({"C": 10, "R": 2, "U": 2, "B": 2})
    card_id = state.players[1].hand[0]
    targets = {"target_player": 2} if name == "Bonecrusher Giant // Stomp" else {}
    if name == "Fire // Ice":
        targets = {"target_distribution": {"2": 2}, "divide_total": 2}
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card_id, "selected_face_index": face, "targets": targets,
    })
    original_id = state.stack[-1].id
    copy_spell(state, 2, {"target_stack_id": original_id})
    copy_id = state.stack[-1].id
    counter_spell(state, 2, {"target_stack_id": original_id})
    assert state.cards[card_id].zone == Zone.GRAVEYARD
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state.priority_player = 1
    return state, card_id, copy_id


def add_counter(state, name):
    raw = COUNTERS[name]
    card = CardInstance("counter", name, 1, 1, Zone.HAND, ["Instant"],
                        mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
                        type_line=raw["type_line"], colors=raw["colors"])
    state.cards[card.id] = card
    state.players[1].hand.append(card.id)
    return card


@pytest.mark.parametrize("name", ["Negate", "Spell Pierce"])
def test_noncreature_counter_can_target_surviving_adventure_copy(name):
    state, source_id, copy_id = surviving_copy()
    card = add_counter(state, name)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == card.id and move["type"] == "cast_spell")
    assert copy_id in {target["id"] for target in move["target_hints"]["stack_targets"]}
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card.id,
        "targets": {"target_stack_id": copy_id, "pay_unless_counter": False},
    })
    assert resolve_top_of_stack(state)
    assert state.stack == [] and state.players[1].life == state.players[2].life == 20
    assert state.cards[source_id].name == "Bonecrusher Giant // Stomp"
    assert state.players[1].graveyard.count(source_id) == 1


@pytest.mark.parametrize("taxed", [False, True])
def test_counter_resolution_checks_copy_type_instead_of_departed_creature(taxed):
    state, source_id, copy_id = surviving_copy()
    handler = counter_spell_unless_pay if taxed else counter_spell
    handler(state, 1, {
        "target_stack_id": copy_id, "target_kind": "noncreature",
        "unless_cost": "{2}", "pay_unless_counter": False,
    })
    assert state.stack == []
    assert state.cards[source_id].zone == Zone.GRAVEYARD


@pytest.mark.parametrize("name,original,face", [
    ("Spell Snare", "Fire // Ice", 0),
    ("Disdainful Stroke", "Valki, God of Lies // Tibalt, Cosmic Impostor", 1),
])
def test_counter_mana_bound_uses_copied_half_value(name, original, face):
    state, _, copy_id = surviving_copy(original, face)
    card = add_counter(state, name)
    move = next(move for move in RulesEngine().legal_moves(state, 1)
                if move.get("card_id") == card.id and move["type"] == "cast_spell")
    assert copy_id in {target["id"] for target in move["target_hints"]["stack_targets"]}
    state = checked_action(state, RulesEngine(), 1, {
        "type": "cast_spell", "card_id": card.id, "cost_choice": {"id": "base"},
        "targets": {"target_stack_id": copy_id},
    })
    assert resolve_top_of_stack(state)
    assert state.stack == [] and state.players[1].life == 20


def test_ai_scores_surviving_planeswalker_copy_as_its_selected_face():
    state, source_id, copy_id = surviving_copy("Valki, God of Lies // Tibalt, Cosmic Impostor", 1)
    assert "Creature" in state.cards[source_id].types and "Planeswalker" not in state.cards[source_id].types
    before = serialize_match_snapshot(state)
    score = AIAgent(difficulty="master", archetype="Control")._stack_item_threat_score(state, copy_id, 1)
    assert score > 10
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize("name,original,face", [
    ("Spell Snare", "Valki, God of Lies // Tibalt, Cosmic Impostor", 1),
    ("Disdainful Stroke", "Fire // Ice", 0),
])
def test_counter_mana_bound_rejects_invalid_copy_without_mutation(name, original, face):
    state, _, copy_id = surviving_copy(original, face)
    card = add_counter(state, name)
    assert not any(move.get("card_id") == card.id for move in RulesEngine().legal_moves(state, 1))
    before = serialize_match_snapshot(state)
    with pytest.raises(ActionRejected):
        checked_action(state, RulesEngine(), 1, {
            "type": "cast_spell", "card_id": card.id, "cost_choice": {"id": "base"},
            "targets": {"target_stack_id": copy_id},
        })
    assert serialize_match_snapshot(state) == before


def test_control_ai_counters_high_threat_copy_after_original_is_gone():
    state, _, copy_id = surviving_copy("Valki, God of Lies // Tibalt, Cosmic Impostor", 1)
    card = add_counter(state, "Negate")
    rules = RulesEngine()
    decision = AIAgent(difficulty="master", archetype="Control").choose_action(state, rules.legal_moves(state, 1), 1)
    assert decision.action["card_id"] == card.id
    assert decision.action["targets"]["target_stack_id"] == copy_id
    state = checked_action(state, rules, 1, decision.action)
    assert resolve_top_of_stack(state)
    assert state.stack == []
