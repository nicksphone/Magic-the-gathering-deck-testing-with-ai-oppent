"""Exact transpositions are decision-local, bounded and mutation-sensitive."""
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from ai import pending_effects as projections
from tests.test_ai_strategic_score_reuse import position


@pytest.mark.parametrize('seat', [1, 2])
def test_identical_encoding_reuses_but_gameplay_and_ai_changes_do_not(seat):
    state, _ = position(seat)
    owner = object()
    compute = Mock(return_value=3.0)
    with projections.decision_projection_scope(state, seat):
        assert projections.reuse_position_score(state, seat, owner, compute) == 3.0
        assert projections.reuse_position_score(state, seat, owner, compute) == 3.0
        assert compute.call_count == 1
        # Pickle alias topology may conservatively distinguish equivalent copies.
        assert projections.reuse_position_score(deepcopy(state), seat, owner, compute) == 3.0
        initial_calls = compute.call_count
        for change in ('life', 'mana', 'priority', 'rng', 'opaque'):
            changed = deepcopy(state)
            if change == 'life':
                changed.players[seat].life -= 1
            elif change == 'mana':
                changed.players[seat].mana_pool['B'] += 1
            elif change == 'priority':
                changed.priority_player = 3-seat
            elif change == 'rng':
                changed.rng.random()
            else:
                changed.ai_information_player = 3-seat
            projections.reuse_position_score(changed, seat, owner, compute)
        assert compute.call_count == initial_calls + 5
        projections.reuse_position_score(state, 3-seat, owner, compute)
        projections.reuse_position_score(state, seat, object(), compute)
        assert compute.call_count == initial_calls + 7
    with projections.decision_projection_scope(state, seat):
        projections.reuse_position_score(state, seat, owner, compute)
    assert compute.call_count == initial_calls + 8


@pytest.mark.parametrize('limit', ['POSITION_SCORE_CACHE_BYTES', 'POSITION_SCORE_CACHE_ENTRIES'])
def test_cache_budget_falls_back_without_changing_results(limit):
    state, _ = position(1)
    owner = object()
    compute = Mock(return_value=4.0)
    with patch.object(projections, limit, 0), projections.decision_projection_scope(state, 1):
        assert projections.reuse_position_score(state, 1, owner, compute) == 4.0
        assert projections.reuse_position_score(state, 1, owner, compute) == 4.0
        assert compute.call_count == 2


def test_failed_or_unserializable_queries_are_not_cached():
    state, _ = position(1)
    owner = object()
    compute = Mock(side_effect=[ValueError('failed score'), 2.0])
    with projections.decision_projection_scope(state, 1):
        with pytest.raises(ValueError):
            projections.reuse_position_score(state, 1, owner, compute)
        assert projections.reuse_position_score(state, 1, owner, compute) == 2.0
    state.unsaved_callback = lambda: None
    compute = Mock(return_value=5.0)
    with projections.decision_projection_scope(state, 1):
        assert projections.reuse_position_score(state, 1, owner, compute) == 5.0
        assert projections.reuse_position_score(state, 1, owner, compute) == 5.0
    assert compute.call_count == 2
