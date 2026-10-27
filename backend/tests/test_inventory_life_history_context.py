"""Canonical public positions; malformed/future metadata are protocol negatives."""
from copy import deepcopy
from dataclasses import field, make_dataclass
import json
import pickle

import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchState
from rules_engine import graveyard_inventory as inventory
from rules_engine.replacement import pay_life
from tests.test_public_graveyard_reviewed_context import public_position, unchanged_query


@pytest.mark.parametrize('seat', (1, 2))
def test_known_zero_life_history_keeps_reviewed_public_sources_inert(seat):
    root, before, public, _ = public_position(seat)
    assert public.life_lost_this_turn == {1: 0, 2: 0}
    assert public.life_loss_history_known is True
    assert unchanged_query(public, seat)['status'] == 'inert'
    assert pickle.dumps(root) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_real_opponent_life_payment_requires_separate_context_review(seat):
    root, before, public, _ = public_position(seat)
    life = public.players[3-seat].life
    assert pay_life(public, 3-seat, 1)
    assert public.players[3-seat].life == life - 1
    assert public.life_lost_this_turn[3-seat] == 1
    assert public.life_loss_history_known is True
    assert unchanged_query(public, seat) == {
        'status': 'unknown',
        'reason': 'uncovered reviewed permission/protection context', 'receipts': []}
    assert pickle.dumps(root) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_legacy_missing_life_history_is_unknown_not_zero_certified(seat):
    root, before, _, _ = public_position(seat)
    payload = serialize_match_snapshot(root)
    del payload['life_lost_this_turn']
    del payload['life_loss_history_known']
    restored = deserialize_match_snapshot(json.loads(json.dumps(payload)))
    public, _ = decision_view(restored, seat, [])
    assert public.life_loss_history_known is False
    assert public.life_lost_this_turn == {1: 0, 2: 0}
    assert unchanged_query(public, seat) == {
        'status': 'unknown',
        'reason': 'uncovered reviewed permission/protection context', 'receipts': []}
    assert pickle.dumps(root) == before


BAD_LOSSES = [
    pytest.param({True: 0, 2: 0}, id='bool-key'),
    pytest.param({1.0: 0, 2: 0}, id='float-key'),
    pytest.param({1: False, 2: 0}, id='bool-value'),
    pytest.param({1: 0.0, 2: 0}, id='float-value'),
    pytest.param({1: -1, 2: 0}, id='negative-value'),
    pytest.param({1: 0}, id='missing-seat'),
    pytest.param({1: 0, 2: 0, 3: 0}, id='extra-seat'),
    pytest.param({'1': 0, '2': 0}, id='string-keys'),
]


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('losses', BAD_LOSSES)
def test_malformed_life_history_never_certifies_inert_sources(seat, losses):
    root, before, public, _ = public_position(seat)
    public.life_lost_this_turn = deepcopy(losses)
    assert unchanged_query(public, seat)['status'] == 'unknown'
    assert pickle.dumps(root) == before


@pytest.mark.parametrize('seat', (1, 2))
def test_integer_known_flag_is_not_a_boolean_certificate(seat):
    root, before, public, _ = public_position(seat)
    public.life_loss_history_known = 1
    assert unchanged_query(public, seat)['status'] == 'unknown'
    assert pickle.dumps(root) == before


@pytest.mark.parametrize('seat', (1, 2))
@pytest.mark.parametrize('kind', ('runtime', 'declared'))
def test_future_fields_still_require_review(seat, kind, monkeypatch):
    root, before, public, _ = public_position(seat)
    if kind == 'runtime':
        public.future_permission = {}
    else:
        original_fields = inventory.fields
        future = make_dataclass('FuturePublicInventory', [
            ('future_permission', dict, field(default_factory=dict))])
        monkeypatch.setattr(inventory, 'fields', lambda schema:
            original_fields(schema) + original_fields(future)
            if schema is MatchState else original_fields(schema))
    assert unchanged_query(public, seat)['status'] == 'unknown'
    assert pickle.dumps(root) == before
