"""Public combat display is qualified, never a selected-assignment alias."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from tests.test_training_combat_intent_audit import scenario
from tests.test_selected_mana_http import game, retain, rejected, forbid_external_network


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
@pytest.mark.parametrize('field', ['pending_combat', 'player_id', 'effect_controller', 'context'])
@pytest.mark.parametrize('is_null', [False, True])
def test_combat_continuation_context_cannot_be_discarded(game, seat, kind, field, is_null):
    env, action, _, _ = scenario(seat, kind, 'band' if kind == 'attack' else 'cost')
    value = {'active_player': env._state.active_player, 'step': env._state.step.value,
             'unknown_nested_choice': True}
    request = {**action, field: None if is_null else value}
    original, before = deepcopy(request), env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
@pytest.mark.parametrize('form', ['null', 'object_alias', 'nested_unknown', 'nested_null', 'changed_choice'])
def test_known_combat_display_cannot_hide_chosen_or_unknown_fields(game, seat, kind, form):
    env, action, hint, info = scenario(seat, kind, 'ordinary' if kind == 'attack' else 'capacity')
    key = 'defenders' if kind == 'attack' else 'attackers'
    value = deepcopy(hint[key])
    if form == 'null':
        value = None
    elif form == 'object_alias':
        value = {'chosen_ids': info['ids']}
    elif form in {'nested_unknown', 'nested_null'}:
        value[0]['chosen_target'] = None if form == 'nested_null' else info['ids'][0]
    else:
        value = [info['ids'][0]]
    request = {**action, key: value}
    before, original = env.snapshot(), deepcopy(request)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
@pytest.mark.parametrize('is_null', [False, True])
def test_nested_cost_display_is_exact_current_public_metadata(seat, kind, is_null):
    env, action, hint, info = scenario(seat, kind, 'tax' if kind == 'attack' else 'cost')
    key = 'attack_costs' if kind == 'attack' else 'block_costs'
    request = {**hint, **action}
    request[key] = deepcopy(hint[key])
    cost = (request[key][info['ids'][0]][f'player:{3-seat}'] if kind == 'attack' else
            request[key][info['guard']])
    cost['payment_choices'] = None if is_null else {'sacrifice_card_ids': info['ids'][:1]}
    before, original = env.snapshot(), deepcopy(request)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
def test_canonical_metadata_does_not_infer_omitted_assignments(seat, kind):
    env, action, hint, _ = scenario(seat, kind, 'band' if kind == 'attack' else 'capacity')
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(hint)
    request = {**hint, **action}
    del request['attack_targets' if kind == 'attack' else 'blocks']
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    assert env.snapshot() == before
