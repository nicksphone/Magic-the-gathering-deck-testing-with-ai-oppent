"""Unsupported-null rejection and independently declared valid execution controls."""
from copy import deepcopy

import pytest

from rules_engine.action_validation import ActionRejected
from game_state.state import Zone
from training.environment import TrainingEnvironment, decode_action
from tests.test_nonmana_intent_audit import scenario, trusted_execution
from tests.test_training_selected_mana import mana_position
from tests.test_training_choice_coverage import card, cast
from tests.test_training_environment import resolve
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def execute_http(client, match, env, action):
    """Actual accepted action plus two priority passes, with DB restore each time."""
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={
        'player_id': env.acting_seat, 'action': action})
    assert response.status_code == 200, response.text
    restored = restart(identifier)
    assert restored.state.stack[-1].source_card_id == action['card_id']
    for _ in range(2):
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': restored.state.priority_player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
        restored = restart(identifier)
    return restored.state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('choice', ['target', 'cost', 'zone', 'face'])
def test_unsupported_requested_null_is_not_permission_to_drop_field(game, seat, family, choice):
    env, action, _, target, top = scenario(seat, family)
    field = {'target': 'target_card_id', 'zone': 'source_zone', 'face': 'face_index',
             'cost': 'payment_choices' if family == 'spell' else 'cost_choice'}[choice]
    request = {**action, field: None}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    rejected(client, match, request, seat)
    # This action is declared by the canonical fixture, not normalized from request.
    accepted = env.lookup(action)
    normalized = decode_action(accepted['id'])
    assert env.lookup_intent(action) == accepted
    assert field not in normalized
    assert env.snapshot() == before
    trusted_execution(env, normalized, family, target, top)
    execute_http(client, match, env, normalized)
    assert env.snapshot() == before
    # The key is outside this action's schema, regardless of its null value.
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('target_kind', ['player', 'creature'])
def test_supported_nested_bolt_target_changes_actual_execution(game, seat, target_kind):
    env, action, hint, creature, _ = scenario(seat, 'spell')
    targets = ({'target_player': 3-seat} if target_kind == 'player' else
               {'target_card_id': creature})
    action = {**action, 'targets': targets}
    before = env.snapshot()
    normalized = decode_action(env.lookup_intent({**hint, **action})['id'])
    assert normalized == decode_action(env.lookup(action)['id'])
    assert normalized['targets'] == targets
    assert normalized['cost_choice'] == action['cost_choice']
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    fork = TrainingEnvironment()
    fork.restore(before)
    fork.step(normalized)
    resolve(fork)
    client, match = game
    state = execute_http(client, match, env, normalized)
    for executed in (fork._state, state):
        assert executed.players[3-seat].life == (17 if target_kind == 'player' else 20)
        assert (creature in executed.players[3-seat].graveyard) == (target_kind == 'creature')
        assert action['card_id'] in executed.players[seat].graveyard
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_supported_nested_x_and_typed_discard_choice_execute_selected_card(game, seat):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    source = card(env, 'Sickening Dreams', seat)
    selected = card(env, 'Opt', seat)
    untouched = card(env, 'Savannah Lions', seat)
    action = cast(env, source, {'x_value': 1})
    action['cost_choice']['discard_card_ids'] = [selected]
    before = env.snapshot()
    normalized = decode_action(env.lookup_intent(deepcopy(action))['id'])
    assert normalized == decode_action(env.lookup(action)['id'])
    assert normalized['targets'] == {'x_value': 1}
    assert normalized['cost_choice'] == action['cost_choice']
    assert env.lookup_intent(action) == env.lookup(action)
    fork = TrainingEnvironment()
    fork.restore(before)
    fork.step(normalized)
    resolve(fork)
    client, match = game
    state = execute_http(client, match, env, normalized)
    for executed in (fork._state, state):
        assert selected in executed.players[seat].graveyard
        assert untouched in executed.players[seat].hand
        assert [executed.players[p].life for p in (1, 2)] == [19, 19]
        assert source in executed.players[seat].graveyard
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('bad_targets', [None, {'unknown_choice': None}])
def test_nested_invalid_null_is_checked_not_reinterpreted(game, seat, family, bad_targets):
    env, action, _, _, _ = scenario(seat, family)
    bad = {**action, 'targets': bad_targets}
    before = env.snapshot()
    client, match = game
    retain(match, env)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(bad)
        assert env.snapshot() == before
    rejected(client, match, bad, seat)
