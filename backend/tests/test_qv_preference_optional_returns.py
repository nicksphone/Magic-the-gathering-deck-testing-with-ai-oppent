"""A known preference need not have an observed terminal value target."""
from copy import deepcopy

import pytest

from scripts.train_qv_preferences import validate_preferences
from tests.test_qv_preference_training import preference
from tests.test_learned_qv import contract


def test_preference_without_observed_return_is_valid_and_not_filled_in():
    row = preference()
    del row['return']
    before = deepcopy(row)
    validate_preferences([row], contract=contract())
    assert row == before and 'return' not in row


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), 2.0])
def test_provided_value_target_must_still_be_an_actual_finite_return(value):
    row = preference()
    row['return'] = value
    with pytest.raises(ValueError):
        validate_preferences([row], contract=contract())
