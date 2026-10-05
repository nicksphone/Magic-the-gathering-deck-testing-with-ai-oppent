"""Keep reply branches and fallback scores, but skip unused intermediate values."""
from unittest.mock import patch

import pytest

from ai.agent import AIAgent
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from tests.test_ai_strategic_score_reuse import position
from tests.forecast_reference import eager_reference


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reply', ['valid', 'invalid', 'none', 'resolved'])
def test_only_relevant_response_or_fallback_positions_are_scored(seat, reply):
    state, action = position(seat)
    ai = AIAgent(difficulty='master', archetype='Control')
    state = checked_action(state, ai.engine, seat, action)
    if reply == 'resolved':
        ai.engine.take_action(state, seat, {'type': 'pass_priority'}, reject_invalid=True)
    before = serialize_match_snapshot(state)
    calls = []

    def actions(_state, _legal, _actor, limit):
        if limit == 3 or reply in {'valid', 'resolved'}:
            return [{'type': 'pass_priority'}]
        return [] if reply == 'none' else [{'type': 'cast_spell', 'card_id': 'invalid-test-id'}]

    def score(position, _actor):
        calls.append(bool(position.stack))
        return 10.0

    with patch.object(ai, '_strategic_top_actions', side_effect=actions), \
            patch.object(ai, '_strategic_position_score', side_effect=score):
        assert ai._stack_two_ply_value(state, seat, 0.0) == pytest.approx(2.0)
    assert calls == [reply in {'invalid', 'none'}]
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('counter', [False, True])
@pytest.mark.parametrize('style', ['Control', 'Tempo', 'Tribal'])
def test_real_counter_and_pass_forecasts_match_eager_reference(seat, counter, style):
    state, action = position(seat, counter)
    ai = AIAgent(difficulty='master', archetype=style)
    state = checked_action(state, ai.engine, seat, action)
    before = serialize_match_snapshot(state)
    baseline = ai._strategic_position_score(state, seat)
    assert ai._stack_two_ply_value(state, seat, baseline) == pytest.approx(
        eager_reference(ai, state, seat, baseline))
    assert serialize_match_snapshot(state) == before
