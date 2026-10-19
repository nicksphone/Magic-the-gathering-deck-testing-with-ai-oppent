"""Absent primitive damage sources have no color, never an attached-card lookup."""
import pytest

from game_state.serializers import serialize_match_snapshot
from rules_engine.colors import card_color_names, card_color_symbols
from tests.test_variable_mana import clean


@pytest.mark.parametrize('with_state', [False, True])
def test_absent_source_color_queries_preserve_empty_result_and_state(with_state):
    state = clean() if with_state else None
    before = serialize_match_snapshot(state) if state is not None else None
    assert card_color_symbols(None, state) == set()
    assert card_color_names(None, state) == set()
    if state is not None:
        assert serialize_match_snapshot(state) == before
