"""Paid episodes plus explicitly controlled malformed persisted-frame negatives."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from game_state.serializers import deserialize_match_snapshot
from game_state.state import Zone, object_incarnation
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_temporary_control_lifecycle_audit import position, cast, act, passes, raw_card, snap
from tests.test_generic_protection_damage import CANONICAL


FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad', [None, [], {}, 'receipt', 'reference-list', 'boolean',
                                'negative', 'foreign-source', 'unknown-copy', 'copy-list', 'wrong-id'])
def test_malformed_persisted_control_provenance_rejects_before_any_mutation(seat, bad):
    state, ray, target = position(seat, 'ray-of-command')
    state = cast(state, seat, ray, target)
    item = state.stack[-1]
    # Controlled corruption of a genuinely announced item, never executed as valid context.
    receipt = {'stack_id': item.id, 'source_card_id': ray, 'cast_controller': seat,
               'label': item.label, 'source_reference': {
                   'incarnation': object_incarnation(state.cards[ray]),
                   'zone_change_sequence': state.cards[ray].zone_change_sequence}}
    if bad in (None, [], {}, 'receipt'):
        receipt = bad
    elif bad == 'reference-list':
        receipt['source_reference'] = []
    elif bad == 'boolean':
        receipt['source_reference']['incarnation'] = True
    elif bad == 'negative':
        receipt['source_reference']['zone_change_sequence'] = -1
    elif bad == 'foreign-source':
        receipt['source_card_id'] = target
    elif bad == 'unknown-copy':
        item.payload['__stack_copy_kind'] = 'unknown'
    elif bad == 'copy-list':
        item.payload['__stack_copy_kind'] = []
    else:
        receipt['stack_id'] = 'not-the-announced-item'
    item.payload['__control_source_frame'] = receipt
    state = deserialize_match_snapshot(snap(state))
    before = snap(state)
    with pytest.raises(ActionRejected, match='[Cc]ontrol source|retained control'):
        resolve_top_of_stack(state)
    assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('opposing', [False, True])
@pytest.mark.parametrize('departed', [False, True])
def test_real_paid_copy_has_actual_resolution_identity_and_retained_physical_reference(
        seat, opposing, departed, monkeypatch):
    """Strict desired ledger: requires the separate genuine producer/scheduler patch."""
    copier = 3-seat if opposing else seat
    state, ray, target = position(seat, 'ray-of-command')
    alternative = raw_card(state, CANONICAL['White Knight'],
                           seat if opposing else 3-seat, Zone.BATTLEFIELD).id
    twin = raw_card(state, json.loads((FIXTURES / 'coupled_targets/twincast.json').read_text()),
                    copier, Zone.HAND).id
    counteractor = 3-seat
    counter = raw_card(state, json.loads((FIXTURES / 'trigger_instruction_product/counterspell.json').read_text()),
                       counteractor, Zone.HAND).id
    state.players[seat].mana_pool = {'C': 3, 'U': 3 if copier == seat else 1}
    state.players[counteractor].mana_pool = {'U': 4 if opposing else 2}
    state = cast(state, seat, ray, target)
    original = asdict(state.stack[-1])
    physical = {'incarnation': object_incarnation(state.cards[ray]),
                'zone_change_sequence': state.cards[ray].zone_change_sequence}
    if opposing:
        state = act(state, seat, {'type': 'pass_priority'})
    state = act(state, copier, {'type': 'cast_spell', 'card_id': twin,
                              'cost_choice': {'id': 'base'},
                              'targets': {'target_stack_id': original['id']}})
    state = passes(state)
    choice = 'target_card_id:' + alternative if opposing else 'keep'
    assert choice in state.pending_mechanic_choice['options']
    state = act(state, copier, {'type': 'choose_mechanic', 'card_ids': [choice]})
    copied = asdict(state.stack[-1])
    assert copied['id'] != original['id'] and copied['controller'] == copier
    assert copied['payload']['__copied_from_stack_id'] == original['id']
    if departed:
        if state.priority_player != counteractor:
            state = act(state, state.priority_player, {'type': 'pass_priority'})
        state = act(state, counteractor, {'type': 'cast_spell', 'card_id': counter,
                                       'cost_choice': {'id': 'base'},
                                       'targets': {'target_stack_id': original['id']}})
        state = passes(state)
        assert state.cards[ray].zone == Zone.GRAVEYARD
        assert state.stack[-1].id == copied['id']
        assert state.cards[ray].zone_change_sequence > physical['zone_change_sequence']
    state = deserialize_match_snapshot(snap(state))
    import rules_engine.stack_engine as stack_engine
    resolve = stack_engine.resolve_effect
    observed = []

    def spy(current, actor, key, payload):
        if key == 'temporary_control_instruction':
            observed.append((actor, deepcopy(payload)))
        return resolve(current, actor, key, payload)

    monkeypatch.setattr(stack_engine, 'resolve_effect', spy)
    state = passes(state)
    assert observed and observed[-1][0] == copier
    frame = observed[-1][1]['__resolving_item']
    assert frame['id'] == copied['id'] and frame['controller'] == copier
    assert frame['payload']['__stack_copy_kind'] == 'spell'
    assert '__resolving_item' not in frame['payload']
    assert frame['payload']['__control_source_frame']['source_reference'] == physical
    assert frame['payload']['__control_source_frame']['stack_id'] == original['id']
    assert state.cards[alternative if opposing else target].controller == copier
    record = state.delayed_triggers[-1]
    assert record['controller'] == copier
    assert copied['id'] in json.dumps(record)
