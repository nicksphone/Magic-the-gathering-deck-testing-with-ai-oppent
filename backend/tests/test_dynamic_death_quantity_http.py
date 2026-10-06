"""Real isolated API/SQLite protocol using canonical partial positions, no decks."""
from copy import deepcopy
import json
import socket
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_dynamic_death_quantity import (FAMILIES, RAW, position, tokens,
                                              write_receipt)


def persist(match):
    with Session(engine) as session:
        main._persist_active_match(Repository(session), match)


def state_and_database(match):
    with sqlite3.connect(DATABASE_PATH) as connection:
        database = list(connection.iterdump())
    return (serialize_match_snapshot(match.state),
            deepcopy(main._controller_snapshot(match)), database)


def restore(identifier):
    match = main.ACTIVE_MATCHES[identifier]
    state = serialize_match_snapshot(match.state)
    controller = deepcopy(main._controller_snapshot(match))
    main.ACTIVE_MATCHES.pop(identifier)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), identifier)
    restored = main.ACTIVE_MATCHES[identifier]
    assert serialize_match_snapshot(restored.state) == state
    assert main._controller_snapshot(restored) == controller
    return restored


@pytest.fixture
def canonical_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('External network access is forbidden in offline qualification')
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


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', FAMILIES)
def test_dynamic_count_survives_actual_http_sqlite_restart(request, canonical_client, seat, name):
    state, source, action = position(seat, name, 2)
    state.id = 'dynamic-death-http-' + str(seat) + '-' + name.replace(' ', '-')
    match = main.MatchController(
        state=state, rules=RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={pid: main.AIAgent(difficulty='master', archetype='Midrange',
                             opponent_archetype='Midrange') for pid in (1, 2)},
        mode='human_vs_human', deck_ids=(None, None),
        mainboards={1: [], 2: []}, sideboards={1: [], 2: []},
        game_number=1, current_game_recorded=False, match_complete=False,
        best_of=1, root_seed=37)
    main.ACTIVE_MATCHES[state.id] = match
    persist(match)
    setup = serialize_match_snapshot(state)
    status_response = canonical_client.get('/cards/completeness', params={'names': name})
    assert status_response.status_code == 200
    public_status = status_response.json()
    before = state_and_database(match)
    invalid = {**action, 'payment_choices': {'sacrifice_card_ids': ['no-such-object']}}
    response = canonical_client.post('/matches/' + state.id + '/action',
                                    json={'player_id': seat, 'action': invalid})
    assert response.status_code == 422
    assert state_and_database(main.ACTIVE_MATCHES[state.id]) == before
    match = restore(state.id)
    response = canonical_client.post('/matches/' + state.id + '/action',
                                    json={'player_id': seat, 'action': action})
    assert response.status_code == 200, response.text
    match = restore(state.id)
    assert len(match.state.stack) == 1
    queued = serialize_match_snapshot(match.state)
    for _ in range(2):
        actor = match.state.priority_player
        response = canonical_client.post('/matches/' + state.id + '/action',
                                        json={'player_id': actor,
                                              'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
        match = restore(state.id)
    assert not match.state.stack
    generated = tokens(match.state, seat)
    write_receipt(request, {'setup': setup, 'action': action,
                           'public_completeness': public_status, 'queued': queued,
                           'expected': 2, 'actual': len(generated),
                           'resolved': serialize_match_snapshot(match.state),
                           'revision': match.revision,
                           'mutation_receipts': deepcopy(match.mutation_receipts)})
    assert len(generated) == 2, f'{name}: expected 2, actual {len(generated)}'
