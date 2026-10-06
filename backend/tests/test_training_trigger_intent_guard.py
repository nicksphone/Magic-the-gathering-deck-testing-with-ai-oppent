"""Strict trigger presentation shapes cannot hide a nested authoritative choice."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from training.environment import decode_action
from tests.test_training_trigger_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('key', ['trigger_labels', 'event'])
@pytest.mark.parametrize('malformed', ['null', 'object', 'nested_list', 'wrong_scalar', 'empty'])
def test_malformed_display_or_nested_choice_rejects(game, seat, key, malformed):
    env, action, hint = scenario(seat)
    alternate = {**action, 'trigger_order': list(reversed(action['trigger_order']))}
    values = {'null': None, 'object': alternate, 'nested_list': [alternate],
              'wrong_scalar': True, 'empty': [] if key == 'trigger_labels' else ''}
    request = {**hint, **action, key: values[malformed]}
    original, before = deepcopy(request), env.snapshot()
    with pytest.raises(ActionRejected, match='must be a display'):
        env.lookup_intent(request)
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert request == original and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_order_is_never_derived_from_display_or_root_context(seat):
    env, action, hint = scenario(seat)
    before = env.snapshot()
    display_only = {key: value for key, value in hint.items() if key != 'trigger_order'}
    for request in (display_only, {**display_only, 'action': action},
                    {**display_only, 'pending_trigger_order': deepcopy(env._state.pending_trigger_order)}):
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_display_labels_do_not_override_explicit_reversed_order(seat):
    env, action, hint = scenario(seat, reverse=True)
    original, before = deepcopy(hint), env.snapshot()
    accepted = env.lookup_intent({**hint, **action})
    assert decode_action(accepted['id']) == action
    assert hint == original and env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_uninterpreted_root_context_rejects_before_completion(seat):
    env, action, _, = scenario(seat)
    before = env.snapshot()
    for request in ({**action, 'resolving_item': None},
                    {**action, 'context': {'action': action}},
                    {**action, 'player_id': seat}):
        with pytest.raises(ActionRejected, match='Trigger order contract cannot carry requested fields'):
            env.lookup_intent(request)
        assert env.snapshot() == before
