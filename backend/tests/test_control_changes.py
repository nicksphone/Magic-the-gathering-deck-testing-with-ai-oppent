from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchFactory, Step, Zone
from effects.registry import resolve_effect
from effects.handlers import deal_damage, destroy_permanent, return_creature_from_graveyard_to_battlefield
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
    from tests.test_keyword_effect_timestamps import add
    from rules_engine.continuous import has_keyword
    state = _state()
    creature = add(state,player=2)
    creature.tapped = True
    spell = add(state,'Act of Treason',zone=Zone.HAND)

    spec = build_ability_spec(state, spell, 1, {"target_card_id": creature.id})
    assert spec.effect.key == 'effect_sequence'
    assert [effect['effect_key'] for effect in spec.effect.payload['effects']] == ['change_control','untap','grant_keyword']
    resolve_effect(state, 1, spec.effect.key, spec.effect.payload)
    assert creature.controller == 1
    assert creature.id in state.players[1].battlefield
    assert creature.id not in state.players[2].battlefield
    assert not creature.tapped and has_keyword(state,creature.id,'haste')

    state.step = Step.CLEANUP
    RulesEngine()._apply_step_start_actions(state)
    assert creature.controller == 2
    assert creature.id in state.players[2].battlefield
    assert not has_keyword(state,creature.id,'haste')


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


def test_temporary_control_does_not_follow_reanimated_new_permanent() -> None:
    state = _state()
    creature = CardInstance("creature", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD, ["Creature"],
                            type_line="Creature — Bear", power=2, toughness=2)
    state.cards[creature.id] = creature
    state.players[2].battlefield.append(creature.id)
    resolve_effect(state, 1, "change_control", {
        "target_card_id": creature.id, "new_controller": 1, "until_end_of_turn": True,
    })
    assert creature.controller == 1

    destroy_permanent(state, 2, {"target_card_id": creature.id})
    assert creature.zone == Zone.GRAVEYARD
    return_creature_from_graveyard_to_battlefield(state, 1, {"target_card_id": creature.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert state.cards[creature.id].zone == Zone.BATTLEFIELD
    assert state.cards[creature.id].controller == 1

    state.step = Step.CLEANUP
    RulesEngine()._apply_step_start_actions(state)
    assert state.cards[creature.id].controller == 1
    assert creature.id in state.players[1].battlefield


def test_lethal_spell_damage_ends_temporary_control_before_reanimation() -> None:
    state = _state()
    creature = CardInstance("creature", "Grizzly Bears", 2, 2, Zone.BATTLEFIELD, ["Creature"],
                            type_line="Creature — Bear", power=2, toughness=2)
    state.cards[creature.id] = creature
    state.players[2].battlefield.append(creature.id)
    resolve_effect(state, 1, "change_control", {
        "target_card_id": creature.id, "new_controller": 1, "until_end_of_turn": True,
    })
    deal_damage(state, 2, {"target_card_id": creature.id, "amount": 2})
    assert creature.zone == Zone.GRAVEYARD
    assert creature.id not in state.temporary_control_changes

    return_creature_from_graveyard_to_battlefield(state, 1, {"target_card_id": creature.id})
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    state.step = Step.CLEANUP
    RulesEngine()._apply_step_start_actions(state)
    assert state.cards[creature.id].controller == 1
