"""Shape-only controls, not amount/unknown-key gameplay admission claims."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.targeting import (
    capture_announced_target_references, validate_announced_target_references)
from tests.test_announced_target_reference_helpers import primitive

BAD = [None, False, True, 0, '', 'root', [], ()]
BAD += [{'target_card_id': value} for value in [True, 0, 1, '', [], {}]]
BAD += [{'target_card_ids': value} for value in ['', 'id', (), {}, [None], [True], [0], [''], [[]], [{}]]]
BAD += [{'target_distribution': value} for value in ['', [], (), True, {None: 1}, {True: 1}, {0: 1}, {3: 1}, {'': 1}]]
BAD += [{'mode_targets': value} for value in [[], (), True, {'one': []}, {'one': 'id'}]]
BAD += [{'mode_targets': {'one': {'target_card_id': []}}},
        {'mode_targets': {'one': {'target_card_ids': ['']}}}]


@pytest.mark.parametrize('announced', BAD)
def test_capture_and_validate_share_structured_shape_rejection_without_mutating_inputs(announced):
    state, _ = primitive()
    before_state, before_announcement = deepcopy(state), deepcopy(announced)
    with pytest.raises(ActionRejected, match='Malformed announced target references'):
        capture_announced_target_references(state, announced)
    with pytest.raises(ActionRejected, match='Malformed announced target references'):
        validate_announced_target_references(announced, {'version': 1, 'targets': {}})
    assert state == before_state and announced == before_announcement


@pytest.mark.parametrize('announced', [{}, {'target_card_id': None}, {'target_card_ids': []},
    {'target_distribution': {}}, {'mode_targets': {}},
    {'target_player': 1, 'target_stack_id': 'stack', 'x_value': 3},
    {'target_distribution': {'1': None, '2': 'not-an-amount', 1: -9, 2: True}},
    {'future_metadata': {'opaque': [None]}, 'mode_texts': ['not-our-grammar']},
    {'mode_targets': {'empty': {'target_player': 2}, 'other': {}}}])
def test_empty_player_only_and_unowned_metadata_are_preserved_without_card_queries(announced):
    state, _ = primitive()
    state.cards.clear()
    before = deepcopy((state, announced))
    bundle = capture_announced_target_references(state, announced)
    validate_announced_target_references(announced, bundle)
    assert (state, announced) == before
    # Opaque amount values above test helper non-interference, NOT legal gameplay.


@pytest.mark.parametrize('amount', [None, -9, True, 'not-an-amount'])
def test_distribution_card_reference_does_not_expand_amount_semantics(amount):
    state, _ = primitive()
    announced = {'target_distribution': {'id': amount}}
    before = deepcopy(announced)
    bundle = capture_announced_target_references(state, announced)
    assert bundle['targets']['target_distribution']['id']['card_id'] == 'id'
    validate_announced_target_references(announced, bundle)
    assert announced == before


def test_nested_modal_and_duplicate_ordered_slots_remain_parallel_and_independent():
    state, _ = primitive()
    announced = {'target_card_ids': ['id', 'id'],
        'mode_targets': {'outer': {'mode_targets': {'inner': {'target_card_id': 'id'}}}}}
    bundle = capture_announced_target_references(state, announced)
    validate_announced_target_references(announced, bundle)
    ordered = bundle['targets']['target_card_ids']
    assert ordered[0] == ordered[1] and ordered[0] is not ordered[1]
    assert bundle['targets']['mode_targets']['outer']['mode_targets']['inner']['target_card_id'] == ordered[0]
