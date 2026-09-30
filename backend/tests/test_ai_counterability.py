"""AI conserves ineffective counters without denying legal human casts."""
import json
from pathlib import Path

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_counterability_scope import add_card, state_with_card
from tests.test_copy_stack_characteristics import add_counter


def prepare(name="Carnage Tyrant", counter="Counterspell"):
    if name == "Carnage Tyrant":
        raw = json.loads((Path(__file__).parent / "fixtures" / "carnage_tyrant.json").read_text())
        state = MatchFactory.from_decks([{"quantity": 60, "card_name": "Island"}],
                                       [{"quantity": 60, "card_name": name, **raw}], seed=707)
        state.pregame_pending = False
        state.kept_hands = {1, 2}
        state.step = Step.PRECOMBAT_MAIN
        state.priority_player = 1
        source = state.cards[state.players[2].hand.pop()]
        source.zone = Zone.STACK
        state.stack.append(StackItem("target", source.id, 2, name, "noop", {}))
    else:
        state, _ = state_with_card(name)
    card = add_card(state, counter, Zone.HAND, 1) if counter == "Counterspell" else add_counter(state, counter)
    state.players[1].mana_pool.update({"U": 4, "C": 2})
    state.players[1].lands_played_this_turn = 1
    return state, card


@pytest.mark.parametrize("difficulty", ["casual", "strong", "master"])
@pytest.mark.parametrize("archetype", ["Control", "Tempo", "Midrange"])
def test_ai_holds_plain_counter_against_intrinsically_protected_spell(difficulty, archetype):
    state, counter = prepare()
    before = serialize_match_snapshot(state)
    ai = AIAgent(difficulty=difficulty, archetype=archetype)
    for _ in range(3):
        decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
        assert decision.action["type"] == "pass_priority", decision
    assert counter.id in state.players[1].hand
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize("name", ["Counterspell", "Negate", "Spell Pierce"])
def test_ai_holds_counter_against_battlefield_protected_spell(name):
    state, _ = prepare("Cultivate", name)
    add_card(state, "Allosaurus Shepherd", Zone.BATTLEFIELD, 2)
    decision = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["type"] == "pass_priority"


def test_ai_selects_counterable_spell_before_higher_scoring_protected_spell():
    state, counter = prepare()
    bolt = add_card(state, "Lightning Bolt", Zone.STACK, 2)
    state.stack.append(StackItem("bolt", bolt.id, 2, bolt.name, "deal_damage", {"amount": 3, "target_player": 1}))
    ai = AIAgent(archetype="Control", difficulty="master")
    assert ai._stack_item_threat_score(state, "target", 1) > ai._stack_item_threat_score(state, "bolt", 1)
    decision = ai.choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == counter.id
    assert decision.action["targets"]["target_stack_id"] == "bolt"
    state = checked_action(state, RulesEngine(), 1, decision.action)
    assert resolve_top_of_stack(state)
    assert [item.id for item in state.stack] == ["target"]


def test_ai_can_materialize_counter_for_ability_from_spell_protected_source():
    state, _ = state_with_card("Allosaurus Shepherd", Zone.BATTLEFIELD)
    stifle = add_card(state, "Stifle", Zone.HAND, 1)
    state.players[1].mana_pool["U"] = 1
    state.players[1].lands_played_this_turn = 1
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == stifle.id)
    action = AIAgent(archetype="Control")._materialize_action(state, move, 1)
    assert not action.get("_invalid_ai_choice")
    assert action["targets"]["target_stack_id"] == "target"
    state = checked_action(state, RulesEngine(), 1, action)
    assert resolve_top_of_stack(state) and not state.stack


def add_cryptic(state):
    raw = json.loads((Path(__file__).parent / "fixtures" / "cryptic_command.json").read_text())
    cryptic = CardInstance("cryptic", raw["name"], 1, 1, Zone.HAND, ["Instant"],
                           mana_cost=raw["mana_cost"], oracle_text=raw["oracle_text"],
                           type_line=raw["type_line"], colors=raw["colors"])
    state.cards[cryptic.id] = cryptic
    state.players[1].hand.append(cryptic.id)
    state.players[1].mana_pool.update({"U": 3, "C": 1})
    state.players[1].lands_played_this_turn = 1
    return cryptic


def test_ai_uses_useful_cryptic_modes_instead_of_ineffective_counter_mode():
    state, _ = state_with_card("Allosaurus Shepherd")
    cryptic = add_cryptic(state)
    spinner = add_card(state, "Destiny Spinner", Zone.BATTLEFIELD, 2)
    decision = AIAgent(archetype="Control").choose_action(state, RulesEngine().legal_moves(state, 1), 1)
    assert decision.action["card_id"] == cryptic.id
    modes = decision.action["targets"]["mode_texts"]
    assert any("draw" in mode.lower() for mode in modes)
    assert any("return" in mode.lower() for mode in modes)
    assert not any("counter" in mode.lower() for mode in modes)
    hand_size = len(state.players[1].hand)
    state = checked_action(state, RulesEngine(), 1, decision.action)
    assert resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand_size
    assert state.cards[spinner.id].zone == Zone.HAND
    assert [item.id for item in state.stack] == ["target"]


def test_ai_preserves_compound_counter_draw_action_when_secondary_effect_is_useful():
    state, _ = prepare()
    cryptic = add_cryptic(state)
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == cryptic.id)
    modes = [mode for mode in move["target_hints"]["modes"] if "counter" in mode.lower() or "draw" in mode.lower()]
    action = AIAgent(archetype="Control")._materialize_action(state, {**move, "targets": {"mode_texts": modes}}, 1)
    assert not action.get("_invalid_ai_choice")
    hand_size = len(state.players[1].hand)
    state = checked_action(state, RulesEngine(), 1, action)
    assert resolve_top_of_stack(state)
    assert len(state.players[1].hand) == hand_size
    assert [item.id for item in state.stack] == ["target"]


def test_preselected_protected_target_cannot_bypass_ai_plain_counter_guard():
    state, counter = prepare()
    move = next(move for move in RulesEngine().legal_moves(state, 1) if move.get("card_id") == counter.id)
    action = AIAgent()._materialize_action(state, {**move, "targets": {"target_stack_id": "target"}}, 1)
    assert action.get("_invalid_ai_choice")
