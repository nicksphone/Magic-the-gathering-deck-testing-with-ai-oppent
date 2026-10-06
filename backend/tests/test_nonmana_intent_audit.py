"""Non-mana guard acceptance; immutable historical witnesses are archived separately."""
from copy import deepcopy
import json

import pytest

from ai.action_contract import complete_action
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.environment import TrainingEnvironment, decode_action
from training.dataset import EpisodeAliases
from tests.test_training_selected_mana import mana_position
from tests.test_training_choice_coverage import card, cast
from tests.test_training_environment import resolve
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


def scenario(seat, family):
    env = mana_position(seat)
    env._state.players[seat].mana_pool = {color: 20 for color in 'WUBRGC'}
    visible_target = card(env, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    if family == 'spell':
        cid = card(env, 'Lightning Bolt', seat)
        action = cast(env, cid, {'target_player': 3-seat})
        top = []
    else:
        cid = card(env, 'Recruitment Officer', seat, Zone.BATTLEFIELD)
        top = [card(env, name, seat, Zone.LIBRARY) for name in
               ('Serra Angel', 'Opt', 'Savannah Lions', 'Serra Angel')]
        action = {'type': 'activate_ability', 'card_id': cid, 'ability_index': 0, 'targets': {}}
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == action['type'] and move['card_id'] == cid)
    return env, action, hint, visible_target, top


def trusted_execution(env, action, family, visible_target, top):
    fork = TrainingEnvironment()
    fork.restore(env.snapshot())
    seat = fork.acting_seat
    fork.step(action)
    assert fork._state.stack[-1].source_card_id == action['card_id']
    resolve(fork)
    if family == 'spell':
        assert fork._state.players[3-seat].life == 17
        assert not fork._state.cards[visible_target].counters.get('__damage_marked', 0)
        assert action['card_id'] in fork._state.players[seat].graveyard
    else:
        own = fork.observe(seat)
        other = fork.observe(3-seat)
        assert set(top).issubset(own['known_cards'])
        assert not set(top).intersection(other['known_cards'])
        assert 'prompts' not in other['pending_choice']
        assert fork.prompts(3-seat) == []
        assert not any(key in json.dumps(own['pending_choice']) for key in
                       ('continuation', 'rng_state', 'starting_decks'))
        eligible = next(cid for cid in top if fork._state.cards[cid].name == 'Savannah Lions')
        fork.step({'type': 'choose_mechanic', 'card_ids': [eligible]})
        assert eligible in fork._state.players[seat].hand
        assert not fork._state.pending_mechanic_choice


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
@pytest.mark.parametrize('choice', ['target', 'cost', 'zone', 'face'])
def test_requested_nonmana_choices_must_reject_not_transform_action(game, seat, family, choice):
    env, action, hint, target, top = scenario(seat, family)
    field, value = {
        'target': ('target_card_id', target),
        'cost': ('payment_choices', {'discard_card_ids': [action['card_id']]}) if family == 'spell' else
                ('cost_choice', {'id': 'unoffered-cost'}),
        'zone': ('source_zone', 'graveyard'),
        'face': ('face_index', 19),
    }[choice]
    request = {**action, field: value}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    identifier = retain(match, env)
    rejected(client, match, request, seat)
    # Independently declared canonical action, never derived by stripping request.
    accepted = env.lookup(action)
    assert env.lookup_intent(action) == accepted
    normalized = decode_action(accepted['id'])
    assert field not in normalized
    assert env.snapshot() == before
    trusted_execution(env, normalized, family, target, top)
    assert env.snapshot() == before
    # Actual HTTP executes the independently chosen valid action.
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': normalized})
    assert response.status_code == 200, response.text
    assert restart(identifier).state.stack[-1].source_card_id == action['card_id']
    # The unsupported request still must reject, including after valid controls.
    with pytest.raises(ActionRejected):
        env.lookup_intent(request)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
def test_actual_whole_move_display_metadata_preserves_selected_parameters(game, seat, family):
    env, action, hint, target, top = scenario(seat, family)
    before = env.snapshot()
    intent = {**hint, **action}
    assert env.lookup_intent(intent) == env.lookup(action)
    assert env.snapshot() == before
    trusted_execution(env, decode_action(env.lookup_intent(intent)['id']), family, target, top)
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
def test_recognized_authoritative_parameters_are_retained_and_checked(game, seat, family):
    env, action, _, _, _ = scenario(seat, family)
    bad_actions = ([{**action, 'cost_choice': {'id': 'unoffered-cost'}},
                    {**action, 'from_graveyard': True}, {**action, 'selected_face_index': 19},
                    {**action, 'targets': {'target_player': 99}}] if family == 'spell' else
                   [{**action, 'ability_index': 99}, {**action, 'payment_choices': {'sacrifice_card_ids': [action['card_id']]}},
                    {**action, 'targets': {'target_player': 99}}])
    before = env.snapshot()
    client, match = game
    retain(match, env)
    for bad in bad_actions:
        with pytest.raises(ActionRejected):
            env.lookup(bad)
        with pytest.raises(ActionRejected):
            env.lookup_intent(bad)
        rejected(client, match, bad, seat)
        assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['spell', 'ability'])
def test_actor_private_bytes_unchanged_by_opposing_hidden_identity_permutation(seat, family):
    env, action, hint, _, _ = scenario(seat, family)
    def inputs():
        aliases = EpisodeAliases()
        observation = aliases.observation(env.observe(seat))
        return json.dumps({'observation': observation, 'action': aliases.action(action, seat),
                           'prompts': env.prompts(seat)}, sort_keys=True).encode()
    before = inputs()
    for ids in (env._state.players[3-seat].hand, env._state.players[3-seat].library):
        first, second = ids[:2]
        a, b = deepcopy(env._state.cards[first]), deepcopy(env._state.cards[second])
        a.id, b.id = second, first
        env._state.cards[first], env._state.cards[second] = b, a
        ids.reverse()
    assert inputs() == before
    assert env.lookup_intent({**hint, **action}) == env.lookup(action)
    assert env.prompts(3-seat) == []
