"""Irrelevant printed text must not trigger global ability-layer scans."""
from unittest.mock import patch

import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine import replacement
from tests.test_ai_search_prefix import bare_state
from tests.test_ai_recurring_engines import add


@pytest.mark.parametrize('query', ['player_life_total_cant_change', 'player_cant_gain_life', 'player_cant_lose_life'])
def test_irrelevant_canonical_board_does_not_scan_ability_layers_for_life_prohibitions(query):
    state = bare_state(1)
    for index in range(32):
        add(state, 'Torrential Gearhulk', 1 if index % 2 else 2)
    before = serialize_match_snapshot(state)
    with patch('rules_engine.replacement.printed_abilities_suppressed',
               side_effect=AssertionError('Irrelevant printed text should be rejected before layer queries')):
        assert not getattr(replacement, query)(state, 1)
    assert serialize_match_snapshot(state) == before
