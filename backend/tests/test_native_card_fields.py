"""Differential checks for the optional C++ card metadata copier."""
from copy import deepcopy
import gc
import os

import pytest

from game_state import copying
from game_state.serializers import serialize_match_snapshot
from game_state.state import CardInstance, Zone
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_root_metadata_copy_contract import canonical120, state_with_metadata

if os.getenv('MTG_AI_NATIVE_METADATA_COPY') == '1':
    from _mtg_native_card_fields import copy_card_fields
else:
    copy_card_fields = pytest.importorskip('_mtg_native_card_fields').copy_card_fields


@pytest.fixture
def native_hits(monkeypatch):
    hits = []

    def observe(*args):
        result = copy_card_fields(*args)
        hits.append(result is not None)
        return result

    monkeypatch.setattr(copying, '_copy_card_fields_native', observe)
    return hits


def test_low_level_batch_preserves_order_aliases_cycles_and_memo():
    shared = []
    root = object()
    copied_root = object()
    shared.extend([shared, root, Zone.HAND])
    left = {'second': shared, 'first': 193}
    right = {'own': {'alias': shared}}
    memo = {id(root): copied_root}
    fields, additions, retained = copy_card_fields([left, right], memo, Zone)
    assert memo == {id(root): copied_root}
    assert list(fields[0]) == ['second', 'first']
    copied = fields[0]['second']
    assert copied is additions[id(shared)] is fields[1]['own']['alias']
    assert copied is not shared and copied[0] is copied
    assert copied[1:] == [copied_root, Zone.HAND]
    assert [id(source) for source in retained] == [id(shared), id(right['own'])]
    copied.append('new')
    assert len(shared) == 3 and shared[1] is root


@pytest.mark.parametrize('history', [True, False])
def test_integrated_batch_preserves_card_root_and_sibling_aliases(native_hits, history):
    state = state_with_metadata()
    one = CardInstance('one', '', 1, 1, Zone.HAND)
    two = CardInstance('two', '', 2, 2, Zone.HAND)
    state.cards = {two.id: two, one.id: one}
    shared = []
    shared.extend([shared, state, state.__dict__, two])
    one.metadata = {'tail': shared, 'before': [1]}
    two.metadata = shared

    expected = deepcopy(state)
    clone = copying.copy_match_state(state, include_history=history)
    assert native_hits == [True]
    assert list(clone.cards) == list(expected.cards) == ['two', 'one']
    assert clone.rng.getstate() == expected.rng.getstate()
    assert clone.log == (expected.log if history else [])
    assert clone.log_alias is clone.log
    attached = clone.cards['one'].metadata['tail']
    assert attached is clone.cards['two'].metadata and attached is not shared
    assert attached[0] is attached and attached[1] is clone
    assert attached[2] is not clone.__dict__ and attached[2]['cards'] is clone.cards
    assert attached[3] is clone.cards['two']
    assert list(clone.cards['one'].metadata) == list(expected.cards['one'].metadata)
    assert clone.cards['one'].metadata['before'] == expected.cards['one'].metadata['before']
    attached.append('new')
    assert len(shared) == 4


def test_batch_miss_leaves_hooks_to_python_and_keeps_atomic_overrides(native_hits):
    state = state_with_metadata()
    card = CardInstance('unsupported', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    calls = []
    atom = ''.join(['literal-', 'later'])

    class Hook:
        def __deepcopy__(self, memo):
            calls.append('hook')
            memo[id(atom)] = 'python hook'
            return 'fallback copy'

    shared = []
    shared.append(shared)
    card.metadata = [shared, Hook(), atom]
    gc_before = gc.isenabled()
    clone = copying.copy_match_state(state)
    assert gc.isenabled() is gc_before
    assert native_hits == [False] and calls == ['hook']
    payload = clone.cards[card.id].metadata
    assert payload[0] is not shared and payload[0][0] is payload[0]
    assert payload[1:] == ['fallback copy', 'python hook']
    assert card.metadata[2] is atom


@pytest.mark.parametrize('unsupported', [{1, 2}, ('item',), [[[[]]]]])
def test_raw_miss_leaves_original_memo_untouched(unsupported):
    class Special(list):
        pass

    if isinstance(unsupported, list):
        for _ in range(512):
            unsupported = [unsupported]
    original = {'sentinel': []}
    memo = {id(original): original}
    assert copy_card_fields([{'same': original, 'miss': unsupported}, {'foreign': Special()}], memo, Zone) is None
    assert memo == {id(original): original}


def test_explicit_memo_and_field_copier_do_not_call_native(native_hits):
    state = state_with_metadata()
    card = CardInstance('edge', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    card.metadata = [['ordinary']]
    actual = copying.copy_match_state(state, memo={id(card.metadata): ['replace']})
    assert actual.cards[card.id].metadata == ['replace']
    copying.copy_match_state(state, _field_copier=deepcopy)
    assert native_hits == []


def test_registered_gc_callback_retains_python_path(native_hits):
    state = state_with_metadata()
    card = CardInstance('gc-guard', '', 1, 1, Zone.HAND)
    state.cards[card.id] = card
    card.metadata = [['unchanged']]

    def callback(phase, info):
        pass

    gc.callbacks.append(callback)
    try:
        result = copying.copy_match_state(state)
    finally:
        gc.callbacks.remove(callback)
    assert result.cards[card.id].metadata == card.metadata
    assert result.cards[card.id].metadata is not card.metadata
    assert native_hits == []


def test_checked_action_matches_python_in_real_canonical_position(native_hits, monkeypatch):
    state = canonical120()
    engine = RulesEngine()
    before = serialize_match_snapshot(state)
    seat = state.priority_player
    offer = next(move for move in engine.legal_moves(state, seat) if move['type'] == 'mulligan')
    action = {'type': offer['type']}
    native = checked_action(state, engine, seat, action)
    assert True in native_hits
    monkeypatch.setattr(copying, '_copy_card_fields_native', None)
    reference = checked_action(state, engine, seat, action)
    assert serialize_match_snapshot(native) == serialize_match_snapshot(reference)
    assert list(native.cards) == list(reference.cards)
    assert native.rng.getstate() == reference.rng.getstate()
    assert serialize_match_snapshot(state) == before
