"""Controlled INTERNAL protocol boundaries, not a new canonical sequence card."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.keyword_triggers import schedule_control_loss_tap
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_temporary_control_lifecycle_audit import position, cast, act, passes, snap


def sequence_protocol(seat):
    state, ray, target = position(seat, 'ray-of-command')
    state = cast(state, seat, ray, target)
    item = state.stack[-1]
    original = deepcopy(item.payload)
    leaf = deepcopy(original)
    leaf.pop('__control_source_frame')
    # Explicit protocol wrapper on a genuinely announced item: no invented source,
    # StackItem, Oracle text, controller, target or successful canonical-card claim.
    item.effect_key = 'effect_sequence'
    item.payload = {**original, 'effects': [
        {'effect_key': 'temporary_control_instruction', 'payload': leaf}]}
    return state, ray, target


@pytest.mark.parametrize('seat', [1, 2])
def test_internal_sequence_leaf_uses_retained_transport_receipt(seat):
    state, ray, target = sequence_protocol(seat)
    expected = deepcopy(state.stack[-1].payload['__control_source_frame'])
    identity = state.stack[-1].id
    state = passes(state)
    assert state.cards[target].controller == seat
    record = state.delayed_triggers[-1]
    assert record['source_card_id'] == ray and record['controller'] == seat
    assert record['payload']['__control_source_frame'] == expected
    assert record['payload']['__resolving_item']['id'] == identity
    assert record['payload']['__delayed_source_reference'] == expected['source_reference']


@pytest.mark.parametrize('seat', [1, 2])
def test_internal_malformed_sequence_root_rejects_before_pop(seat):
    state, _, _ = sequence_protocol(seat)
    state.stack[-1].payload['__control_source_frame'] = None
    before = snap(state)
    with pytest.raises(ActionRejected, match='retained control'):
        resolve_top_of_stack(state)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
def test_internal_conflicting_leaf_metadata_rejects_checked_root_atomically(seat):
    state, _, _ = sequence_protocol(seat)
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    state.stack[-1].payload['effects'][0]['payload']['__control_source_frame'] = None
    before = snap(state)
    with pytest.raises(ActionRejected, match='retained control resolution'):
        checked_action(state, RulesEngine(), state.priority_player, {'type': 'pass_priority'})
    assert snap(state) == before
    # Checked-root atomicity only; no claim that direct malformed core dispatch
    # can undo preceding effect mutations on its disposable planning state.


@pytest.mark.parametrize('seat', [1, 2])
def test_internal_scheduler_unknown_receipt_key_cannot_publish(seat):
    state, ray, target = position(seat, 'ray-of-command')
    state = cast(state, seat, ray, target)
    payload = deepcopy(state.stack[-1].payload)
    frame = asdict(state.stack[-1])
    frame['payload']['__control_source_frame']['unknown'] = True
    payload['__resolving_item'] = frame
    before = snap(state)
    with pytest.raises(ActionRejected, match='retained control resolution'):
        schedule_control_loss_tap(state, seat, payload)
    assert snap(state) == before
