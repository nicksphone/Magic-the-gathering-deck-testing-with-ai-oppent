"""Mulligan guards preserve the current candidate's actor-first boundary."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_intent_actor_prevalidation import BAD, IDS, watch_helpers
from tests.test_training_keep_hand_intent_audit import opening
from tests.test_training_suspend_intent_audit import isolated_source


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('actor', BAD, ids=IDS)
def test_mulligan_invalid_actor_rejects_before_helpers(monkeypatch, seat, actor):
    env, _ = opening(seat)
    request = {'type': 'mulligan', 'current_mulligans': 0}
    before, original = env.snapshot(), deepcopy(request)
    calls = watch_helpers(monkeypatch, env)
    with pytest.raises(ActionRejected, match='Seat must be integer 1 or 2'):
        env.lookup_intent(request, actor)
    assert not calls and env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
def test_mulligan_default_and_explicit_actor_equivalence(seat):
    env, _ = opening(seat)
    before = env.snapshot()
    expected = env.lookup({'type': 'mulligan'}, seat)
    request = {'type': 'mulligan', 'current_mulligans': 0}
    assert env.lookup_intent(request) == env.lookup_intent(request, None) == expected
    assert env.lookup_intent(request, seat) == expected
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, 3-seat)
    assert env.snapshot() == before
