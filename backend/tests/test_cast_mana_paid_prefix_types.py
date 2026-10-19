"""Strict private reference types on a genuine completed native mana prefix."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from tests.test_cast_mana_owner_native import paused_cast
from tests.test_forge_human_replacement_order import balances, choose, restore


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field', ['incarnation', 'zone_change_sequence'])
def test_completed_native_prefix_refuses_equal_valued_float(seat, field):
    state, _, _ = paused_cast(seat)
    receipt = next(iter(balances(state)))
    state = choose(restore(state), seat, receipt)
    before = deepcopy(serialize_match_snapshot(state))
    assert state.pending_replacement_choice is not None
    payment = before['mana_continuation']['frames'][1]['data']
    assert payment['cursor'] == 1 and payment['in_flight'] is True
    assert len(payment['paid_prefix']) == 1
    payload = deepcopy(before)
    retained = payload['mana_continuation']['frames'][1]['data']
    source = retained['paid_prefix'][0]['source']
    assert source == retained['steps'][0]['source'] and type(source[field]) is int
    source[field] = float(source[field])
    assert type(source[field]) is float and source == retained['steps'][0]['source']
    corrupted = deepcopy(payload)
    try:
        with pytest.raises(ActionRejected):
            deserialize_match_snapshot(payload)
    finally:
        assert payload == corrupted
        assert serialize_match_snapshot(state) == before
