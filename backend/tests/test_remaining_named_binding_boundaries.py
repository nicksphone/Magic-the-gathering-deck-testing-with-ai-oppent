"""Non-string inputs retain the existing no-RAW admission boundary."""
from copy import deepcopy

import pytest

from tests.test_remaining_named_binding_scope import _registered, _assert_bypasses_raw


@pytest.mark.parametrize('name', [
    pytest.param(None, id='none'),
    pytest.param(False, id='boolean'),
    pytest.param([], id='list'),
    pytest.param({}, id='mapping'),
])
def test_non_string_names_bypass_raw_without_changing_inputs(name):
    subject, table = _registered()
    before = deepcopy(name)
    _assert_bypasses_raw(subject, table, name)
    assert type(name) is type(before)
    assert name == before
