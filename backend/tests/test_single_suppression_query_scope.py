"""A single immutable query may reuse both empty layer views, then forget them."""
from unittest.mock import patch

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine import basic_land_layer, continuous
from rules_engine.query_context import query_cache
from tests.test_ability_suppression import add
from tests.test_ai_recurring_engines import fixture
from effects.registry import resolve_effect


@pytest.mark.parametrize('seat', [1, 2])
def test_single_suppression_query_reuses_empty_views_without_retaining_state(seat):
    state = fixture()
    elf = add(state, 'Llanowar Elves', seat)
    before = serialize_match_snapshot(state)
    with patch.object(basic_land_layer, '_printed_layer_four_effect',
                      wraps=basic_land_layer._printed_layer_four_effect) as query:
        assert not continuous.printed_abilities_suppressed(state, elf.id)
        assert query.call_count == 1
    assert query_cache(state) is None
    assert serialize_match_snapshot(state) == before
    source = add(state, 'Humility', 3-seat)
    assert continuous.printed_abilities_suppressed(state, elf.id)
    assert query_cache(state) is None
    resolve_effect(state, 3-seat, 'destroy_permanent', {'target_card_id': source.id})
    assert not continuous.printed_abilities_suppressed(state, elf.id)
    assert query_cache(state) is None
