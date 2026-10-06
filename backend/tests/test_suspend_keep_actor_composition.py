"""Current composition: actor validation precedes the newly guarded families."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_intent_actor_prevalidation import BAD, IDS, watch_helpers
from tests.test_training_keep_hand_intent_audit import opening
from tests.test_training_suspend_intent_audit import isolated_source, suspend_position


def position(family, seat):
    return suspend_position(seat) if family == 'suspend' else opening(seat, True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['suspend', 'keep_hand'])
@pytest.mark.parametrize('actor', BAD, ids=IDS)
def test_new_families_reject_invalid_actor_before_helpers(monkeypatch, seat, family, actor):
    env, action = position(family, seat)
    before, original = env.snapshot(), deepcopy(action)
    calls = watch_helpers(monkeypatch, env)
    with pytest.raises(ActionRejected, match='Seat must be integer 1 or 2'):
        env.lookup_intent(action, actor)
    assert not calls and env.snapshot() == before and action == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['suspend', 'keep_hand'])
def test_new_families_keep_default_and_explicit_actor_equivalence(seat, family):
    env, action = position(family, seat)
    before = env.snapshot()
    expected = env.lookup(action, seat)
    assert env.lookup_intent(action) == env.lookup_intent(action, None) == expected
    assert env.lookup_intent(action, seat) == expected
    with pytest.raises(ActionRejected):
        env.lookup_intent(action, 3-seat)
    assert env.snapshot() == before
