"""Historical replay metadata must not authorize hidden or corrupt knowledge. PYTEST_DONT_REWRITE"""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from tests.natural_heat_diagnostic_support import canonical, exact_state, receipts
from tests.test_natural_heat_target_audit import (
    _assert_legacy_snapshot_parity, _legacy_snapshot_with_public_entry,
    _legacy_snapshot_with_committed_death, _replay_legacy_receipts,
)


def resolved_receipt():
    row, state = exact_state()
    state, context = _replay_legacy_receipts(row, state, receipts())
    return row, state, receipt_for_resolution(), context


def receipt_for_resolution():
    return next(row for row in receipts() if row['event'] == 'applied' and row['tick'] == 305)


@pytest.mark.parametrize('seat', ['1', '2'])
@pytest.mark.parametrize('corruption', ['hidden_card', 'name', 'reference', 'missing'])
def test_public_entry_compat_rejects_extra_or_corrupt_observations(seat, corruption):
    row, state, receipt, context = resolved_receipt()
    source_id = row['action']['card_id']
    raw_before = canonical(receipt['snapshot'])
    expected = _legacy_snapshot_with_public_entry(receipt['snapshot'], source_id)
    victim_id = row['action']['targets']['target_card_id']
    expected = _legacy_snapshot_with_committed_death(
        expected, victim_id, row['snapshot']['cards'][victim_id]['zone_change_sequence'])
    actual = serialize_match_snapshot(state)
    _assert_legacy_snapshot_parity(actual, expected, receipt['snapshot'], **context)
    assert canonical(receipt['snapshot']) == raw_before
    actual = deepcopy(actual)
    memory = actual['card_observations'][seat]
    if corruption == 'hidden_card':
        hidden = state.players[3-int(seat)].library[0]
        memory[hidden] = deepcopy(actual['cards'][hidden])
    elif corruption == 'name':
        memory[source_id]['name'] = 'corrupt observed identity'
    elif corruption == 'reference':
        memory[source_id]['zone_change_sequence'] += 1
    else:
        del memory[source_id]
    before = canonical(actual)
    with pytest.raises(AssertionError):
        _assert_legacy_snapshot_parity(actual, expected, receipt['snapshot'], **context)
    assert canonical(actual) == before


@pytest.mark.parametrize('tick', [303, 304])
def test_public_entry_compat_rejects_a_source_still_on_stack(tick):
    row, _ = exact_state()
    receipt = next(item for item in receipts() if item['event'] == 'applied' and item['tick'] == tick)
    before = canonical(receipt['snapshot'])
    with pytest.raises(AssertionError):
        _legacy_snapshot_with_public_entry(receipt['snapshot'], row['action']['card_id'])
    assert canonical(receipt['snapshot']) == before
