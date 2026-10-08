"""Actual paid loyalty state remains immutable during prospective entry queries."""
import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine.entry_counters import prospective_entry_ability_view
import test_brainstorm_desired as brain
from test_emperor_lifecycle_audit import (
    setup, resolve_cast, token_activation, priority, offered, atomic_reject,
)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('restore', [False, True])
def test_paid_used_emperor_prospective_entry_query_preserves_live_once_guard(seat, restore):
    state, source, _ = setup(seat)
    state = resolve_cast(state, seat, source, {'W': 4})
    state = token_activation(state, seat, source)
    state = priority(brain.cold(state) if restore else state, seat)
    assert source in state.loyalty_activated_this_turn
    before = serialize_match_snapshot(state)
    used_record = state.loyalty_activated_this_turn
    result = prospective_entry_ability_view(state, state.cards[source], seat)
    assert 'Planeswalker' in result['types']
    assert serialize_match_snapshot(state) == before
    assert state.loyalty_activated_this_turn is used_record
    assert source in used_record
    assert not offered(state, seat, source)
    atomic_reject(state, seat, source)
