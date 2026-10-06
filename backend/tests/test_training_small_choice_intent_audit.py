"""Replacement/trigger-target consumer audit; independent deliberate choices."""
from copy import deepcopy
import json

import pytest

from effects.handlers import add_counters
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases
from training.environment import TrainingEnvironment, decode_action
from tests.test_training_choice_coverage import position, card, cast
from tests.test_training_environment import resolve
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


FAMILIES = ('replacement', 'target')


def scenario(seat, family, choice=0):
    env = position(seat)
    if family == 'replacement':
        target = card(env, 'Grizzly Bears', seat, Zone.BATTLEFIELD)
        card(env, 'Hardened Scales', seat, Zone.BATTLEFIELD)
        card(env, 'Doubling Season', seat, Zone.BATTLEFIELD)
        # Retained actual effect boundary, using unmodified canonical card fields.
        add_counters(env._state, seat, {'target_card_id': target, 'amount': 1})
        hints = [p['hint'] for p in env.prompts(seat) if p['hint']['type'] == 'choose_replacement']
        assert [h['replacement_name'] for h in hints] == ['Hardened Scales', 'Doubling Season']
        hint = hints[choice]
        action = {'type': hint['type'], 'replacement_source_id': hint['replacement_source_id']}
        info = {'target': target, 'count': 4 if choice == 0 else 3,
                'alternate': hints[1-choice]['replacement_source_id']}
        assert env._state.pending_replacement_choice['player_id'] == seat
    else:
        targets = [card(env, 'Sol Ring', owner, Zone.BATTLEFIELD) for owner in (seat, 3-seat)]
        sage = card(env, 'Reclamation Sage', seat)
        env.step(cast(env, sage))
        resolve(env)
        hint = next(p['hint'] for p in env.prompts(seat)
                    if p['hint'].get('target_card_id') == targets[choice])
        action = {'type': hint['type'], 'stack_id': hint['stack_id'], 'target_card_id': targets[choice]}
        info = {'target': targets[choice], 'other': targets[1-choice], 'alternate': targets[1-choice]}
        assert env._state.pending_trigger_order['current_controller'] == seat
    return env, action, hint, info


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('field_kind', ['unknown', 'alias', 'context'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_requested_fields_reject_before_normalization(game, seat, family, field_kind, is_null):
    env, action, _, info = scenario(seat, family)
    context = 'pending_replacement_choice' if family == 'replacement' else 'pending_trigger_order'
    if field_kind == 'unknown':
        key, value = 'unknown_choice', True
    elif field_kind == 'context':
        key, value = context, deepcopy(getattr(env._state, context))
    else:
        key, value = (('source_id', info['alternate']) if family == 'replacement' else
                      ('targets', {'target_card_id': info['alternate']}))
    request = {**action, key: None if is_null else value}
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


def finish(env, family):
    if family == 'target':
        resolve(env)
        hint = next(p['hint'] for p in env.prompts() if p['hint']['type'] == 'choose_optional_effect')
        env.step({'type': 'choose_optional_effect', 'stack_id': hint['stack_id'], 'accept': True})


def outcome(state, seat, family, info):
    assert not state.pending_replacement_choice and not state.pending_trigger_order
    if family == 'replacement':
        assert state.cards[info['target']].counters['+1/+1'] == info['count']
    else:
        chosen = state.cards[info['target']]
        assert info['target'] in state.players[chosen.owner].graveyard
        other = state.cards[info['other']]
        assert info['other'] in state.players[other.owner].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('choice', [0, 1])
def test_independent_deliberate_whole_views_execute_and_restart(game, seat, family, choice):
    env, action, hint, info = scenario(seat, family, choice)
    before = env.snapshot()
    accepted = env.lookup(action)
    assert decode_action(accepted['id']) == action
    assert env.lookup_intent(hint) == accepted
    fork, replay = TrainingEnvironment(), TrainingEnvironment()
    fork.restore(before)
    replay.restore(before)
    assert fork.step(accepted['id']) == replay.step(action)
    assert fork.snapshot() == replay.snapshot()
    finish(fork, family)
    outcome(fork._state, seat, family, info)
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    response = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert response.status_code == 200, response.text
    offered = next(move for move in response.json()['moves']
                   if move['type'] == action['type'] and all(move.get(k) == v for k, v in action.items()))
    assert env.lookup_intent(offered) == accepted
    other = client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert other.status_code == 200 and other.json()['moves'] == []
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    if family == 'target':
        for _ in range(2):
            current = restart(identifier)
            response = client.post(f'/matches/{identifier}/action', json={
                'player_id': current.state.priority_player, 'action': {'type': 'pass_priority'}})
            assert response.status_code == 200, response.text
        current = restart(identifier)
        response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': {
            'type': 'choose_optional_effect', 'stack_id': current.state.pending_trigger_order['current_stack_id'],
            'accept': True}})
        assert response.status_code == 200, response.text
    outcome(restart(identifier).state, seat, family, info)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('bad_kind', ['missing', 'stale'])
def test_recognized_invalid_chosen_values_are_atomic(game, seat, family, bad_kind):
    env, action, _, _ = scenario(seat, family)
    key = 'replacement_source_id' if family == 'replacement' else 'target_card_id'
    bad = {k: v for k, v in action.items() if k != key}
    if bad_kind == 'stale':
        bad[key] = 'stale-choice'
    before = env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(bad)
    client, match = game
    retain(match, env)
    rejected(client, match, bad, seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_other_pending_controller_cannot_choose(game, seat, family):
    env, action, _, _ = scenario(seat, family)
    before = env.snapshot()
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(action, 3-seat)
    client, match = game
    retain(match, env)
    rejected(client, match, action, 3-seat)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_actor_input_bytes_ignore_opposing_private_identity_order(seat, family):
    env, action, hint, _ = scenario(seat, family)
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
    assert env.lookup_intent(hint) == env.lookup(action)
