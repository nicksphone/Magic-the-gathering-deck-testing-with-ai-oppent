"""Read retained actor-owned continuation, never public move body metadata."""
from copy import deepcopy

import pytest

from ai.agent import AIAgent
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine
from tests.test_ai_resource_forecast import position


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_actual_private_continuation_is_used_without_public_body_or_mutation(seat, restore):
    state = position(seat, board_lands=2)
    if restore:
        state = deserialize_match_snapshot(serialize_match_snapshot(state))
    moves = RulesEngine().legal_moves(state, seat)
    assert 'followup_effect' not in moves[0]
    assert state.pending_mechanic_choice['followup_effect']['effect_key'] == 'draw_cards'
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Ramp').choose_action(state, moves, seat)
    assert len(decision.action['card_ids']) == 2
    assert serialize_match_snapshot(state) == before
    assert 'followup_effect' not in RulesEngine().legal_moves(state, seat)[0]


@pytest.mark.parametrize('seat', [1, 2])
def test_injected_move_body_cannot_override_actual_retained_draw(seat):
    state = position(seat, board_lands=2)
    moves = deepcopy(RulesEngine().legal_moves(state, seat))
    moves[0]['followup_effect'] = {'effect_key': 'unsupported-private-body'}
    decision = AIAgent(archetype='Ramp').choose_action(state, moves, seat)
    assert len(decision.action['card_ids']) == 2


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_retained_continuation_cannot_be_invented_from_move(seat):
    state = position(seat, board_lands=2)
    moves = deepcopy(RulesEngine().legal_moves(state, seat))
    moves[0]['followup_effect'] = state.pending_mechanic_choice.pop('followup_effect')
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Ramp').choose_action(state, moves, seat)
    assert decision.action['card_ids'] == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mismatch', ['actor', 'kind', 'options', 'count', 'actor_bool', 'min_bool', 'move_actor'])
def test_unrelated_pending_cannot_supply_a_discard_continuation(seat, mismatch):
    state = position(seat, board_lands=2)
    moves = RulesEngine().legal_moves(state, seat)
    if mismatch == 'actor':
        state.pending_mechanic_choice['player_id'] = 3 - seat
    elif mismatch == 'kind':
        state.pending_mechanic_choice['kind'] = 'unrelated-choice'
    elif mismatch == 'options':
        state.pending_mechanic_choice['options'] = state.pending_mechanic_choice['options'][:1]
    elif mismatch == 'count':
        state.pending_mechanic_choice['count'] += 1
    elif mismatch == 'actor_bool':
        state.pending_mechanic_choice['player_id'] = True
    elif mismatch == 'min_bool':
        state.pending_mechanic_choice['min_count'] = False
    elif mismatch == 'move_actor':
        moves[0]['player_id'] = 3 - seat
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Ramp').choose_action(state, moves, seat)
    assert decision.action['card_ids'] == []
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_other_actor_has_no_choice_or_private_continuation(seat):
    state = position(seat, board_lands=2)
    wrong_moves = RulesEngine().legal_moves(state, 3 - seat)
    assert wrong_moves == []
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Ramp').choose_action(state, wrong_moves, 3 - seat)
    assert decision.action == {'type': 'pass_priority'}
    assert serialize_match_snapshot(state) == before


def test_boolean_caller_is_not_the_integer_pending_actor():
    state = position(1, board_lands=2)
    moves = RulesEngine().legal_moves(state, 1)
    before = serialize_match_snapshot(state)
    decision = AIAgent(archetype='Ramp').choose_action(state, moves, True)
    assert decision.action['card_ids'] == []
    assert serialize_match_snapshot(state) == before
