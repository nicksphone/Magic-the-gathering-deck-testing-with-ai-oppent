"""Trusted CI fixture setup must publish native kinds, not infer from card zones."""
import pytest

from rules_engine.targeting import stack_object_kind
from tests.modal_contract_support import canonical_fixture


@pytest.mark.parametrize(('face_kind', 'kind'), [
    ('copy_target', 'spell'), ('divided_copy_target', 'spell'),
    ('modal_copy_target', 'spell'), ('modal_two_targets', 'spell'),
    ('counter_payment_1', 'activated'), ('counter_payment_2', 'activated'),
])
def test_browser_fixture_publishes_explicit_native_frames(face_kind, kind):
    state = canonical_fixture(face_kind)
    assert state.stack
    assert all(stack_object_kind(state, item) == kind for item in state.stack)
    if face_kind.endswith('copy_target'):
        assert len(state.stack) == 2
        assert state.pending_mechanic_choice['kind'] == 'copy_target'
        assert state.pending_mechanic_choice['stack_id'] == state.stack[-1].id
        assert state.pending_mechanic_choice['player_id'] == state.stack[-1].controller
