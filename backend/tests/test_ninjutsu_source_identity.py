"""Canonical source references; zone changes below are controlled, not spell claims."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from card_data.fallback_cards import fallback_card_payload
from game_state.state import Zone
from training.environment import TrainingEnvironment
from tests.test_linked_damage_targets import raw_card
from tests.test_selected_mana_http import game, retain, restart, forbid_external_network
from tests.test_training_choice_coverage import position
from tests.test_training_environment import resolve
from tests.test_training_ninjutsu_intent_audit import scenario, assert_activation


def relocate(state, cid, destination):
    card = state.cards[cid]
    getattr(state.players[card.owner], card.zone.value).remove(cid)
    card.move_to_zone(destination)
    getattr(state.players[card.owner], destination.value).append(cid)


def http_resolve(client, identifier):
    for _ in range(2):
        controller = restart(identifier)
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': controller.state.priority_player,
            'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    return restart(identifier).state


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('movement', ['unchanged', 'exiled', 'reentered'])
@pytest.mark.parametrize('via_http', [False, True])
def test_paid_reference_survives_replay_and_controlled_departure(
        game, tmp_path, seat, movement, via_http):
    env, action, _, info = scenario(seat)
    original = env.snapshot()
    client, match = game
    if via_http:
        identifier = retain(match, env)
        response = client.post(f'/matches/{identifier}/action', json={
            'player_id': seat, 'action': action})
        assert response.status_code == 200, response.text
        env._state = deepcopy(restart(identifier).state)
        env._state.id = original['state']['id']
    else:
        env.step(action)
    state = env._state
    assert_activation(state, seat, info)
    sequence = state.cards[info['ninja']].zone_change_sequence
    assert state.stack[0].payload['__source_zone_sequence'] == sequence
    if movement != 'unchanged':
        relocate(state, info['ninja'], Zone.EXILE)
        if movement == 'reentered':
            relocate(state, info['ninja'], Zone.HAND)
        assert state.cards[info['ninja']].zone_change_sequence > sequence
    pending = env.snapshot()
    (tmp_path / 'before.json').write_text(json.dumps(original, sort_keys=True))
    (tmp_path / 'pending.json').write_text(json.dumps(pending, sort_keys=True))
    fork = TrainingEnvironment()
    fork.restore(pending)
    resolve(env)
    resolve(fork)
    assert env.snapshot() == fork.snapshot()
    (tmp_path / 'after.json').write_text(json.dumps(env.snapshot(), sort_keys=True))
    if via_http:
        saved = TrainingEnvironment()
        saved.restore(pending)
        retain(restart(identifier), saved)
        state = http_resolve(client, identifier)
        assert state.cards[info['ninja']].zone == env._state.cards[info['ninja']].zone
        private = next(cid for cid in state.players[3-seat].hand)
        public = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}')
        assert public.status_code == 200, public.text
        assert private not in public.text
        env._state = deepcopy(state)
        assert private not in env.observe(seat)['known_cards']
    else:
        state = env._state
    expected = {'unchanged': Zone.BATTLEFIELD, 'exiled': Zone.EXILE,
                'reentered': Zone.HAND}[movement]
    assert state.cards[info['ninja']].zone == expected
    assert (info['ninja'] in state.attackers) == (movement == 'unchanged')
    assert info['attackers'][1] in state.players[seat].hand
    assert info['attackers'][1] not in state.attackers
    assert info['attackers'][0] in state.attackers
    assert all(state.cards[cid].tapped for cid in info['lands'])
    assert not state.stack and sum(state.players[seat].mana_pool.values()) == 0


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('reference', [None, True, '0', -1])
def test_unverifiable_pending_legacy_reference_does_not_guess_or_refund(seat, reference):
    env, action, _, info = scenario(seat)
    env.step(action)
    if reference is None:
        env._state.stack[0].payload.pop('__source_zone_sequence')
    else:
        env._state.stack[0].payload['__source_zone_sequence'] = reference
    restored = TrainingEnvironment()
    restored.restore(env.snapshot())
    resolve(restored)
    assert restored._state.cards[info['ninja']].zone == Zone.HAND
    assert info['attackers'][1] in restored._state.players[seat].hand
    assert all(restored._state.cards[cid].tapped for cid in info['lands'])
    assert not restored._state.stack


@pytest.mark.parametrize('seat', [1, 2])
def test_new_activation_can_reference_returned_hand_object(seat):
    env, action, _, info = scenario(seat)
    for _ in range(2):
        raw_card(env._state, fallback_card_payload('Island'), seat, Zone.BATTLEFIELD)
    env.step(action)
    relocate(env._state, info['ninja'], Zone.EXILE)
    relocate(env._state, info['ninja'], Zone.HAND)
    resolve(env)
    assert env._state.cards[info['ninja']].zone == Zone.HAND
    env.step({**action, 'return_card_id': info['attackers'][0]})
    assert env._state.stack[0].payload['__source_zone_sequence'] == (
        env._state.cards[info['ninja']].zone_change_sequence)
    resolve(env)
    assert env._state.cards[info['ninja']].zone == Zone.BATTLEFIELD
    assert all(cid in env._state.players[seat].hand for cid in info['attackers'])


@pytest.mark.parametrize('seat', [1, 2])
def test_canonical_cycling_draw_is_independent_of_departed_source(game, seat):
    env = position(seat)
    rows = json.loads((Path(__file__).parent / 'fixtures/death_cycle_ordering/canonical.json').read_text())
    cycler = raw_card(env._state, rows['Lonely Sandbar'], seat, Zone.HAND)
    raw_card(env._state, fallback_card_payload('Island'), seat, Zone.BATTLEFIELD)
    env._state.players[seat].mana_pool = {}
    client, match = game
    identifier = retain(match, env)
    response = client.post(f'/matches/{identifier}/action', json={
        'player_id': seat, 'action': {'type': 'cycle_card', 'card_id': cycler.id}})
    assert response.status_code == 200, response.text
    env._state = deepcopy(restart(identifier).state)
    assert env._state.stack[0].effect_key == 'cycle_draw'
    assert env._state.cards[cycler.id].zone == Zone.GRAVEYARD
    relocate(env._state, cycler.id, Zone.EXILE)
    count = len(env._state.players[seat].hand)
    retain(restart(identifier), env)
    state = http_resolve(client, identifier)
    assert state.cards[cycler.id].zone == Zone.EXILE
    assert len(state.players[seat].hand) == count + 1
    assert not state.stack
