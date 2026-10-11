"""Private continuation omission does not admit forged whole-view context."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment
from tests.test_fable_optional_linked_discard import episode, snap


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('forged', [None, {
    'effect_key': 'draw_cards', 'payload': {'amount': 99}, 'count_field': 'amount',
}])
def test_absent_private_followup_rejects_explicit_forgery_atomically(seat, forged):
    state, _, _, _, _ = episode(seat)
    env = TrainingEnvironment()
    env._state = state
    before = snap(state)
    view = deepcopy(RulesEngine().legal_moves(state, seat)[0])
    assert 'followup_effect' not in view
    assert state.pending_mechanic_choice['followup_effect']['effect_key'] == 'draw_cards'
    assert state.pending_mechanic_choice['followup_effect']['payload'] == {}
    assert RulesEngine().legal_moves(state, 3-seat) == []
    assert 'followup_effect' not in env.observe(seat)['pending_choice']
    assert 'followup_effect' not in env.observe(3-seat)['pending_choice']
    view['followup_effect'] = deepcopy(forged)
    view['card_ids'] = []
    with pytest.raises(ActionRejected, match='Mechanic view context does not match pending state'):
        env.lookup_intent(view, seat)
    assert snap(state) == before
