"""Ordered source reuse must end before battlefield or layer state changes."""
from unittest.mock import patch

import pytest

from effects.registry import resolve_effect
from game_state.serializers import serialize_match_snapshot
from rules_engine import continuous
from rules_engine.query_context import rule_query_scope, query_cache
from tests.test_ability_suppression import add
from tests.test_ai_recurring_engines import fixture


@pytest.mark.parametrize('seat', [1, 2])
def test_source_activity_is_reused_only_in_one_immutable_scope(seat):
    state = fixture()
    elf = add(state, 'Llanowar Elves', seat)
    loss = add(state, 'Humility', 3-seat)
    original = continuous.printed_abilities_suppressed
    with patch.object(continuous, 'printed_abilities_suppressed', wraps=original) as suppression:
        with rule_query_scope(state):
            first = continuous._continuous_sources(state)
            assert next(active for cid, _, active in first if cid == elf.id) is False
            for _ in range(3):
                assert continuous._continuous_sources(state) == first
            assert suppression.call_count == len(first)
    assert query_cache(state) is None
    resolve_effect(state, seat, 'destroy_permanent', {'target_card_id': loss.id})
    assert next(active for cid, _, active in continuous._continuous_sources(state)
                if cid == elf.id) is True
    assert loss.id not in continuous._all_battlefield_ids(state)


@pytest.mark.parametrize('seat', [1, 2])
def test_order_and_positions_are_fresh_after_reordering_control_and_timestamps(seat):
    state = fixture()
    a = add(state, 'Llanowar Elves', seat)
    b = add(state, 'Royal Assassin', 3-seat)
    with rule_query_scope(state):
        ids = continuous._all_battlefield_ids(state)
        positions = continuous._battlefield_position_map(state)
        ids.clear()
        positions.clear()
        assert continuous._all_battlefield_ids(state)
        assert continuous._battlefield_position_map(state)
    state.players[b.controller].battlefield.remove(b.id)
    b.controller = seat
    state.players[seat].battlefield.insert(0, b.id)
    a.effect_timestamp = continuous.effect_timestamp(b) + 1
    with rule_query_scope(state):
        assert continuous._all_battlefield_ids(state) == continuous._all_battlefield_ids.__wrapped__(state)
        assert continuous._battlefield_position_map(state) == continuous._battlefield_position_map.__wrapped__(state)
        assert continuous._all_battlefield_ids(state).index(b.id) < continuous._all_battlefield_ids(state).index(a.id)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('suppressed', [False, True])
def test_effective_views_match_unshared_source_scan_without_mutation(seat, suppressed):
    state = fixture()
    elf = add(state, 'Llanowar Elves', seat)
    add(state, 'Royal Assassin', 3-seat)
    if suppressed:
        add(state, 'Humility', 3-seat)
    before = serialize_match_snapshot(state)
    def view():
        return (continuous.effective_combat_stats(state, elf.id),
                continuous.effective_keyword_counts(state, elf.id),
                continuous.continuous_layer_trace(state, elf.id))
    cached = view()
    with patch.object(continuous, '_continuous_sources', continuous._continuous_sources.__wrapped__):
        assert view() == cached
    assert serialize_match_snapshot(state) == before
