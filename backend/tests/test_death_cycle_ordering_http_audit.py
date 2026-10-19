"""Actual isolated HTTP/restart ordering and actor-owned private continuation."""
from copy import deepcopy
import json
import socket
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_death_cycle_ordering_audit import (RAW, add, cards, cycle_position,
                                                 death_position, receipt, tokens)


@pytest.fixture
def offline_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No external socket access in canonical offline audit')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    original = dict(main.ACTIVE_MATCHES)
    try:
        with TestClient(main.app) as client:
            with Session(engine) as session:
                repo = Repository(session)
                for raw in RAW.values():
                    repo.upsert_card({
                        'scryfall_id': raw['id'], 'name': raw['name'],
                        'oracle_text': raw.get('oracle_text', ''),
                        'mana_cost': raw.get('mana_cost', ''),
                        'type_line': raw.get('type_line', ''),
                        'layout': raw.get('layout', ''),
                        'colors': ','.join(raw.get('colors', [])),
                        'power': raw.get('power'), 'toughness': raw.get('toughness'),
                        'legalities_json': json.dumps(raw.get('legalities', {})),
                        'card_faces_json': json.dumps(raw.get('card_faces', []))})
            yield client
    finally:
        main.ACTIVE_MATCHES.clear()
        main.ACTIVE_MATCHES.update(original)


def install(state, request, seat, private=False):
    state.id = 'ordering-' + __import__('hashlib').sha256(request.node.nodeid.encode()).hexdigest()[:16]
    match = main.MatchController(
        state=state, rules=RulesEngine(),
        controllers={pid: 'ai' if private and pid != seat else 'human' for pid in (1, 2)},
        ai={pid: main.AIAgent(difficulty='master', archetype='Midrange', opponent_archetype='Midrange')
            for pid in (1, 2)},
        mode='player_vs_ai' if private else 'human_vs_human', deck_ids=(None, None),
        mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False,
        best_of=1, root_seed=37)
    main.ACTIVE_MATCHES[state.id] = match
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)
    return match


def restore(identifier):
    match = main.ACTIVE_MATCHES[identifier]
    snapshot = serialize_match_snapshot(match.state)
    config = deepcopy(main._controller_snapshot(match))
    main.ACTIVE_MATCHES.pop(identifier)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), identifier)
    restored = main.ACTIVE_MATCHES[identifier]
    assert serialize_match_snapshot(restored.state) == snapshot
    assert main._controller_snapshot(restored) == config
    return restored


def frozen(match):
    with sqlite3.connect(DATABASE_PATH) as connection:
        database = list(connection.iterdump())
    return (serialize_match_snapshot(match.state),
            deepcopy(main._controller_snapshot(match)), database)


def act(client, match, seat, action):
    return client.post('/matches/' + match.state.id + '/action',
                       json={'player_id': seat, 'action': action})


def drain(client, identifier, limit=8):
    match = main.ACTIVE_MATCHES[identifier]
    for _ in range(limit):
        if not match.state.stack or match.state.pending_mechanic_choice:
            return match
        if match.controllers.get(match.state.priority_player) == 'ai':
            response = client.post('/matches/' + identifier + '/autoplay?ticks=1')
        else:
            response = act(client, match, match.state.priority_player, {'type': 'pass_priority'})
        assert response.status_code == 200, response.text
        match = restore(identifier)
    raise AssertionError('Bounded expected stack protocol did not finish')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('kind', ['death', 'cycle'])
