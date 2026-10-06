"""Pending views cannot override continuations or infer authoritative choices."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_pending_intent_audit import scenario


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('key', ['player_id', 'effect_controller', 'followup_effect', 'resolving_item'])
@pytest.mark.parametrize('value', [None, {'type': 'choose_mechanic', 'card_ids': ['foreign-choice']}])
def test_context_tampering_rejects_before_normalizer(monkeypatch, seat, key, value):
    env, action, _, *_ = scenario(seat, 'mechanic')
    before = env.snapshot()
    request = {**action, key: value}
    original = deepcopy(request)
    def forbidden(_):
        pytest.fail('Invalid context reached normalization')
    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, seat)
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
def test_whole_context_exact_no_inferred_discard_and_nested_override(seat):
    env, action, hint, *_ = scenario(seat, 'mechanic')
    pending = deepcopy(env._state.pending_mechanic_choice)
    context = {key: pending[key] for key in
               ('player_id', 'effect_controller', 'followup_effect', 'resolving_item')}
    before = env.snapshot()
    request = {**hint, **context, **action}
    original = deepcopy(request)
    assert env.lookup_intent(request) == env.lookup(action)
    assert request == original and env.snapshot() == before
    with pytest.raises(ActionRejected):
        env.lookup_intent({**hint, **context})
    request['resolving_item']['payload']['card_ids'] = action['card_ids']
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['mechanic', 'optional'])
def test_context_without_matching_pending_actor_rejects(seat, family):
    env, action, _, *_ = scenario(seat, family)
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent({**action, 'player_id': seat}, 3-seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_context_integer_bool_not_interchangeable(seat):
    env, action, _, *_ = scenario(seat, 'mechanic')
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent({**action, 'player_id': True})
    assert env.snapshot() == before
