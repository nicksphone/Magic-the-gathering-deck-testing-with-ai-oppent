"""Empty historical observation defaults never excuse corrupt grants. PYTEST_DONT_REWRITE"""
from copy import deepcopy

import pytest

from game_state.serializers import serialize_match_snapshot
from tests.natural_heat_diagnostic_support import canonical
from tests.test_legacy_public_entry_compat import resolved_receipt
from tests.test_natural_heat_target_audit import (
    _assert_legacy_snapshot_parity, _legacy_snapshot_with_committed_death,
    _legacy_snapshot_with_public_entry,
)


@pytest.mark.parametrize('seat', ['1', '2'])
@pytest.mark.parametrize('role', ['source', 'victim'])
@pytest.mark.parametrize('fault', ['nonempty', 'null', 'missing', 'future-field'])
def test_legacy_observation_default_does_not_hide_grants_or_missing_metadata(seat, role, fault):
    row, state, receipt, context = resolved_receipt()
    source = row['action']['card_id']
    victim = row['action']['targets']['target_card_id']
    expected = _legacy_snapshot_with_public_entry(receipt['snapshot'], source)
    expected = _legacy_snapshot_with_committed_death(
        expected, victim, row['snapshot']['cards'][victim]['zone_change_sequence'])
    actual = serialize_match_snapshot(state)
    _assert_legacy_snapshot_parity(actual, expected, receipt['snapshot'], **context)
    actual = deepcopy(actual)
    observation = actual['card_observations'][seat][source if role == 'source' else victim]
    assert observation['activated_ability_effects'] == []
    if fault == 'missing':
        del observation['activated_ability_effects']
    elif fault == 'future-field':
        observation['future_permission'] = []
    else:
        # Explicit metadata faults, not invented canonical grant episodes.
        observation['activated_ability_effects'] = [{'uncovered_ability': True}] if fault == 'nonempty' else None
    before = canonical(actual)
    with pytest.raises(AssertionError):
        _assert_legacy_snapshot_parity(actual, expected, receipt['snapshot'], **context)
    assert canonical(actual) == before
