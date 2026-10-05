"""Public forecasts share resolution-time alternatives without hidden draws."""
import pytest

from ai.agent import AIAgent
from ai.pending_effects import pending_counter_gain
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_linked_damage_targets import position
from tests.test_landfall_alternatives import position as alternative_position


@pytest.mark.parametrize('seat', [1, 2])
def test_linked_damage_counter_forecast_rechecks_landfall_at_resolution(seat):
    state, spell, _, _, targets = position(seat)
    observer = 3-seat
    state.players[observer].life = 3
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    ai = AIAgent()
    stack_id = state.stack[-1].id
    before = serialize_match_snapshot(state)
    ordinary = pending_counter_gain(state, observer, stack_id)
    assert ordinary is not None and ordinary > 0
    assert serialize_match_snapshot(state) == before
    state.land_entries_this_turn[seat] = 1
    before = serialize_match_snapshot(state)
    enhanced = pending_counter_gain(state, observer, stack_id)
    assert enhanced is not None and enhanced > ordinary
    assert ai._stack_item_threat_score(state, stack_id, observer) == enhanced
    assert serialize_match_snapshot(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('enhanced', [False, True])
def test_conditional_draw_forecast_stays_unknown_without_reading_library(seat, enhanced):
    state, spell, _, targets = alternative_position('mysteries-of-the-deep', seat)
    state.land_entries_this_turn[seat] = int(enhanced)
    state = checked_action(state, RulesEngine(), seat,
                           {'type': 'cast_spell', 'card_id': spell.id, 'targets': targets})
    before = serialize_match_snapshot(state)
    assert pending_counter_gain(state, 3-seat, state.stack[-1].id) is None
    assert serialize_match_snapshot(state) == before
