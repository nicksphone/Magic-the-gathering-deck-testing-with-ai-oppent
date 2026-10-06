"""Strict complete paid Favor flows; illegal counter targets remain ordinary RED."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.favor_lifecycle_support import (
    paid_to_search, act, snap, restart, record, assert_private, assert_outcome,
)


@pytest.fixture
def shuffles(monkeypatch):
    import rules_engine.events as events
    original = events.emit_event
    trace = []

    def observe(state, event, payload):
        if event == 'shuffle':
            trace.append(deepcopy(payload))
        return original(state, event, payload)

    monkeypatch.setattr(events, 'emit_event', observe)
    return trace


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'zero', 'unsummon', 'bolt', 'veil', 'blink'])
@pytest.mark.parametrize('find', [False, True])
def test_actual_paid_favor_response_partial_target_search_continuation(seat, mode, find, tmp_path, shuffles):
    state, data = paid_to_search(seat, mode, tmp_path)
    affected = data['affected']
    pending = state.pending_mechanic_choice
    assert pending['kind'] == 'search_library' and pending['player_id'] == affected
    assert pending['continuation_controller'] == pending['resolving_item']['controller'] == seat
    assert pending['resolving_item']['id'] == data['stack_id']
    assert pending['min_count'] == 0 and pending['count'] == 1
    assert set(data['library']) == set(pending['options'])
    assert not set(data['caster_library']).intersection(pending['options'])
    assert_private(state, affected)
    data['chosen'] = pending['options'][1]
    before = snap(state)
    invalid = [
        (seat, {'type': 'choose_mechanic', 'card_ids': [data['chosen']]}),
        (affected, {'type': 'choose_mechanic', 'card_ids': [data['caster_library'][0]]}),
        (affected, {'type': 'choose_mechanic', 'card_ids': [data['chosen'], data['chosen']]}),
        (affected, {'type': 'pass_priority'}),
    ]
    for actor, action in invalid:
        with pytest.raises(ActionRejected):
            act(state, actor, action)
        assert snap(state) == before
    state = restart(state, tmp_path, 'search-paused')
    rng = state.rng.getstate()
    state = act(state, affected, {'type': 'choose_mechanic', 'card_ids': [data['chosen']] if find else []})
    record(tmp_path, 'actual-complete-before-desired-assertion', state, data)
    assert state.rng.getstate() != rng
    # act() executes independent restored copies to prove root/determinism parity.
    assert len(shuffles) == 2 and shuffles[0] == shuffles[1]
    receipt = shuffles[0]
    assert receipt['player_id'] == affected
    assert receipt['cause']['controller'] == seat and receipt['cause']['stack_id'] == data['stack_id']
    assert receipt['cause']['source_card_id'] == data['source'] and receipt['cause']['kind'] == 'spell'
    assert_private(restart(state, tmp_path, 'complete'), affected)
    assert_outcome(state, data, find)


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_paid_favor_no_eligible_search_still_shuffles_and_applies_legal_suffix(seat, tmp_path, shuffles):
    state, data = paid_to_search(seat, 'none', tmp_path, eligible=False)
    assert state.pending_mechanic_choice is None
    assert len(shuffles) == 2 and shuffles[0] == shuffles[1]
    assert shuffles[0]['player_id'] == data['affected']
    assert shuffles[0]['cause']['controller'] == seat
    assert shuffles[0]['cause']['stack_id'] == data['stack_id']
    assert_outcome(state, data, False)
    assert_private(restart(state, tmp_path, 'no-eligible-complete'), data['affected'])
