"""Private continuation boundaries, produced by genuine canonical activations."""
from copy import deepcopy

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from rules_engine.action_validation import ActionRejected
from tests.test_forge_human_replacement_order import act, fingerprint, setup
from tests.test_linked_mana_damage import request


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_native_pause_has_private_snapshot_and_no_public_owner(seat):
    state, sources, _, _ = setup(seat)
    result = act(state, seat, request(state.cards[sources[0]], 'W'))
    assert result.pending_replacement_choice is not None
    private = result.mana_continuation
    assert private['version'] == 1 and private['origin']['actor'] == seat
    before = fingerprint(result)
    snapshot = serialize_match_snapshot(result)
    assert snapshot['mana_continuation'] == private
    assert snapshot['mana_continuation'] is not private
    assert 'mana_continuation' not in serialize_match(result)
    assert 'frames' not in result.pending_replacement_choice
    assert fingerprint(deserialize_match_snapshot(snapshot)) == before
    snapshot['mana_continuation']['version'] = -1
    assert fingerprint(result) == before


@pytest.mark.parametrize('bad', [True, 0, 2, '1'])
def test_snapshot_refuses_unknown_or_mistyped_private_version(bad):
    state, _, _, _ = setup(1)
    snapshot = deepcopy(serialize_match_snapshot(state))
    snapshot['mana_continuation'] = {'version': bad}
    with pytest.raises((ValueError, ActionRejected)):
        deserialize_match_snapshot(snapshot)


@pytest.mark.parametrize('seat', [1, 2])
def test_valid_legacy_snapshot_without_private_field_stays_idle(seat):
    state, _, _, _ = setup(seat)
    snapshot = serialize_match_snapshot(state)
    snapshot.pop('mana_continuation', None)
    result = deserialize_match_snapshot(snapshot)
    assert getattr(result, 'mana_continuation', None) is None
    assert result.rng.getstate() == state.rng.getstate()
