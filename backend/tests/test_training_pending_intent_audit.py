"""Two canonical pending-choice families; sole unsupported rejection expectations."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from training.dataset import EpisodeAliases
from training.environment import TrainingEnvironment, decode_action
from tests.test_linked_damage_targets import raw_card
from tests.test_training_choice_coverage import card, cast
from tests.test_training_environment import resolve
from tests.test_training_selected_mana import mana_position
from tests.test_selected_mana_http import game, retain, restart, rejected, forbid_external_network


FAMILIES = ('mechanic', 'optional')


def scenario(seat, family, choose=True):
    env = mana_position(seat)
    selected = card(env, 'Opt', seat)
    untouched = card(env, 'Savannah Lions', seat)
    if family == 'mechanic':
        rows = json.loads((Path(__file__).parent / 'fixtures/discard_history.json').read_text())
        raw = next(row for row in rows if row['name'] == 'Daretti, Scrap Savant')
        source = raw_card(env._state, raw, seat, Zone.BATTLEFIELD)
        assert source.oracle_text == raw['oracle_text'] and source.loyalty == 3
        env.step({'type': 'activate_loyalty', 'card_id': source.id, 'ability_index': 0, 'targets': {}})
        resolve(env)
        assert env._state.pending_mechanic_choice['kind'] == 'discard'
        action = {'type': 'choose_mechanic', 'card_ids': [selected] if choose else []}
        source_id = source.id
        target = None
    else:
        target = card(env, 'Sol Ring', 3-seat, Zone.BATTLEFIELD)
        source_id = card(env, 'Reclamation Sage', seat)
        env.step(cast(env, source_id))
        resolve(env)
        target_hint = next(p['hint'] for p in env.prompts() if p['hint'].get('target_card_id') == target)
        env.step({'type': 'choose_trigger_target', 'stack_id': target_hint['stack_id'], 'target_card_id': target})
        resolve(env)
        assert env._state.pending_trigger_order['phase'] == 'optional'
        action = {'type': 'choose_optional_effect', 'stack_id': env._state.pending_trigger_order['current_stack_id'],
                  'accept': choose}
    hint = next(p['hint'] for p in env.prompts(seat) if p['hint']['type'] == action['type'])
    return env, action, hint, source_id, selected, untouched, target


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('field_kind', ['choice_alias', 'unknown'])
@pytest.mark.parametrize('is_null', [False, True])
def test_unsupported_choice_keys_reject_not_silently_normalize(game, seat, family, field_kind, is_null):
    env, action, _, _, _, untouched, _ = scenario(seat, family)
    key, value = (('unknown_choice', True) if field_kind == 'unknown' else
                  ('selected_card_ids', [untouched]) if family == 'mechanic' else ('choice_id', 'decline'))
    request = {**action, key: None if is_null else value}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    # No accepted unsupported witness or normalized execution precedes this assertion.
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request)
    finally:
        assert env.snapshot() == before


def outcome(state, seat, family, choose, source, selected, untouched, target):
    assert not state.pending_mechanic_choice and not state.pending_trigger_order
    if family == 'mechanic':
        assert state.cards[source].loyalty == 5
        assert state.discards_this_turn[seat] == state.draws_this_turn[seat] == int(choose)
        assert (selected in state.players[seat].graveyard) == choose
        assert untouched in state.players[seat].hand
    else:
        assert (target in state.players[3-seat].graveyard) == choose
        assert (target in state.players[3-seat].battlefield) != choose
        assert source in state.players[seat].battlefield


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('choose', [False, True])
def test_independent_actual_whole_views_execute_explicit_choice_and_restore(game, seat, family, choose):
    env, action, hint, source, selected, untouched, target = scenario(seat, family, choose)
    before = env.snapshot()
    accepted = env.lookup(action)
    assert env.lookup_intent({**hint, **action}) == accepted
    assert decode_action(accepted['id']) == action
    fork, replay = TrainingEnvironment(), TrainingEnvironment()
    fork.restore(before)
    replay.restore(before)
    assert fork.step(accepted['id']) == replay.step(action)
    assert fork.snapshot() == replay.snapshot()
    outcome(fork._state, seat, family, choose, source, selected, untouched, target)
    client, match = game
    identifier = retain(match, env)
    restart(identifier)
    response = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
    assert response.status_code == 200, response.text
    api_hint = next(move for move in response.json()['moves'] if move['type'] == action['type'])
    # Trusted harness compares actual API views; policy observation remains sanitized.
    assert env.lookup_intent({**api_hint, **action}) == accepted
    other = client.get(f'/matches/{identifier}/legal-moves?player_id={3-seat}')
    assert other.status_code == 200 and other.json()['moves'] == []
    response = client.post(f'/matches/{identifier}/action', json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    outcome(restart(identifier).state, seat, family, choose, source, selected, untouched, target)
    assert env.snapshot() == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_recognized_bad_choices_and_wrong_seat_are_atomic(game, seat, family):
    env, action, _, _, selected, _, _ = scenario(seat, family)
    bad = ([{'type': 'choose_mechanic'}, {**action, 'card_ids': [selected, selected]},
            {**action, 'card_ids': ['stale-object']}, {**action, 'choice_id': 'unsupported-second-choice'}]
           if family == 'mechanic' else
           [{'type': 'choose_optional_effect', 'stack_id': action['stack_id']},
            {**action, 'stack_id': 'stale-stack'}, {**action, 'accept': None}, {**action, 'accept': 'false'}])
    before = env.snapshot()
    client, match = game
    retain(match, env)
    for request in bad:
        for lookup in (env.lookup, env.lookup_intent):
            with pytest.raises(ActionRejected):
                lookup(request)
            assert env.snapshot() == before
        rejected(client, match, request, seat)
    for lookup in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            lookup(action, 3-seat)
        assert env.snapshot() == before
    rejected(client, match, action, 3-seat)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_pending_actor_observation_bytes_ignore_opposing_hidden_identity_order(seat, family):
    env, action, hint, _, selected, _, _ = scenario(seat, family)
    assert env.prompts(3-seat) == []
    assert 'prompts' not in env.observe(3-seat)['pending_choice']
    if family == 'mechanic':
        assert selected in env.observe(seat)['known_cards']
        assert selected not in env.observe(3-seat)['known_cards']
    def inputs():
        observation = EpisodeAliases().observation(env.observe(seat))
        assert not any(key in json.dumps(observation) for key in
                       ('continuation_effects', 'rng_state', 'starting_decks', 'seed'))
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
