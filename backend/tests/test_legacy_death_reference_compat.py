"""A historical reference adapter cannot excuse other state corruption. PYTEST_DONT_REWRITE"""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from tests.natural_heat_diagnostic_support import canonical, witness
from tests.test_legacy_public_entry_compat import receipt_for_resolution, resolved_receipt
from tests.test_natural_heat_target_audit import (
    _assert_legacy_snapshot_parity, _legacy_snapshot_with_committed_death,
    _legacy_snapshot_with_public_entry,
)


@pytest.mark.parametrize('corruption', ['zone', 'sequence', 'membership', 'observation'])
def test_death_reference_adapter_rejects_invalid_historical_provenance(corruption):
    row = witness()
    card_id = row['action']['targets']['target_card_id']
    previous = row['snapshot']['cards'][card_id]['zone_change_sequence']
    snapshot = deepcopy(receipt_for_resolution()['snapshot'])
    if corruption == 'zone':
        snapshot['cards'][card_id]['zone'] = 'battlefield'
    elif corruption == 'sequence':
        snapshot['cards'][card_id]['zone_change_sequence'] += 1
    elif corruption == 'membership':
        snapshot['players'][str(snapshot['cards'][card_id]['owner'])]['graveyard'].remove(card_id)
    else:
        del snapshot['card_observations']['1'][card_id]
    before = canonical(snapshot)
    with pytest.raises((AssertionError, KeyError)):
        _legacy_snapshot_with_committed_death(snapshot, card_id, previous)
    assert canonical(snapshot) == before


@pytest.mark.parametrize('seat', ['1', '2'])
@pytest.mark.parametrize('corruption', ['name', 'sequence', 'life', 'hidden'])
def test_legacy_death_reference_does_not_relax_other_parity(seat, corruption):
    row, state, receipt, context = resolved_receipt()
    card_id = row['action']['targets']['target_card_id']
    raw = receipt['snapshot']
    before = canonical(raw)
    expected = _legacy_snapshot_with_committed_death(
        raw, card_id, row['snapshot']['cards'][card_id]['zone_change_sequence'])
    expected = _legacy_snapshot_with_public_entry(expected, row['action']['card_id'])
    actual = serialize_match_snapshot(state)
    _assert_legacy_snapshot_parity(actual, expected, raw, **context)
    assert canonical(raw) == before
    if corruption == 'name':
        actual['card_observations'][seat][card_id]['name'] = 'corrupt identity'
    elif corruption == 'sequence':
        actual['cards'][card_id]['zone_change_sequence'] += 1
    elif corruption == 'life':
        actual['players'][seat]['life'] += 1
    else:
        hidden = actual['players'][str(3-int(seat))]['library'][0]
        actual['card_observations'][seat][hidden] = deepcopy(actual['cards'][hidden])
    actual_before, expected_before = canonical(actual), canonical(expected)
    with pytest.raises(AssertionError):
        _assert_legacy_snapshot_parity(actual, expected, raw, **context)
    assert canonical(actual) == actual_before
    assert canonical(expected) == expected_before
    assert canonical(raw) == before
