"""Canonical Vehicle crew fixtures and response-window regressions."""
import json
from pathlib import Path

from ai.agent import AIAgent
from effects.handlers import change_control, counter_ability
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, StackItem, Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack


CARDS = json.loads((Path(__file__).parent / "fixtures/permanent_spell_context.json").read_text())


def _vehicle_state():
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=51,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = state.priority_player = 1
    for cid, name in (("vehicle", "Smuggler's Copter"), ("crew", "Soul Warden")):
        row = CARDS[name]
        card = CardInstance(
            id=cid, name=name, owner=1, controller=1, zone=Zone.BATTLEFIELD,
            types=row["type_line"].split(" — ")[0].split(),
            type_line=row["type_line"], oracle_text=row["oracle_text"],
            mana_cost=row["mana_cost"], power=int(row["power"]),
            toughness=int(row["toughness"]), summoning_sick=True,
        )
        state.cards[cid] = card
        state.players[1].battlefield.append(cid)
    return state


def _crew(state):
    return checked_action(state, RulesEngine(), 1, {
        "type": "crew", "card_id": "vehicle", "crew_card_ids": ["crew"],
    })


def test_crew_pays_tap_cost_now_and_uses_response_stack_until_cleanup() -> None:
    state = _crew(_vehicle_state())
    vehicle = state.cards["vehicle"]
    assert state.cards["crew"].tapped is True
    assert "Creature" not in vehicle.types
    assert len(state.stack) == 1 and state.stack[-1].effect_key == "crew_vehicle"
    assert state.priority_player == 1
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    resolve_top_of_stack(state)
    assert "Creature" in state.cards["vehicle"].types
    assert state.cards["vehicle"].tapped is False
    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    assert "Creature" not in state.cards["vehicle"].types


def test_countered_crew_keeps_cost_paid_and_vehicle_noncreature() -> None:
    state = _crew(_vehicle_state())
    counter_ability(state, 2, {"target_stack_id": state.stack[-1].id})
    assert not state.stack
    assert state.cards["crew"].tapped is True
    assert "Creature" not in state.cards["vehicle"].types


def test_crew_resolution_does_not_recheck_tapped_creature_power() -> None:
    state = _crew(_vehicle_state())
    state.players[1].battlefield.remove("crew")
    state.players[1].graveyard.append("crew")
    state.cards["crew"].zone = Zone.GRAVEYARD
    resolve_top_of_stack(state)
    assert "Creature" in state.cards["vehicle"].types


def test_crew_does_not_animate_vehicle_after_it_leaves_or_returns() -> None:
    state = _crew(_vehicle_state())
    state.players[1].battlefield.remove("vehicle")
    state.players[1].graveyard.append("vehicle")
    state.cards["vehicle"].zone = Zone.GRAVEYARD
    resolve_top_of_stack(state)
    assert "Creature" not in state.cards["vehicle"].types

    state = _crew(_vehicle_state())
    state.players[1].battlefield.remove("vehicle")
    state.players[1].battlefield.append("vehicle")
    assign_static_order_on_battlefield_entry(state, "vehicle")
    resolve_top_of_stack(state)
    assert "Creature" not in state.cards["vehicle"].types


def test_crew_resolution_follows_vehicle_after_control_change() -> None:
    state = _crew(_vehicle_state())
    change_control(state, 2, {"target_card_id": "vehicle", "new_controller": 2})
    resolve_top_of_stack(state)
    assert state.cards["vehicle"].controller == 2
    assert "Creature" in state.cards["vehicle"].types


def test_crew_resolution_grants_artifact_creature_to_same_permanent() -> None:
    state = _crew(_vehicle_state())
    state.cards["vehicle"].types = ["Enchantment"]
    resolve_top_of_stack(state)
    assert {"Artifact", "Creature"}.issubset(state.cards["vehicle"].types)
    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    assert state.cards["vehicle"].types == ["Enchantment"]


def test_already_creature_vehicle_can_be_crewed_again() -> None:
    state = _vehicle_state()
    state.cards["vehicle"].types.append("Creature")
    assert any(move["type"] == "crew" for move in RulesEngine().legal_moves(state, 1))
    state = _crew(state)
    resolve_top_of_stack(state)
    state.step = Step.END_STEP
    RulesEngine().next_step(state)
    assert "Creature" in state.cards["vehicle"].types


def test_ai_materializes_legal_crew_selection() -> None:
    state = _vehicle_state()
    move = {
        "type": "crew", "card_id": "vehicle", "crew_value": 1,
        "crew_candidates": [{"id": "crew", "name": "Soul Warden", "power": 1}],
    }
    action = AIAgent(difficulty="master", archetype="Midrange")._materialize_action(state, move, 1)
    assert action["crew_card_ids"] == ["crew"]


def test_ai_does_not_waste_crew_on_animated_or_pending_vehicle() -> None:
    agent = AIAgent(difficulty="master", archetype="Midrange")
    rules = RulesEngine()
    state = _vehicle_state()
    state.players[1].hand = []
    state.cards["vehicle"].types.append("Creature")
    assert agent.choose_action(state, rules.legal_moves(state, 1), 1).action["type"] != "crew"

    state = _vehicle_state()
    state.players[1].hand = []
    state.stack.append(StackItem("pending-crew", "vehicle", 1, "Smuggler's Copter crew", "crew_vehicle", {"card_id": "vehicle"}))
    assert agent.choose_action(state, rules.legal_moves(state, 1), 1).action["type"] != "crew"
