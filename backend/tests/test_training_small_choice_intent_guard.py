"""Typed choices survive metadata; continuation context is never authoritative."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from training.environment import decode_action
from tests.test_training_small_choice_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('key', ['event', 'replacement_name'])
@pytest.mark.parametrize('bad_kind', ['null', 'nested', 'array', 'boolean', 'empty'])
def test_replacement_metadata_cannot_hide_nested_choice(game, seat, key, bad_kind):
    env, action, hint, info = scenario(seat, 'replacement')
    nested = {**action, 'replacement_source_id': info['alternate']}
    values = {'null': None, 'nested': nested, 'array': [nested], 'boolean': True, 'empty': ''}
    request = {**hint, key: values[bad_kind]}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ActionRejected, match='Replacement metadata must be a display string'):
        env.lookup_intent(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad_kind', ['null', 'nested', 'array', 'boolean', 'empty'])
def test_actual_api_target_name_is_display_not_a_nested_choice(game, seat, bad_kind):
    env, action, _, info = scenario(seat, 'target')
    nested = {**action, 'target_card_id': info['alternate']}
    values = {'null': None, 'nested': nested, 'array': [nested], 'boolean': True, 'empty': ''}
    request = {**action, 'target_name': values[bad_kind]}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ActionRejected, match='Trigger target name must be a display string'):
        env.lookup_intent(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['replacement', 'target'])
def test_exact_pending_context_is_rejected_not_silently_discarded(game, seat, family):
    env, action, _, _ = scenario(seat, family)
    context = 'pending_replacement_choice' if family == 'replacement' else 'pending_trigger_order'
    before = env.snapshot()
    for extra in ({context: deepcopy(getattr(env._state, context))},
                  {'action': deepcopy(action)}, {'resolving_item': None},
                  {'context': {'action': deepcopy(action)}}):
        request = {**action, **extra}
        original = deepcopy(request)
        with pytest.raises(ActionRejected, match='contract cannot carry requested fields'):
            env.lookup_intent(request)
        with pytest.raises(ActionRejected):
            env.lookup(request)
        client, match = game
        retain(match, env)
        assert rejected(client, match, request, seat).status_code == 422
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
def test_recognized_nullable_target_alternative_preserves_deliberate_card_choice(seat):
    env, action, hint, _ = scenario(seat, 'target', choice=1)
    before = env.snapshot()
    intent = {**hint, 'target_player': None}
    original = deepcopy(intent)
    accepted = env.lookup_intent(intent)
    assert accepted == env.lookup(action)
    assert decode_action(accepted['id']) == action
    assert intent == original and env.snapshot() == before
    for request in ({**action, 'target_player': 3-seat},
                    {'type': action['type'], 'stack_id': action['stack_id'], 'target_player': None}):
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['replacement', 'target'])
def test_no_chosen_source_or_target_is_inferred_from_context(seat, family):
    env, action, hint, _ = scenario(seat, family)
    key = 'replacement_source_id' if family == 'replacement' else 'target_card_id'
    before = env.snapshot()
    missing = {k: v for k, v in hint.items() if k != key}
    for request in (missing, {**missing, 'action': action}):
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
        assert env.snapshot() == before
