"""Cold command and persisted-discovery edge controls; owned local DB only."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from game_state.state import Step
from persistence.repository import Repository
from tests.test_lazy_saved_matches import store


@pytest.mark.parametrize('seat', [1, 2])
def test_cold_priority_stop_command_exact_retry_and_restore(store, seat):
    _, rows = store
    mid = rows[0][0]['id']
    headers = {'Idempotency-Key': 'cold-stop', 'X-Match-Revision': '0'}
    with TestClient(main.app) as client:
        assert not main.ACTIVE_MATCHES
        result = client.post(f'/matches/{mid}/priority-stops',
                             json={'player_id': seat, 'stops': [Step.PRECOMBAT_MAIN.value]}, headers=headers)
        assert result.status_code == 200, result.text
        assert set(main.ACTIVE_MATCHES) == {mid}
        assert main.ACTIVE_MATCHES[mid].state.priority_stops[seat] == {Step.PRECOMBAT_MAIN}
        state = serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state)
        config = main._controller_snapshot(main.ACTIVE_MATCHES[mid])
        main.ACTIVE_MATCHES.clear()
        retry = client.post(f'/matches/{mid}/priority-stops',
                            json={'player_id': seat, 'stops': [Step.PRECOMBAT_MAIN.value]}, headers=headers)
        assert retry.status_code == 200 and retry.json() == result.json()
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == state
        assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == config


def test_complete_saved_match_not_discovered_but_cold_readable_without_deletion(store):
    db, rows = store
    raw, config = rows[0]
    config = {**config, 'match_complete': True}
    with Session(db) as session:
        Repository(session).save_active_match(raw['id'], json.dumps(raw), json.dumps(config))
    with TestClient(main.app) as client:
        assert not main.ACTIVE_MATCHES
        listed = client.get('/matches').json()
        assert len(listed) == 2 and raw['id'] not in {item['id'] for item in listed}
        assert not main.ACTIVE_MATCHES
        assert client.get('/matches/' + raw['id']).status_code == 200
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[raw['id']].state) == raw
        assert main._controller_snapshot(main.ACTIVE_MATCHES[raw['id']]) == config
    with Session(db) as session:
        assert len(Repository(session).list_active_matches()) == 3


def test_row_snapshot_identity_mismatch_cannot_publish_another_id(store):
    db, rows = store
    raw, config = rows[0]
    wrong = deepcopy(raw)
    wrong['id'] = 'another-saved-id'
    with Session(db) as session:
        Repository(session).save_active_match(raw['id'], json.dumps(wrong), json.dumps(config))
    with TestClient(main.app) as client:
        assert client.get('/matches/' + raw['id']).status_code == 404
        assert not main.ACTIVE_MATCHES
        assert raw['id'] not in {item['id'] for item in client.get('/matches').json()}


def test_plausible_metadata_does_not_certify_deeply_corrupt_snapshot_restore(store):
    db, rows = store
    raw, config = rows[0]
    corrupted = deepcopy(raw)
    corrupted['cards'][next(iter(corrupted['cards']))]['counters'] = None
    state_json, controller_json = json.dumps(corrupted), json.dumps(config)
    with Session(db) as session:
        Repository(session).save_active_match(raw['id'], state_json, controller_json)
    with TestClient(main.app) as client:
        listed = client.get('/matches')
        assert listed.status_code == 200
        summary = next(item for item in listed.json() if item['id'] == raw['id'])
        assert set(summary) == {'id', 'mode', 'turn', 'game_number', 'revision', 'players'}
        assert len(listed.json()) == len(rows) and not main.ACTIVE_MATCHES
        rejected = client.get('/matches/' + raw['id'])
        assert rejected.status_code == 404
        assert rejected.json() == {'detail': 'Match not found'}
        assert not main.ACTIVE_MATCHES
        assert client.get('/matches').json() == listed.json()
    with Session(db) as session:
        saved = Repository(session).get_active_match(raw['id'])
        assert saved.state_json == state_json and saved.controller_json == controller_json
