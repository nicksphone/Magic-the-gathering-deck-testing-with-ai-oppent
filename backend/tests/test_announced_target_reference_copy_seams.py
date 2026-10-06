"""Additional canonical paid-copy seams; the original focused tests stay frozen."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from tests.test_announced_target_reference_product import (
    setup, raw_card, ROWS, EXTRA, ref, cast, blink, passes, act, restart, snap)

FIXTURE = Path(__file__).parent / 'fixtures/coupled_targets'
LINKED = json.loads((FIXTURE / 'searing-blaze.json').read_text())
WALKER = json.loads((FIXTURE / 'ugin.json').read_text())


def paid_copy(state, seat, original_id):
    if state.priority_player != seat:
        state = act(state, state.priority_player, {'type': 'pass_priority'})
    copier = raw_card(state, EXTRA['twincast'], seat, Zone.HAND)
    state = cast(state, seat, copier.id, {'target_stack_id': original_id})
    state = passes(state)
    assert state.pending_mechanic_choice['kind'] == 'copy_target'
    return state, state.pending_mechanic_choice['stack_id']


def frame(state, sid):
    return next(item for item in state.stack if item.id == sid)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('keep', [False, True])
def test_paid_divided_copy_same_slot_new_object_preserves_amount_and_rejects_collision(seat, keep, tmp_path):
    state, first = setup(seat)
    second = raw_card(state, ROWS['Grizzly Bears'], 3-seat, Zone.BATTLEFIELD).id
    source = raw_card(state, EXTRA['pyrotechnics'], seat, Zone.HAND)
    state = cast(state, seat, source.id, {'target_distribution': {first: 2, second: 2}})
    original_id = state.stack[-1].id
    original_refs = deepcopy(state.stack[-1].payload['__announced_target_references'])
    state = blink(state, 3-seat, first)
    current = ref(state.cards[first])
    state, copied_id = paid_copy(state, seat, original_id)
    pending = state.pending_mechanic_choice
    assert pending['distribution_target'] == first
    selected = 'target_card_id:' + first
    collision = 'target_card_id:' + second
    assert selected in pending['options'] and collision not in pending['options']
    before = snap(state)
    with pytest.raises(ActionRejected):
        act(state, seat, {'type': 'choose_mechanic', 'card_ids': [collision]})
    assert snap(state) == before
    state = act(restart(state, tmp_path, 'divided-copy-first'), seat,
                {'type': 'choose_mechanic', 'card_ids': ['keep' if keep else selected]})
    assert state.pending_mechanic_choice['distribution_target'] == second
    state = act(state, seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
    copied = frame(state, copied_id)
    assert copied.payload['target_distribution'] == {first: 2, second: 2}
    expected = deepcopy(original_refs)
    if not keep:
        expected['targets']['target_distribution'][first] = current
    assert copied.payload['__announced_target_references'] == expected
    assert frame(state, original_id).payload['__announced_target_references'] == original_refs
    state = passes(state)
    assert state.cards[first].zone == (Zone.BATTLEFIELD if keep else Zone.GRAVEYARD)
    if keep:
        assert state.cards[first].counters.get('__damage_marked', 0) == 0
    assert state.cards[second].zone == Zone.GRAVEYARD
    state = passes(state)
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('to_list', [False, True])
def test_paid_linked_shape_change_migrates_untouched_old_secondary_and_specialized_receipt(seat, to_list, tmp_path):
    state, target = setup(seat)
    walker = raw_card(state, WALKER, 3-seat, Zone.BATTLEFIELD)
    source = raw_card(state, LINKED, seat, Zone.HAND)
    targets = ({'target_player': 3-seat, 'target_card_id': target} if to_list
               else {'target_card_ids': [walker.id, target]})
    state = cast(state, seat, source.id, targets)
    original_id = state.stack[-1].id
    original_refs = deepcopy(state.stack[-1].payload['__announced_target_references'])
    old_secondary = deepcopy(state.stack[-1].payload['target_instances'][1])
    secondary_ref = ref(state.cards[target])
    state = blink(state, 3-seat, target)
    assert ref(state.cards[target]) != secondary_ref
    state, copied_id = paid_copy(state, seat, original_id)
    assert state.pending_mechanic_choice['linked_target_index'] == 0
    new_primary = 'target_card_id:' + walker.id if to_list else 'target_player:' + str(3-seat)
    assert new_primary in state.pending_mechanic_choice['options']
    state = act(restart(state, tmp_path, 'linked-primary'), seat,
                {'type': 'choose_mechanic', 'card_ids': [new_primary]})
    assert state.pending_mechanic_choice['linked_target_index'] == 1
    copied = frame(state, copied_id)
    refs = copied.payload['__announced_target_references']['targets']
    if to_list:
        assert copied.payload['__announced_targets'] == {'target_card_ids': [walker.id, target]}
        assert refs['target_card_ids'] == [ref(state.cards[walker.id]), secondary_ref]
    else:
        assert copied.payload['__announced_targets'] == {'target_player': 3-seat, 'target_card_id': target}
        assert refs == {'target_card_id': secondary_ref}
    assert copied.payload['target_instances'][1] == old_secondary
    state = act(restart(state, tmp_path, 'linked-secondary'), seat,
                {'type': 'choose_mechanic', 'card_ids': ['keep']})
    assert frame(state, copied_id).payload['target_instances'][1] == old_secondary
    assert frame(state, original_id).payload['__announced_target_references'] == original_refs
    before_life, before_loyalty = state.players[3-seat].life, state.cards[walker.id].loyalty
    state = passes(state)
    assert state.cards[target].zone == Zone.BATTLEFIELD
    assert state.cards[target].counters.get('__damage_marked', 0) == 0
    assert state.players[3-seat].life == before_life - (0 if to_list else 1)
    assert state.cards[walker.id].loyalty == before_loyalty - (1 if to_list else 0)
    state = passes(state)
    assert not state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_conditional_copy_explicit_new_object_refreshes_conditional_and_generic_receipts(seat, tmp_path):
    state, target = setup(seat)
    source = raw_card(state, EXTRA['unholy-heat'], seat, Zone.HAND)
    state = cast(state, seat, source.id, {'target_card_id': target})
    original_id = state.stack[-1].id
    original_payload = deepcopy(state.stack[-1].payload)
    state = blink(state, 3-seat, target)
    current = ref(state.cards[target])
    state, copied_id = paid_copy(state, seat, original_id)
    option = 'target_card_id:' + target
    assert option in state.pending_mechanic_choice['options']
    state = act(restart(state, tmp_path, 'conditional-copy'), seat,
                {'type': 'choose_mechanic', 'card_ids': [option]})
    copied = frame(state, copied_id)
    assert copied.payload['__announced_target_references']['targets']['target_card_id'] == current
    assert frame(state, original_id).payload == original_payload
    state = passes(state)
    assert state.cards[target].zone == Zone.GRAVEYARD
    state = passes(state)
    assert not state.stack
