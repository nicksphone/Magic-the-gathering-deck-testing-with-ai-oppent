"""Inventory schema/veto protocols, not continuation or gameplay qualification."""
from copy import deepcopy
from dataclasses import field, make_dataclass
import json
import pickle

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match, serialize_match_snapshot
from game_state.state import MatchState
from rules_engine import graveyard_inventory as inventory
from tests.test_numeric_inventory_adapter import positive, pure_inventory


REVIEWED_MATCH91 = '6781fbd7d6aa55cfb6d6b9aee82506ba9f824d0603ef60fe733263a982551867'
REVIEWED_MATCH93 = 'cbeb9f80f6473744268be74235a1616122da8a0b0578f2b9c61e3f955d57ef31'
PRIVATE_SENTINEL = 'PRIVATE_MANA_PAYLOAD_MUST_NOT_ENTER_PUBLIC_COVERAGE'


@pytest.fixture
def reviewed_pin_only_protocol_negative(monkeypatch):
    """Expose missing context vetoes without changing data or production code."""
    monkeypatch.setitem(inventory._SCHEMA_PINS, MatchState, REVIEWED_MATCH93)


class PrivatePayload:
    def __deepcopy__(self, memo):
        raise AssertionError('Private continuation payload must not be copied')

    def __iter__(self):
        raise AssertionError('Private continuation payload must not be traversed')

    def __bool__(self):
        raise AssertionError('Private continuation payload must not be interpreted')


@pytest.mark.parametrize('seat', [1, 2])
def test_current_none_and_legacy_omission_preserve_default_coverage(seat):
    state = positive(seat)
    assert state.mana_continuation is None
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    native = deepcopy(serialize_match_snapshot(state))
    for legacy in (False, True):
        payload = deepcopy(native)
        if legacy:
            del payload['mana_continuation']
        restored = deserialize_match_snapshot(json.loads(json.dumps(payload)))
        assert restored.mana_continuation is None
        assert pure_inventory(restored, seat) == expected
    assert serialize_match_snapshot(state) == native


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['empty', 'native-envelope-shape', 'opaque'])
def test_dictionary_continuation_is_vetoed_without_interpretation(
        seat, kind, reviewed_pin_only_protocol_negative):
    state = positive(seat)
    if kind == 'empty':
        payload = {}
    elif kind == 'native-envelope-shape':
        # Negative outer-schema protocol only: no valid owner/frame is invented.
        payload = {'version': 1, 'origin': {}, 'frames': [], 'waiting': {}}
    else:
        payload = {PRIVATE_SENTINEL: PrivatePayload()}
    state.mana_continuation = payload
    before = pickle.dumps(state, protocol=5)
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}
    public = serialize_match(state, look_players=[seat])
    assert 'mana_continuation' not in public
    assert PRIVATE_SENTINEL not in json.dumps(public)
    assert state.mana_continuation is payload
    assert pickle.dumps(state, protocol=5) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [[], (), False, 0, ''], ids=['list', 'tuple', 'bool', 'int', 'str'])
def test_malformed_continuation_type_is_unknown_without_mutation(
        seat, bad, reviewed_pin_only_protocol_negative):
    state = positive(seat)
    state.mana_continuation = deepcopy(bad)
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'incomplete state metadata', 'receipts': []}


@pytest.mark.parametrize('seat', [1, 2])
def test_missing_runtime_continuation_is_not_legacy_snapshot_omission(
        seat, reviewed_pin_only_protocol_negative):
    state = positive(seat)
    del state.mana_continuation
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'incomplete state metadata', 'receipts': []}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['runtime', 'declared'])
def test_future_field_still_requires_separate_review(
        seat, kind, monkeypatch, reviewed_pin_only_protocol_negative):
    state = positive(seat)
    if kind == 'runtime':
        state.future_private_permission = {}
        reason = 'uncovered state field'
    else:
        actual_fields = inventory.fields
        extra = make_dataclass('FutureInventoryMetadata', [
            ('future_private_permission', dict, field(default_factory=dict))])
        monkeypatch.setattr(inventory, 'fields', lambda schema:
            actual_fields(schema) + actual_fields(extra) if schema is MatchState
            else actual_fields(schema))
        reason = 'incomplete state metadata'
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': reason, 'receipts': []}


@pytest.mark.parametrize('seat', [1, 2])
def test_historical_91_field_pin_still_refuses_current_schema(seat, monkeypatch):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    monkeypatch.setitem(inventory._SCHEMA_PINS, MatchState, REVIEWED_MATCH91)
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'incomplete state metadata', 'receipts': []}
