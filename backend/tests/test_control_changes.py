from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from effects.registry import resolve_effect
from rules_engine.ability_model import build_ability_spec
from rules_engine.engine import RulesEngine


def _state() -> object:
    state = MatchFactory.from_decks(
        [{"quantity": 60, "card_name": "Forest"}],
        [{"quantity": 60, "card_name": "Forest"}],
        seed=44,
    )
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    return state


def test_temporary_control_change_moves_permanent_and_returns_at_cleanup() -> None:
    state = _state()
    creature = CardInstance("creature", "Bear", 2, 2, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    spell = CardInstance(
        "threaten",
        "Threaten",
        1,
        1,
        Zone.HAND,
        ["Sorcery"],
        mana_cost="{2}{R}",
        oracle_text="Gain control of target creature until end of turn. Untap that creature. It gains haste until end of turn.",
    )
    state.cards[creature.id] = creature
    state.cards[spell.id] = spell
    state.players[2].battlefield.append(creature.id)
    state.players[1].hand.append(spell.id)

    spec = build_ability_spec(state, spell, 1, {"target_card_id": creature.id})
    assert spec.effect.key == "change_control"
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert creature.controller == 1
    assert creature.id in state.players[1].battlefield
    assert creature.id not in state.players[2].battlefield

    state.step = Step.CLEANUP
    RulesEngine()._apply_step_start_actions(state)
    assert creature.controller == 2
    assert creature.id in state.players[2].battlefield


def test_control_change_duration_is_snapshot_safe() -> None:
    state = _state()
    creature = CardInstance("creature", "Bear", 2, 2, Zone.BATTLEFIELD, ["Creature"], type_line="Creature — Bear")
    state.cards[creature.id] = creature
    state.players[2].battlefield.append(creature.id)
    resolve_effect(
        state,
        1,
        "change_control",
        {"target_card_id": creature.id, "new_controller": 1, "until_end_of_turn": True},
    )
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.temporary_control_changes[creature.id]["controller"] == 2
    assert restored.cards[creature.id].controller == 1
