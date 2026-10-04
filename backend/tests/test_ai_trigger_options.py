"""Mandatory target and optional resolution are separate real rules choices."""
import pytest

from ai.agent import AIAgent
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_trigger_target_choices import setup_targeted_sage


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Ramp', 'Aggro', 'Tokens', 'Drain'])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
def test_sage_targets_enemy_artifact_then_accepts_profitable_optional_effect(seat, style, difficulty):
    state, rules, _, own, enemy = setup_targeted_sage(seat=seat)
    state = deserialize_match_snapshot(serialize_match_snapshot(state))
    before = serialize_match_snapshot(state)
    ai = AIAgent(archetype=style, difficulty=difficulty)
    action = ai.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert action['type'] == 'choose_trigger_target' and action['target_card_id'] == enemy.id
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, seat, action)
    assert not resolve_top_of_stack(state)  # Deliberate may-effect resolution window.
    assert state.pending_trigger_order['phase'] == 'optional'
    before = serialize_match_snapshot(state)
    choice = ai.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert choice['type'] == 'choose_optional_effect' and choice['accept']
    assert serialize_match_snapshot(state) == before
    state = checked_action(state, rules, seat, choice)
    assert state.cards[enemy.id].zone == Zone.GRAVEYARD
    assert state.cards[own.id].zone == Zone.BATTLEFIELD


@pytest.mark.parametrize('seat', [1, 2])
def test_sage_can_decline_when_its_only_target_would_destroy_own_mana_engine(seat):
    state, rules, _, own, enemy = setup_targeted_sage(seat=seat)
    state.players[3-seat].battlefield.remove(enemy.id)
    state.players[3-seat].graveyard.append(enemy.id)
    state.cards[enemy.id].move_to_zone(Zone.GRAVEYARD)
    ai = AIAgent(archetype='Ramp', difficulty='master')
    target = ai.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert target['target_card_id'] == own.id
    state = checked_action(state, rules, seat, target)
    assert not resolve_top_of_stack(state)
    choice = ai.choose_action(state, rules.legal_moves(state, seat), seat).action
    assert choice['accept'] is False
    state = checked_action(state, rules, seat, choice)
    assert state.cards[own.id].zone == Zone.BATTLEFIELD and not state.stack