@pytest.mark.parametrize('mode', ['none', 'rip', 'leyline_enemy'])
def test_actual_http_replacement_order_and_self_trigger_restart(request, offline_client, seat, kind, mode):
    if kind == 'death':
        state, source, action = death_position(seat, 'Chromatic Star', mode)
    else:
        state, source, action = cycle_position(seat, 'Shark Typhoon', mode)
    match = install(state, request, seat)
    before = frozen(match)
    invalid = {**action, 'card_id': 'missing-source'}
    rejected = act(offline_client, match, seat, invalid)
    assert rejected.status_code == 422
    assert frozen(main.ACTIVE_MATCHES[state.id]) == before
    match = restore(state.id)
    response = act(offline_client, match, seat, action)
    assert response.status_code == 200, response.text
    match = restore(state.id)
    queued = serialize_match_snapshot(match.state)
    match = drain(offline_client, state.id)
    generated = tokens(match.state, seat)
    expected = 0 if kind == 'cycle' else 1 if mode == 'none' else 0
    receipt(request, {'setup': serialize_match_snapshot(state), 'action': action,
                      'queued': queued, 'resolved': serialize_match_snapshot(match.state),
                      'expected_hand_count': 1 if kind == 'cycle' or mode == 'none' else 0,
                      'actual_hand_count': len(match.state.players[seat].hand),
                      'expected_shark_count': 1 if kind == 'cycle' else 0,
                      'actual_shark_count': len(generated),
                      'revision': match.revision,
                      'baseline_self_cycling_composed': True})
    assert len(match.state.players[seat].hand) == (1 if kind == 'cycle' or mode == 'none' else 0)
    assert len(queued['stack']) == (2 if kind == 'cycle' else expected)
    if kind == 'cycle':
        assert len(generated) == 1 and generated[0].power == generated[0].toughness == 2


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'leyline_enemy'])
def test_cycle_draw_private_dredge_continuation_restart_and_actor_guard(request, offline_client, seat, mode):
    state, source, action = cycle_position(seat, 'Lonely Sandbar', mode)
    dredger = add(state, 'Life from the Loam', seat, Zone.GRAVEYARD)
    secret = add(state, 'Swamp', 3 - seat, Zone.HAND)
    own_secret = add(state, 'Raging Goblin', seat, Zone.HAND)
    state.mechanic_choice_players = {seat}
    library_ids = list(state.players[seat].library)
    match = install(state, request, seat, private=True)
    response = act(offline_client, match, seat, action)
    assert response.status_code == 200, response.text
    match = drain(offline_client, state.id)
    assert match.state.pending_mechanic_choice['kind'] == 'draw'
    assert match.state.pending_mechanic_choice['player_id'] == seat
    assert dredger.id in match.state.pending_mechanic_choice['options']
    public = main._serialize_match_controller(match)
    encoded = json.dumps(public)
    assert secret.id not in encoded and all(cid not in encoded for cid in library_ids)
    assert own_secret.id in encoded and public['root_seed'] is None
    before = frozen(match)
    rejected = act(offline_client, match, 3 - seat,
                   {'type': 'choose_mechanic', 'choice_id': dredger.id})
    assert rejected.status_code in (403, 422)
    assert frozen(main.ACTIVE_MATCHES[state.id]) == before
    match = restore(state.id)
    response = act(offline_client, match, seat,
                   {'type': 'choose_mechanic', 'choice_id': dredger.id})
    assert response.status_code == 200, response.text
    match = restore(state.id)
    receipt(request, {'action': action, 'pending_public': public,
                      'library_before_private': library_ids,
                      'rejected_status': rejected.status_code,
                      'resolved': serialize_match_snapshot(match.state),
                      'revision': match.revision})
    assert not match.state.pending_mechanic_choice and not match.state.stack
    assert dredger.id in match.state.players[seat].hand
    assert own_secret.id in match.state.players[seat].hand
    assert not match.state.players[seat].library
    expected_zone = Zone.EXILE if mode == 'leyline_enemy' else Zone.GRAVEYARD
    assert all(match.state.cards[cid].zone == expected_zone for cid in library_ids)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'rip'])
def test_actual_http_cycle_or_discard_watcher_once_after_restart(request, offline_client, seat, mode):
    state, source, action = cycle_position(seat, 'Lonely Sandbar', mode)
    watcher = add(state, 'Archfiend of Ifnir', seat)
    opposing = add(state, 'Krosan Tusker', 3 - seat)
    match = install(state, request, seat)
    response = act(offline_client, match, seat, action)
    assert response.status_code == 200, response.text
    match = restore(state.id)
    queued = serialize_match_snapshot(match.state)
    match = drain(offline_client, state.id)
    actual = match.state.cards[opposing.id].counters.get('-1/-1', 0)
    receipt(request, {'action': action, 'queued': queued,
                      'watcher_id': watcher.id, 'target_id': opposing.id,
                      'actual_counter': actual, 'expected_counter': 1,
                      'resolved': serialize_match_snapshot(match.state),
                      'revision': match.revision})
    assert actual == 1
