"""Combat consumer audit: sole unsupported rejection, independent valid actions."""
from copy import deepcopy
import json

import pytest

from game_state.state import Step, Zone
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases
from training.environment import TrainingEnvironment, decode_action
from tests.test_training_choice_coverage import position
from tests.test_combat_domain_temporary_costs import add, activate, zero_mana
from tests.test_ai_combat_intents import ROWS, raw_add
from tests.test_declaration_limits import add as limit_card, attack_step
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


CASES = [('attack', 'ordinary'), ('attack', 'band'), ('attack', 'tax'),
         ('block', 'ordinary'), ('block', 'capacity'), ('block', 'cost')]


def scenario(seat, kind, family):
    env = position(seat)
    state = env._state
    zero_mana(state)
    state.turn = 5
    active = seat if kind == 'attack' else 3-seat
    if family == 'band':
        creatures = [raw_add(state, name, active, cards=ROWS)
                     for name in ('Benalish Hero', 'Invisible Stalker')]
    else:
        creatures = [add(state, 'Grizzly Bears', active) for _ in range(2)]
    ids = [c.id for c in creatures]
    for creature in creatures:
        creature.summoning_sick = False
    info = {'ids': ids, 'active': active, 'family': family, 'kind': kind}
    if kind == 'attack':
        attack_step(state, seat)
        targets = {cid: f'player:{3-seat}' for cid in ids}
        if family == 'ordinary':
            walker = limit_card(state, 'Ugin, the Spirit Dragon', 3-seat)
            walker.loyalty = 7
            targets[ids[1]] = f'planeswalker:{walker.id}'
            info['walker'] = walker.id
        if family == 'tax':
            add(state, 'Propaganda', 3-seat)
            state.players[seat].mana_pool['U'] = 4
        action = {'type': 'attack', 'attackers': ids, 'attack_targets': targets}
        if family == 'band':
            action['bands'] = [ids]
    else:
        if family == 'cost':
            env._state, _ = activate(state, 'War Cadence', active, 1)
            state = env._state
            state.players[seat].mana_pool['W'] = 1
        guard = add(state, 'Grizzly Bears' if family == 'ordinary' else 'Wall of Glare', seat)
        state.active_player, state.priority_player = active, seat
        state.step = Step.DECLARE_BLOCKERS
        state.attackers = ids
        state.attack_targets = {cid: f'player:{seat}' for cid in ids}
        state.attackers_declared = True
        for cid in ids:
            state.cards[cid].tapped = True
        groups = {cid: [guard.id] for cid in (ids[:1] if family == 'ordinary' else ids)}
        action = {'type': 'block', 'blocks': groups}
        info['guard'] = guard.id
    state.passed_priority = set()
    hint = next(m for m in env._rules.legal_moves(deepcopy(state), seat) if m['type'] == kind)
    return env, action, hint, info


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['attack', 'block'])
@pytest.mark.parametrize('field', ['unknown_choice', 'targets', 'payment_choices', 'defender_id'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_top_level_combat_requests_reject(game, seat, kind, field, is_null):
    env, action, _, info = scenario(seat, kind, 'band' if kind == 'attack' else 'cost')
    values = {'unknown_choice': True, 'targets': {'target_player': seat},
              'payment_choices': {'sacrifice_card_ids': info['ids'][:1]},
              'defender_id': f'player:{seat}'}
    request = {**action, field: None if is_null else values[field]}
    before, original = env.snapshot(), deepcopy(request)
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
@pytest.mark.parametrize('kind', ['attack', 'block'])
@pytest.mark.parametrize('form', ['nested_alias', 'nested_null', 'null_value', 'duplicate'])
def test_malformed_nested_chosen_assignments_reject_atomically(game, seat, kind, form):
    env, action, _, info = scenario(seat, kind, 'band' if kind == 'attack' else 'capacity')
    request = deepcopy(action)
    if kind == 'attack':
        if form == 'duplicate':
            request['bands'] = [[info['ids'][0], info['ids'][0]]]
        else:
            request['attack_targets'][info['ids'][0]] = (
                None if form == 'null_value' else
                {'defender_id': None if form == 'nested_null' else f'player:{3-seat}'})
    elif form == 'duplicate':
        request['blocks'][info['ids'][0]] = [info['guard'], info['guard']]
    else:
        request['blocks'][info['ids'][0]] = (
            None if form == 'null_value' else
            {'blocker_ids': None if form == 'nested_null' else [info['guard']]})
    before, original = env.snapshot(), deepcopy(request)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    assert env.snapshot() == before and request == original


def assert_assignment(state, seat, action, info):
    if action['type'] == 'attack':
        assert state.attackers == action['attackers']
        assert state.attack_targets == action['attack_targets']
        assert state.attack_bands == action.get('bands', [])
        if info['family'] == 'tax':
            assert state.players[seat].mana_pool['U'] == 0
    else:
        assert state.blocks == action['blocks']
        if info['family'] == 'cost':
            assert state.players[seat].mana_pool['W'] == 0


def finish(env):
    for _ in range(16):
        state = env._state
        if state.step == Step.END_COMBAT:
            return
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        if state.step == Step.DECLARE_BLOCKERS and not state.blockers_declared:
            env.step({'type': 'block', 'blocks': {}})
        else:
            env.step({'type': 'pass_priority'})
    raise AssertionError('Bounded combat did not reach end combat')


def assert_outcome(state, seat, info):
    if info['kind'] == 'attack':
        damage = 2 if info['family'] == 'band' else 4
        if info['family'] == 'ordinary':
            damage = 2
            assert state.cards[info['walker']].loyalty == 5
        assert state.players[3-seat].life == 20-damage
    elif info['family'] == 'ordinary':
        assert state.players[seat].life == 18
        assert state.cards[info['guard']].zone == Zone.GRAVEYARD
        assert state.cards[info['ids'][0]].zone == Zone.GRAVEYARD
        assert state.cards[info['ids'][1]].zone == Zone.BATTLEFIELD
    else:
        assert state.players[seat].life == 20
        assert state.cards[info['guard']].zone == Zone.BATTLEFIELD
        assert state.cards[info['guard']].counters['__damage_marked'] == 4


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,family', CASES)
def test_independent_whole_views_exact_choices_http_resolution_restart(game, seat, kind, family):
    env, action, hint, info = scenario(seat, kind, family)
    before, original = env.snapshot(), deepcopy(action)
    accepted = env.lookup(action)
    decoded = decode_action(accepted['id'])
    assert all(decoded[key] == value for key, value in action.items())
    assert env.lookup_intent({**hint, **action}) == accepted
    fork, replay = TrainingEnvironment(), TrainingEnvironment()
    fork.restore(before)
    replay.restore(before)
    assert fork.step(accepted['id']) == replay.step(action)
    assert fork.snapshot() == replay.snapshot()
    assert_assignment(fork._state, seat, action, info)
    finish(fork)
    assert_outcome(fork._state, seat, info)
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    response = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert response.status_code == 200, response.text
    whole = next(move for move in response.json()['moves'] if move['type'] == kind)
    assert env.lookup_intent({**whole, **action}) == accepted
    assert rejected(client, match, action, 3-seat).status_code in (403, 422)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    assert_assignment(restart(identifier).state, seat, action, info)
    for _ in range(16):
        current = restart(identifier)
        state = current.state
        if state.step == Step.END_COMBAT:
            break
        assert not state.pending_mechanic_choice and not state.pending_trigger_order
        chosen = ({'type': 'block', 'blocks': {}} if state.step == Step.DECLARE_BLOCKERS
                  and not state.blockers_declared else {'type': 'pass_priority'})
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': state.priority_player, 'action': chosen})
        assert response.status_code == 200, response.text
    else:
        raise AssertionError('HTTP combat did not complete within bound')
    assert_outcome(restart(identifier).state, seat, info)
    assert env.snapshot() == before and action == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind,family', CASES)
def test_combat_actor_input_ignores_opposing_hidden_identity_order(seat, kind, family):
    env, action, hint, _ = scenario(seat, kind, family)
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
