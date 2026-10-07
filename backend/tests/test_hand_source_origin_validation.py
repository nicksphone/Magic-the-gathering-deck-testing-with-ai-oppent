"""Native producer-origin protocol corruption, not legal new activation domains."""
import pytest
from rules_engine.action_validation import ActionRejected
from rules_engine.stack_engine import resolve_top_of_stack
from tests.test_hand_source_context_product import announced, snapshot


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('origin', [[], {}])
@pytest.mark.parametrize('context_present', [False, True])
def test_malformed_native_origin_rejects_structurally_before_pop(seat, origin, context_present):
    state, _, _, _, frame, _ = announced(seat)
    item = next(item for item in state.stack if item.id == frame)
    item.payload['__activation_source_origin'] = origin
    if not context_present:
        del item.payload['__activation_source_context']
    before = snapshot(state)
    with pytest.raises(ActionRejected): resolve_top_of_stack(state)
    assert snapshot(state) == before
