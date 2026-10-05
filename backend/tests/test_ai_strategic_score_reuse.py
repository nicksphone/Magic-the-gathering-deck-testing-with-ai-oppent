"""Reuse the caller's already computed score, without caching mutable states."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from tests.test_ai_pending_deployment import observed
from tests.test_ai_search_prefix import bare_state, actor_correct_reference


def position(seat, counter=False):
    state = bare_state(seat)
    card = deepcopy(next(c for c in observed().cards.values() if c.name == 'Priest of Forgotten Gods'))
    card.id, card.owner, card.controller, card.zone = 'candidate', seat, seat, Zone.HAND
    state.cards[card.id] = card
    state.players[seat].hand.append(card.id)
    state.players[seat].mana_pool.update({'B': 2})
    if counter:
        opponent = 3-seat
        response = CardInstance('counter', 'Counterspell', opponent, opponent, Zone.HAND, ['Instant'],
                                mana_cost='{U}{U}', oracle_text='Counter target spell.')
        state.cards[response.id] = response
        state.players[opponent].hand.append(response.id)
        state.players[opponent].mana_pool.update({'U': 2})
    return state, {'type': 'cast_spell', 'card_id': card.id}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('counter', [False, True])
def test_supplied_baseline_preserves_delta_and_avoids_root_revaluation(seat, counter):
    state, action = position(seat, counter)
    ai = AIAgent(difficulty='master', archetype='Control')
    state = checked_action(state, ai.engine, seat, action)
    before = serialize_match_snapshot(state)
    baseline = ai._strategic_position_score(state, seat)
    reference = ai._stack_two_ply_value(state, seat)
    with patch.object(ai, '_strategic_position_score', wraps=ai._strategic_position_score) as score:
        assert ai._stack_two_ply_value(state, seat, baseline) == pytest.approx(reference)
    assert not any(call.args[0] is state for call in score.call_args_list)
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('depth', [0, 1, 2])
def test_root_and_recursive_callers_supply_scores_with_reference_parity(seat, depth):
    state, action = position(seat, counter=True)
    ai = AIAgent(difficulty='master', archetype='Control')
    before = serialize_match_snapshot(state)
    reference = actor_correct_reference(ai, state, action, seat, depth)
    with patch.object(ai, '_stack_two_ply_value', wraps=ai._stack_two_ply_value) as stack:
        assert ai._strategic_line_score(state, action, seat, depth) == pytest.approx(reference)
    assert stack.call_args_list
    assert all(len(call.args) == 3 for call in stack.call_args_list)
    assert serialize_match_snapshot(state) == before
