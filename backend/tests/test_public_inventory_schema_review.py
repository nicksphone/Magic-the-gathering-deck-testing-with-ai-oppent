"""Reviewed empty metadata is covered; active or unknown context is not."""
from copy import deepcopy
from dataclasses import field, make_dataclass

import pytest

from ai.information import decision_view
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import CardInstance, MatchState, PlayerState
from rules_engine import graveyard_inventory as inventory
from rules_engine.control_effects import record_control_effect
from rules_engine.loyalty_instructions import resolve
from tests.test_numeric_inventory_adapter import positive, pure_inventory


def public_card(state, seat, zone):
    return state.cards[getattr(state.players[seat if zone == 'battlefield' else 3-seat], zone)[0]]


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('snapshot_kind', ['current', 'explicit-empty', 'old-emblems',
                                         'old-permissions', 'old-all'])
def test_reviewed_defaults_and_legacy_omissions_preserve_coverage(seat, snapshot_kind):
    state = positive(seat)
    assert state.emblems == state.loyalty_permissions == []
    assert all(card.control_effect_base is None and card.control_effects == []
               for card in state.cards.values())
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'inert'
    payload = serialize_match_snapshot(state)
    if snapshot_kind in {'old-emblems', 'old-all'}:
        payload.pop('emblems')
    if snapshot_kind in {'old-permissions', 'old-all'}:
        payload.pop('loyalty_permissions')
    for raw in payload['cards'].values():
        assert 'control_effect_base' not in raw and 'control_effects' not in raw
        if snapshot_kind == 'explicit-empty':
            raw.update(control_effect_base=None, control_effects=[])
    restored = deserialize_match_snapshot(payload)
    assert restored.emblems == restored.loyalty_permissions == []
    assert all(card.control_effect_base is None and card.control_effects == []
               for card in restored.cards.values())
    assert pure_inventory(restored, seat) == expected
    projected, _ = decision_view(restored, seat, [])
    assert pure_inventory(projected, seat) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('operation', ['emblem', 'flash'])
def test_real_permission_producers_remain_uncovered(seat, operation):
    state = positive(seat)
    resolve(state, seat, {'loyalty_operation': operation,
                         'text': 'Creatures you control get +1/+1.'})
    expected = {'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}
    assert pure_inventory(state, seat) == expected
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert pure_inventory(restored, seat) == expected
    projected, _ = decision_view(restored, seat, [])
    assert pure_inventory(projected, seat) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['emblems', 'loyalty_permissions'])
@pytest.mark.parametrize('entry', ['absent-source', {}, {'created_turn': -1},
                                  {'kind': 'unsupported-future-permission'}])
def test_nonempty_state_context_is_not_filtered_to_inert(seat, name, entry):
    state = positive(seat)
    setattr(state, name, [deepcopy(entry)])
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', ['battlefield', 'graveyard'])
@pytest.mark.parametrize('base', [1, 2, 0, False, {}, [], ''])
def test_control_baseline_must_be_none_not_merely_falsey(seat, zone, base):
    state = positive(seat)
    public_card(state, seat, zone).control_effect_base = deepcopy(base)
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('zone', ['battlefield', 'graveyard'])
@pytest.mark.parametrize('entry', [{}, {'expires_turn': -1}, {'kind': 'future-control'}])
def test_nonempty_control_ledger_is_never_covered(seat, zone, entry):
    state = positive(seat)
    public_card(state, seat, zone).control_effects = [deepcopy(entry)]
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('ledger_kind', ['live', 'expired', 'retained-base'])
def test_retained_valid_control_history_is_uncovered_even_without_transfer(seat, ledger_kind):
    state = positive(seat)
    card = public_card(state, seat, 'battlefield')
    record_control_effect(state, card, card.controller)
    assert state.temporary_control_changes == {}
    if ledger_kind == 'expired':
        card.control_effects[0]['expires_turn'] = state.turn - 1
    elif ledger_kind == 'retained-base':
        card.control_effects.clear()
    expected = pure_inventory(state, seat)
    assert expected['status'] == 'unknown'
    assert expected['reason'] == 'uncovered source modification/metadata'
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert pure_inventory(restored, seat) == expected
    projected, _ = decision_view(restored, seat, [])
    assert pure_inventory(projected, seat) == expected


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target', ['emblems', 'loyalty_permissions', 'battlefield', 'graveyard'])
@pytest.mark.parametrize('bad', [None, (), {}, set(), 0, False, ''])
def test_malformed_reviewed_list_container_fails_closed(seat, target, bad):
    state = positive(seat)
    value, name = ((state, target) if target in {'emblems', 'loyalty_permissions'}
                   else (public_card(state, seat, target), 'control_effects'))
    setattr(value, name, deepcopy(bad))
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target', ['state', 'battlefield', 'graveyard', 'player'])
def test_future_runtime_field_is_unknown_even_when_empty(seat, target):
    state = positive(seat)
    value = (state if target == 'state' else state.players[seat] if target == 'player'
             else public_card(state, seat, target))
    value.future_permission = []
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('schema', [MatchState, CardInstance, PlayerState])
def test_future_declared_field_requires_another_review(seat, schema, monkeypatch):
    state = positive(seat)
    assert pure_inventory(state, seat)['status'] == 'inert'
    actual_fields = inventory.fields
    extra = make_dataclass('FutureContext', [('future_permission', list, field(default_factory=list))])
    monkeypatch.setattr(inventory, 'fields', lambda cls: actual_fields(cls) + actual_fields(extra)
                        if cls is schema else actual_fields(cls))
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target,name', [('state', 'emblems'), ('state', 'loyalty_permissions'),
                                      ('battlefield', 'control_effect_base'),
                                      ('battlefield', 'control_effects'),
                                      ('graveyard', 'control_effect_base'),
                                      ('graveyard', 'control_effects')])
def test_missing_runtime_metadata_is_not_legacy_snapshot_omission(seat, target, name):
    state = positive(seat)
    value = state if target == 'state' else public_card(state, seat, target)
    delattr(value, name)
    assert pure_inventory(state, seat)['status'] == 'unknown'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['numeric_prevention_shields', 'emblems', 'loyalty_permissions'])
def test_continuation_veto_precedes_but_does_not_replace_reviewed_permission_veto(seat, name):
    state = positive(seat)
    state.spell_color_history[seat].add('R')
    reviewed = {'status': 'unknown', 'reason': 'uncovered reviewed permission/protection context',
                'receipts': []}
    assert pure_inventory(state, seat) == reviewed
    setattr(state, name, [{'unsupported-component-context': True}])
    assert pure_inventory(state, seat) == {
        'status': 'unknown', 'reason': 'uncovered continuation/effect context', 'receipts': []}
    setattr(state, name, [])
    assert pure_inventory(state, seat) == reviewed
