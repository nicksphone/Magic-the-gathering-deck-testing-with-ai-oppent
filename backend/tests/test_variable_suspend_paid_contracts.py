"""Future contracts: ordinary REDs, kept outside default backend collection."""
import pytest

from api_contracts import ActionRequest
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from rules_engine.suspend import collect_triggers, suspended
from tests.variable_suspend_support import NAMES, RAW, exile_position, position, resume


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_DESIRED_public_typed_positive_suspend_x_choice(name, seat):
    state, cid = position(name, seat)
    request = ActionRequest.model_validate({'player_id': seat, 'action': {
        'type': 'suspend', 'card_id': cid, 'x_value': 2}})
    assert request.action.model_dump()['x_value'] == 2


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('x', [1, 3])
def test_DESIRED_paid_count_priority_no_cast_and_restart(name, seat, x):
    state, cid = position(name, seat)
    before = serialize_match_snapshot(state)
    successor = checked_action(state, RulesEngine(), seat, {'type': 'suspend', 'card_id': cid, 'x_value': x})
    assert serialize_match_snapshot(state) == before
    assert successor.cards[cid].zone == Zone.EXILE
    assert successor.cards[cid].counters['time'] == x
    assert successor.players[seat].mana_pool.get('C', 0) == 6 - (3 + x)
    assert successor.players[seat].mana_pool.get(RAW[name]['colors'][0], 0) == 0
    assert not successor.stack and successor.spells_cast_this_turn[seat] == 0
    assert successor.priority_player == seat
    assert serialize_match_snapshot(resume(successor)) == serialize_match_snapshot(successor)


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_DESIRED_existing_variable_exile_keyword_recognition(name, seat):
    state, cid = exile_position(name, seat)
    assert suspended(state.cards[cid])


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_DESIRED_owner_upkeep_keyword_collector_not_whole_extra_ability(name, seat):
    state, cid = exile_position(name, seat)
    rows = collect_triggers(state, 'begin_step', {'active_player': seat, 'step': 'upkeep'})
    assert len(rows) == 1 and rows[0]['effect_key'] == 'suspend_upkeep'
    assert rows[0]['source_card_id'] == cid and rows[0]['controller'] == seat
    assert collect_triggers(state, 'begin_step', {'active_player': 3-seat, 'step': 'upkeep'}) == []


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('seat', [1, 2])
def test_DESIRED_keyword_last_counter_cast_trigger_separate_from_card_trigger(name, seat):
    state, cid = exile_position(name, seat, count=0)
    rows = collect_triggers(state, 'time_counters_removed', {'card_id': cid, 'before': 1, 'after': 0})
    assert len(rows) == 1 and rows[0]['effect_key'] == 'suspend_cast_trigger'
    assert rows[0]['source_card_id'] == cid and rows[0]['controller'] == seat
