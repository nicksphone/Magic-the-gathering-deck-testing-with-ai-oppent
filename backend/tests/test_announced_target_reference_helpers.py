"""Pure structural receipt controls; no Oracle/gameplay cards or SQL qualification."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.targeting import (capture_announced_target_references,
    validate_announced_target_references, announced_target_reference_matches,
    replace_announced_target_reference)


def primitive():
    state = SimpleNamespace(cards={'id': SimpleNamespace(id='id', battlefield_incarnation=4,
        zone_change_sequence=2)})
    choices = {'target_card_id': 'id', 'target_card_ids': ['id', 'id'],
        'target_distribution': {'id': 2, '2': 1},
        'mode_targets': {'first': {'target_card_id': 'id'}, 'second': {'target_card_id': 'id'}}}
    return state, choices


def test_all_repeated_slots_are_independent_and_replace_queries_only_chosen_slot():
    state, choices = primitive()
    bundle = capture_announced_target_references(state, choices)
    before = deepcopy(bundle)
    validate_announced_target_references(choices, bundle)
    state.cards['id'].zone_change_sequence = 4
    changed = replace_announced_target_reference(state, bundle, choices, [('target_card_ids', 1)])
    assert bundle == before
    assert changed['targets']['target_card_ids'][1]['zone_change_sequence'] == 4
    expected = deepcopy(before)
    expected['targets']['target_card_ids'][1]['zone_change_sequence'] = 4
    assert changed == expected
    assert announced_target_reference_matches(state, changed, ('target_card_ids', 1), 'id')
    assert not announced_target_reference_matches(state, changed, ('target_card_ids', 0), 'id')


def test_shape_migration_preserves_old_reference_without_querying_current_card():
    state, _ = primitive()
    bundle = capture_announced_target_references(state, {'target_card_id': 'id'})
    state.cards.clear()
    choices = {'mode_targets': {'first': {'target_card_id': 'id'}, 'second': {'target_card_id': 'id'}}}
    result = replace_announced_target_reference(state, bundle, choices, [], remapped_slots={
        ('mode_targets', mode, 'target_card_id'): ('target_card_id',) for mode in choices['mode_targets']})
    for mode in choices['mode_targets']:
        assert result['targets']['mode_targets'][mode]['target_card_id'] == bundle['targets']['target_card_id']


@pytest.mark.parametrize('bad', [None, {}, {'version': True, 'targets': {}},
    {'version': 2, 'targets': {}}, {'version': 1, 'targets': {}},
    {'version': 1, 'targets': {'target_card_id': {'card_id': 'id', 'incarnation': True, 'zone_change_sequence': 2}}},
    {'version': 1, 'targets': {'target_card_id': {'card_id': 'id', 'incarnation': -1, 'zone_change_sequence': 2}}},
    {'version': 1, 'targets': {'target_card_id': {'card_id': 'other', 'incarnation': 4, 'zone_change_sequence': 2}}},
    {'version': 1, 'targets': {'target_card_id': {'card_id': 'id', 'incarnation': 4}}},
    {'version': 1, 'targets': {'target_card_id': {'card_id': 'id', 'incarnation': 4, 'zone_change_sequence': 2, 'extra': 0}}}])
def test_malformed_receipt_rejects_without_touching_inputs(bad):
    choices = {'target_card_id': 'id'}
    before = deepcopy((choices, bad))
    with pytest.raises(ActionRejected, match='Malformed announced target references'):
        validate_announced_target_references(choices, bad)
    assert (choices, bad) == before
