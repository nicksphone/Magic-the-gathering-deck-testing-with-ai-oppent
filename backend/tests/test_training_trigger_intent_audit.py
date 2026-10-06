"""Sole rejection expectations; independent canonical trigger-order controls."""
from copy import deepcopy
import json

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases
from training.environment import TrainingEnvironment, decode_action
from tests.test_training_choice_coverage import position, card, cast
from tests.test_training_environment import resolve
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def scenario(seat, reverse=False):
    env = position(seat)
    card(env, 'Soul Warden', seat, Zone.BATTLEFIELD)
    card(env, 'Sol Ring', 3-seat, Zone.BATTLEFIELD)
    sage = card(env, 'Reclamation Sage', seat)
    env.step(cast(env, sage))
    resolve(env)
    hint = next(p['hint'] for p in env.prompts(seat) if p['hint']['type'] == 'choose_trigger_order')
    assert len(hint['trigger_order']) == 2
    order = list(reversed(hint['trigger_order'])) if reverse else list(hint['trigger_order'])
    return env, {'type': 'choose_trigger_order', 'trigger_order': order}, hint


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('key', ['unknown_choice', 'trigger_ids', 'pending_trigger_order', 'action'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_fields_reject_without_normalization(game, seat, key, is_null):
    env, action, _ = scenario(seat)
    alternate = {**action, 'trigger_order': list(reversed(action['trigger_order']))}
    values = {'unknown_choice': True, 'trigger_ids': alternate['trigger_order'],
              'pending_trigger_order': deepcopy(env._state.pending_trigger_order), 'action': alternate}
    request = {**action, key: None if is_null else values[key]}
    original, before = deepcopy(request), env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
    finally:
        assert env.snapshot() == before and request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reverse', [False, True])
def test_independent_whole_views_chosen_order_http_and_restart(game, seat, reverse):
    env, action, hint = scenario(seat, reverse)
    before = env.snapshot()
    accepted = env.lookup(action)
    assert decode_action(accepted['id']) == action
    assert env.lookup_intent({**hint, **action}) == accepted
    replay, fork = TrainingEnvironment(), TrainingEnvironment()
    replay.restore(before)
    fork.restore(before)
    assert replay.step(action) == fork.step(accepted['id'])
    assert replay.snapshot() == fork.snapshot()
    group = env._state.pending_trigger_order['groups'][str(seat)]
    labels = {trigger['_choice_id']: trigger['label'] for trigger in group}
    assert [item.label for item in replay._state.stack] == [labels[cid] for cid in action['trigger_order']]
    assert replay._state.pending_trigger_order['phase'] == 'targets'
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    response = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert response.status_code == 200, response.text
    offered = next(move for move in response.json()['moves']
                   if move['type'] == action['type'] and move['trigger_order'] == action['trigger_order'])
    assert set(offered) == {'type', 'trigger_order', 'trigger_labels', 'event'}
    assert env.lookup_intent(offered) == accepted
    other = client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert other.status_code == 200 and other.json()['moves'] == []
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    restored = restart(identifier)
    assert [item.label for item in restored.state.stack] == [labels[cid] for cid in action['trigger_order']]
    assert restored.state.pending_trigger_order['phase'] == 'targets'
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('bad_kind', ['duplicate', 'stale', 'partial'])
def test_recognized_invalid_orders_reject_atomically(game, seat, bad_kind):
    env, action, _ = scenario(seat)
    order = action['trigger_order']
    bad = {'duplicate': [order[0], order[0]], 'stale': [order[0], 'stale-trigger'], 'partial': order[:1]}
    request = {**action, 'trigger_order': bad[bad_kind]}
    before = env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request)
    client, match = game
    retain(match, env)
    rejected(client, match, request, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_legitimate_order_wrong_seat_rejects(game, seat):
    env, action, _ = scenario(seat)
    before = env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(action, 3-seat)
    client, match = game
    retain(match, env)
    rejected(client, match, action, 3-seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_display_context_cannot_supply_omitted_order(game, seat):
    env, _, hint = scenario(seat)
    request = {key: value for key, value in hint.items() if key != 'trigger_order'}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    client, match = game
    retain(match, env)
    rejected(client, match, request, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
def test_actor_inputs_ignore_opposing_hidden_identity_permutation(seat):
    env, action, hint = scenario(seat)
    assert env.prompts(3-seat) == []
    assert 'prompts' not in env.observe(3-seat)['pending_choice']
    def inputs():
        observation = EpisodeAliases().observation(env.observe(seat))
        text = json.dumps(observation, sort_keys=True)
        assert not any(key in text for key in ('rng_state', 'starting_decks', 'continuation_effects'))
        return json.dumps({'observation': observation, 'prompts': env.prompts(seat)}, sort_keys=True).encode()
    before = inputs()
    for ids in (env._state.players[3-seat].hand, env._state.players[3-seat].library):
        first, second = ids[:2]
        a, b = deepcopy(env._state.cards[first]), deepcopy(env._state.cards[second])
        a.id, b.id = second, first
        env._state.cards[first], env._state.cards[second] = b, a
        ids.reverse()
    assert inputs() == before
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
