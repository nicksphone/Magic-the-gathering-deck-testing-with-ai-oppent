"""Desired structured rejection of malformed real persisted announcements."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.targeting import validate_announced_target_references
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_announced_target_reference_product import early_path, act, snap

CASES = {
    'root-number': 1,
    'root-list': ['nonempty'],
    'ids-null': {'target_card_ids': None},
    'ids-number': {'target_card_ids': 1},
    'distribution-null': {'target_distribution': None},
    'distribution-number': {'target_distribution': 1},
    'modes-null': {'mode_targets': None},
    'modes-string': {'mode_targets': 'invalid'},
    'mode-child-null': {'mode_targets': {'one': None}},
    'mode-child-number': {'mode_targets': {'one': 1}},
}


@pytest.mark.parametrize('case', CASES)
def test_malformed_announcement_shape_is_structured_without_input_mutation(case):
    announced = deepcopy(CASES[case])
    receipt = {'version': 1, 'targets': {}}
    before = deepcopy((announced, receipt))
    try:
        with pytest.raises(ActionRejected):
            validate_announced_target_references(announced, receipt)
    finally:
        assert (announced, receipt) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', CASES)
def test_real_paid_conditional_frame_rejects_shape_before_pop_without_root_mutation(seat, case):
    state, _, _ = early_path(seat, 'conditional')
    state.stack[-1].payload['__announced_targets'] = deepcopy(CASES[case])
    before = snap(state)
    try:
        with pytest.raises(ActionRejected):
            resolve_top_of_stack(state)
    finally:
        assert snap(state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('empty', [None, {}, [], 0, False])
def test_real_paid_falsy_announcement_control_rejects_mismatched_receipt_immutably(seat, empty):
    state, _, _ = early_path(seat, 'conditional')
    state.stack[-1].payload['__announced_targets'] = deepcopy(empty)
    before = snap(state)
    with pytest.raises(ActionRejected):
        resolve_top_of_stack(state)
    assert snap(state) == before
