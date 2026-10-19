"""Actual AI decisions at paid copy-entry boundaries, not played-game quality."""
import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_entry_copy_native_936 import cast, position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('difficulty', ['casual', 'strong', 'master'])
@pytest.mark.parametrize('offered', ['none', 'coating', 'coated_aura', 'aura_and_ring'])
def test_actual_ai_optional_entry_choice_can_execute_without_mutating_decision_root(
        seat, difficulty, offered):
    names = ['Sculpting Steel', 'Liquimetal Coating', 'Rancor', 'Grizzly Bears', 'Sol Ring']
    state = position(names, names, seat)
    if offered in {'coated_aura', 'aura_and_ring'}:
        state, creature = cast(state, seat, 'Grizzly Bears')
        assert resolve_top_of_stack(state)
        state, aura = cast(state, seat, 'Rancor', target_card_id=creature)
        assert resolve_top_of_stack(state) and state.cards[aura].attached_to == creature
    if offered != 'none':
        state, coating = cast(state, seat, 'Liquimetal Coating')
        assert resolve_top_of_stack(state)
        if offered in {'coated_aura', 'aura_and_ring'}:
            state = checked_action(state, RulesEngine(), seat, {
                'type': 'activate_ability', 'card_id': coating, 'ability_index': 0,
                'targets': {'target_card_id': aura}})
            assert resolve_top_of_stack(state)
    if offered == 'aura_and_ring':
        state, ring = cast(state, seat, 'Sol Ring')
        assert resolve_top_of_stack(state)
    state, steel = cast(state, seat, 'Sculpting Steel')
    assert not resolve_top_of_stack(state)
    assert state.pending_mechanic_choice['kind'] == 'entry_copy'
    assert state.pending_mechanic_choice['player_id'] == seat
    if offered in {'coated_aura', 'aura_and_ring'}:
        assert aura in state.pending_mechanic_choice['options']
    before = serialize_match_snapshot(state)
    moves = RulesEngine().legal_moves(state, seat)
    decision = AIAgent(archetype='Midrange', difficulty=difficulty).choose_action(state, moves, seat)
    assert serialize_match_snapshot(state) == before
    assert decision.action['type'] == 'choose_mechanic'
    selected = decision.action.get('card_ids')
    assert type(selected) is list and len(selected) <= 1
    assert all(cid in state.pending_mechanic_choice['options'] for cid in selected)
    result = checked_action(state, RulesEngine(), seat, decision.action)
    assert result.cards[steel].zone == Zone.BATTLEFIELD
    assert not result.pending_mechanic_choice and not result.stack
    assert result.cards[steel].owner == seat and result.cards[steel].controller == seat
