"""Legacy receipt compatibility must never erase a real queued schedule."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.stack_engine import resolve_top_of_stack
from rules_engine.turn_scheduler import ensure_plan
from tests.natural_heat_diagnostic_support import canonical, exact_state
from tests.queued_sequence_support import cast, position
from tests.test_natural_heat_target_audit import _assert_legacy_snapshot_parity


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('queued_side', ['actual', 'expected'])
def test_nondefault_canonical_queued_schedule_cannot_pass_legacy_parity(seat, queued_side):
    row, state = exact_state()
    actual = serialize_match_snapshot(state)
    historical = deepcopy(row['snapshot'])
    before = canonical(historical)
    _assert_legacy_snapshot_parity(actual, historical)
    assert canonical(historical) == before

    queued, _ = cast(position(seat), 'Time Warp', seat, {'target_player': seat})
    assert resolve_top_of_stack(queued)
    # Match the sealed end-step fixture so the queue is valid, not a malformed cursor.
    queued.step = state.step
    ensure_plan(queued)
    schedule = serialize_match_snapshot(queued)['scheduler']
    assert schedule['extra_turns'][0]['recipient'] == seat
    if queued_side == 'actual':
        actual['scheduler'] = schedule
    else:
        historical['scheduler'] = schedule
    deserialize_match_snapshot(actual)
    deserialize_match_snapshot(historical)
    actual_before, historical_before = canonical(actual), canonical(historical)
    with pytest.raises(AssertionError):
        _assert_legacy_snapshot_parity(actual, historical)
    assert canonical(actual) == actual_before
    assert canonical(historical) == historical_before
