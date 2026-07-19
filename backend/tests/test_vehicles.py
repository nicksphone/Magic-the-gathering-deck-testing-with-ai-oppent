from ai.agent import AIAgent
from game_state.state import CardInstance, MatchFactory, Step, Zone
from rules_engine.engine import RulesEngine


def _vehicle_state():
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=51,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    vehicle = CardInstance("vehicle", "Test Chariot", 1, 1, Zone.BATTLEFIELD, ["Artifact"], oracle_text="Crew 2", type_line="Artifact — Vehicle", power=4, toughness=4)
    creature = CardInstance("crew", "Bear", 1, 1, Zone.BATTLEFIELD, ["Creature"], power=2, toughness=2, summoning_sick=False)
    state.cards.update({vehicle.id: vehicle, creature.id: creature})
    state.players[1].battlefield.extend([vehicle.id, creature.id])
    return state


def test_crew_turns_vehicle_into_tapped_creature_until_cleanup() -> None:
    state = _vehicle_state()
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "crew", "card_id": "vehicle", "crew_card_ids": ["crew"]})
    assert "Creature" in state.cards["vehicle"].types
    assert state.cards["crew"].tapped is True
    engine.next_step(state)
    assert "Creature" in state.cards["vehicle"].types
    state.step = Step.END_STEP
    engine.next_step(state)
    assert "Creature" not in state.cards["vehicle"].types


def test_ai_materializes_legal_crew_selection() -> None:
    state = _vehicle_state()
    move = {
        "type": "crew",
        "card_id": "vehicle",
        "crew_value": 2,
        "crew_candidates": [{"id": "crew", "name": "Bear", "power": 2}],
    }
    action = AIAgent(difficulty="master", archetype="Midrange")._materialize_action(state, move, 1)
    assert action["crew_card_ids"] == ["crew"]
