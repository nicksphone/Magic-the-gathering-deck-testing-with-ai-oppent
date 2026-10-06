"""Canonical foretell intent audit; unsupported requests must not be discarded."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from game_state.serializers import serialize_match
from game_state.state import Zone
from rules_engine.action_validation import ActionRejected
from rules_engine.foretell import record, cast_permission
from training.environment import TrainingEnvironment, decode_action, encode_action
from training.dataset import EpisodeAliases, canonical
from tests.test_api_input_contracts import game, rejected
from tests.test_selected_mana_http import retain, restart, forbid_external_network
from tests.test_training_choice_coverage import position, card, cast
from tests.test_training_environment import resolve
from tests.test_linked_damage_targets import raw_card


ROWS = json.loads((Path(__file__).parent / 'fixtures/foretell.json').read_text())
DOOMSKAR = next(row for row in ROWS if row['name'] == 'Doomskar')


def scenario(seat):
    env = position(seat)
    cid = raw_card(env._state, DOOMSKAR, seat, Zone.HAND).id
    env._state.players[seat].mana_pool = {'C': 2}
    instance = env._state.cards[cid]
    instance.keywords = deepcopy(DOOMSKAR['keywords'])
    for key in ('name', 'mana_cost', 'oracle_text', 'type_line', 'keywords'):
        assert getattr(instance, key) == DOOMSKAR[key]
    action = {'type': 'foretell', 'card_id': cid}
    hint = next(move for move in env._rules.legal_moves(deepcopy(env._state), seat)
                if move['type'] == 'foretell' and move['card_id'] == cid)
    assert set(hint) == {'type', 'card_id', 'card_name', 'mana_cost',
                         'fixed_costs', 'granted_reductions'}
    return env, cid, action, hint


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('field,value', [
    ('return_card_id', 'stale-requested-return'), ('return_card_id', None),
    ('cost_choice', {'id': 'requested-not-offered'}), ('cost_choice', None),
    ('selected_face_index', 1), ('selected_face_index', None),
    ('resolving_item', {'controller': 99}), ('resolving_item', None),
])
def test_unsupported_foretell_request_rejects_before_normalization(game, seat, field, value):
    env, _, action, _ = scenario(seat)
    request = {**action, field: value}
    original, before = deepcopy(request), env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(request, seat)
    client, match = game
    retain(match, env)
    assert rejected(client, match, request, seat).status_code == 422
    try:
        with pytest.raises(ActionRejected):
            env.lookup_intent(request, seat)
    finally:
        assert env.snapshot() == before
        assert request == original


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('whole_view', [False, True])
def test_independent_foretell_exact_cost_private_exile_and_replay(game, seat, whole_view):
    env, cid, action, hint = scenario(seat)
    before = env.snapshot()
    proposed = hint if whole_view else action
    assert env.lookup_intent(proposed, seat) == env.lookup(action, seat)
    assert env.snapshot() == before
    encoded = encode_action(action)
    assert decode_action(encoded) == action
    restored = TrainingEnvironment()
    restored.restore(before)
    assert env.step(encoded) == restored.step(action)
    assert env.snapshot() == restored.snapshot()
    state = env._state
    assert cid in state.players[seat].exile and cid not in state.players[seat].hand
    assert state.priority_player == seat and not state.stack
    assert sum(state.players[seat].mana_pool.values()) == 0
    assert record(state.cards[cid])['fixed_costs'] == ['{1}{W}{W}']
    assert not cast_permission(state, seat, state.cards[cid])
    assert cid in env.observe(seat)['known_cards']
    assert cid not in env.observe(3-seat)['known_cards']
    assert serialize_match(state, look_players=[3-seat])['players'][seat]['exile'] == []
    assert not any('Doomskar' in entry for entry in state.log)
    client, match = game
    unplayed = TrainingEnvironment()
    unplayed.restore(before)
    identifier = retain(match, unplayed)
    match = restart(identifier)
    public_moves = client.get(f'/matches/{identifier}/legal-moves?player_id={seat}').json()['moves']
    public_hint = next(move for move in public_moves
                       if move['type'] == 'foretell' and move['card_id'] == cid)
    assert all(public_hint[key] == value for key, value in hint.items())
    assert public_hint['card_view']['oracle_text'] == DOOMSKAR['oracle_text']
    assert unplayed.lookup_intent(public_hint, seat) == unplayed.lookup(action, seat)
    response = client.post(f'/matches/{identifier}/action',
                           json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    persisted = restart(identifier)
    assert record(persisted.state.cards[cid]) == record(state.cards[cid])
    assert serialize_match(persisted.state, look_players=[3-seat])['players'][seat]['exile'] == []


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_later_turn_doomskar_cast_and_actual_destroy_resolution(game, seat):
    env, cid, action, _ = scenario(seat)
    victim = card(env, 'Grizzly Bears', 3-seat, Zone.BATTLEFIELD)
    env.step(action)
    forbidden = {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                 'cost_choice': {'id': 'foretell_0'}}
    before = env.snapshot()
    with pytest.raises(ActionRejected):
        env.lookup(forbidden, seat)
    assert env.snapshot() == before
    env._state.turn += 1
    env._state.players[seat].mana_pool = {'C': 1, 'W': 2}
    selected = cast(env, cid, from_exile=True)
    assert selected['cost_choice']['id'] == 'foretell_0'
    assert env.lookup_intent(selected, seat) == env.lookup(selected, seat)
    restored = TrainingEnvironment()
    restored.restore(env.snapshot())
    env.step(encode_action(selected))
    restored.step(selected)
    assert env.snapshot() == restored.snapshot()
    assert env._state.stack[-1].payload['__was_foretold']
    resolve(env)
    assert victim in env._state.players[3-seat].graveyard
    assert cid in env._state.players[seat].graveyard
    assert not record(env._state.cards[cid])
    client, match = game
    identifier = retain(match, restored)
    restart(identifier)
    for actor in (restored.acting_seat, 3-restored.acting_seat):
        response = client.post(f'/matches/{identifier}/action',
                               json={'player_id': actor, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    completed = restart(identifier)
    assert cid in completed.state.players[seat].graveyard
    assert victim in completed.state.players[3-seat].graveyard


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('fault', ['insufficient', 'other_turn', 'wrong_zone', 'stale', 'null'])
def test_independent_invalid_foretell_known_fields_and_timing_atomic(game, seat, fault):
    env, cid, action, _ = scenario(seat)
    if fault == 'insufficient':
        env._state.players[seat].mana_pool = {'C': 1}
    elif fault == 'other_turn':
        env._state.active_player = 3-seat
    elif fault == 'wrong_zone':
        env._state.players[seat].hand.remove(cid)
        env._state.players[seat].graveyard.append(cid)
        env._state.cards[cid].move_to_zone(Zone.GRAVEYARD)
    else:
        action['card_id'] = None if fault == 'null' else 'stale-card'
    before = env.snapshot()
    for method in (env.lookup, env.lookup_intent):
        with pytest.raises(ActionRejected):
            method(action, seat)
        assert env.snapshot() == before
    client, match = game
    retain(match, env)
    assert rejected(client, match, action, seat).status_code == 422


@pytest.mark.parametrize('seat', [1, 2])
def test_independent_exile_incarnation_and_hidden_identity_permutation(game, seat):
    env, cid, action, _ = scenario(seat)
    env.step(action)
    actor_input = canonical(EpisodeAliases().observation(env.observe(seat)))
    enemy_input = canonical(EpisodeAliases().observation(env.observe(3-seat)))
    before = env.snapshot()
    concealed = env._state.players[3-seat].hand + env._state.players[3-seat].library
    first, second = concealed[0], concealed[-1]
    env._state.cards[first], env._state.cards[second] = (
        deepcopy(env._state.cards[second]), deepcopy(env._state.cards[first]))
    env._state.cards[first].id, env._state.cards[second].id = first, second
    env._state.players[3-seat].hand.reverse()
    env._state.players[3-seat].library.reverse()
    assert canonical(EpisodeAliases().observation(env.observe(seat))) == actor_input
    env.restore(before)
    # Change the concealed foretold identity only in an adversarial private-root copy.
    env._state.cards[cid].name = 'hidden-permutation'
    assert canonical(EpisodeAliases().observation(env.observe(3-seat))) == enemy_input
    env.restore(before)
    state = env._state
    state.players[seat].exile.remove(cid)
    state.cards[cid].move_to_zone(Zone.HAND)
    state.players[seat].hand.append(cid)
    state.players[seat].hand.remove(cid)
    state.cards[cid].move_to_zone(Zone.EXILE)
    state.players[seat].exile.append(cid)
    state.turn += 1
    assert not record(state.cards[cid]) and not cast_permission(state, seat, state.cards[cid])
    client, match = game
    identifier = retain(match, env)
    restored = restart(identifier)
    assert not record(restored.state.cards[cid])
    rejected(client, restored, {'type': 'cast_spell', 'card_id': cid,
             'from_exile': True, 'cost_choice': {'id': 'foretell_0'}}, seat)
