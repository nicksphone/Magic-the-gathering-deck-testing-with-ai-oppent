"""Source-only saved-match qualification; no live DB or fabricated cards."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

import main
from ai.agent import AIAgent
from card_data.fallback_cards import fallback_card_payload
from game_state.serializers import serialize_match_snapshot
from game_state.state import MatchFactory, Step
from persistence.repository import Repository


def template():
    deck = [{**fallback_card_payload('Island'), 'card_name': 'Island', 'quantity': 60}]
    state = MatchFactory.from_decks(deck, deck, seed=1729)
    state.pregame_pending = False
    state.step = Step.PRECOMBAT_MAIN
    return main.MatchController(state=state, rules=main.RulesEngine(),
        controllers={1: 'human', 2: 'human'}, ai={p: AIAgent() for p in (1, 2)},
        mode='human_vs_human', deck_ids=(None, None), mainboards={1: deck, 2: deck},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=3, root_seed=1729)


def seed(repo, count=3):
    match = template()
    state = serialize_match_snapshot(match.state)
    config = main._controller_snapshot(match)
    rows = []
    for i in range(count):
        raw = deepcopy(state)
        raw['id'] = f'lazy-{uuid4()}'
        raw['turn'] = i + 1
        repo.save_active_match(raw['id'], json.dumps(raw), json.dumps(config))
        rows.append((raw, deepcopy(config)))
    return rows


@pytest.fixture
def store(tmp_path, monkeypatch):
    db = create_engine(f'sqlite:///{tmp_path / "saved.db"}',
                       connect_args={'check_same_thread': False})
    SQLModel.metadata.create_all(db)
    old = dict(main.ACTIVE_MATCHES)
    main.ACTIVE_MATCHES.clear()
    monkeypatch.setattr(main, 'engine', db)
    monkeypatch.setattr(main, 'init_db', lambda: SQLModel.metadata.create_all(db))
    for name in ('_ensure_builtin_decks', '_ensure_expansion_top_decks', '_restore_simulation_jobs'):
        monkeypatch.setattr(main, name, lambda _: None)
    def repository():
        with Session(db) as session:
            yield Repository(session)
    main.app.dependency_overrides[main.get_repo] = repository
    with Session(db) as session:
        rows = seed(Repository(session))
    try:
        yield db, rows
    finally:
        main.app.dependency_overrides.pop(main.get_repo, None)
        main.ACTIVE_MATCHES.clear()
        main.ACTIVE_MATCHES.update(old)
        db.dispose()


def test_startup_and_discovery_do_not_hydrate_gameplay(store, monkeypatch):
    db, rows = store
    with Session(db) as session:
        main._restore_active_matches(Repository(session))
    expected = main.list_active_matches()
    main.ACTIVE_MATCHES.clear()
    calls = []
    original = main.deserialize_match_snapshot
    def counted(raw):
        calls.append(raw['id'])
        return original(raw)
    monkeypatch.setattr(main, 'deserialize_match_snapshot', counted)
    with TestClient(main.app) as client:
        assert calls == []
        response = client.get('/matches')
        assert response.status_code == 200
        assert response.json() == expected
        assert calls == [] and not main.ACTIVE_MATCHES
        assert len(response.json()) == len(rows)
        assert all(set(row) == {'id', 'mode', 'turn', 'game_number', 'revision', 'players'}
                   for row in response.json())


@pytest.mark.parametrize('suffix', ['', '/legal-moves?player_id=1', '/replacement-options?player_id=1', '/rules-diagnostics'])
def test_cold_http_read_restores_only_requested_snapshot(store, suffix):
    _, rows = store
    raw, config = rows[0]
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        response = client.get(f'/matches/{raw["id"]}{suffix}')
        assert response.status_code == 200, response.text
        assert set(main.ACTIVE_MATCHES) == {raw['id']}
        loaded = main.ACTIVE_MATCHES[raw['id']]
        assert serialize_match_snapshot(loaded.state) == raw
        assert main._controller_snapshot(loaded) == config
        assert len(client.get('/matches').json()) == len(rows)


def test_cold_write_retry_and_restart_preserve_receipts(store):
    _, rows = store
    raw, _ = rows[0]
    mid = raw['id']
    action = {'player_id': 1, 'action': {'type': 'play_land', 'card_id': raw['players']['1']['hand'][0]}}
    headers = {'Idempotency-Key': 'cold-land', 'X-Match-Revision': '0'}
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        first = client.post(f'/matches/{mid}/action', json=action, headers=headers)
        assert first.status_code == 200, first.text
        saved = serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state)
        config = main._controller_snapshot(main.ACTIVE_MATCHES[mid])
        main.ACTIVE_MATCHES.clear()
        retry = client.post(f'/matches/{mid}/action', json=action, headers=headers)
        assert retry.status_code == 200 and retry.json() == first.json()
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved
        assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == config
        stale = client.post(f'/matches/{mid}/action', json=action,
                            headers={**headers, 'Idempotency-Key': 'different'})
        assert stale.status_code == 409
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved


def test_concurrent_cold_reads_publish_exactly_one_controller(store, monkeypatch):
    _, rows = store
    mid = rows[0][0]['id']
    calls = []
    counter_lock = threading.Lock()
    original = main.deserialize_match_snapshot
    def counted(raw):
        with counter_lock:
            calls.append(raw['id'])
        time.sleep(.02)
        return original(raw)
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        monkeypatch.setattr(main, 'deserialize_match_snapshot', counted)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: client.get(f'/matches/{mid}'), range(8)))
        assert all(response.status_code == 200 for response in results)
        assert calls == [mid]
        assert set(main.ACTIVE_MATCHES) == {mid}


def test_legacy_eager_restore_never_overwrites_loaded_mutation(store):
    db, rows = store
    mid = rows[0][0]['id']
    with Session(db) as session:
        repo = Repository(session)
        main._restore_active_matches(repo, mid)
        loaded = main.ACTIVE_MATCHES[mid]
        loaded.state.turn = 99
        loaded.revision = 47
        loaded.mutation_receipts['unsaved'] = 'must-not-be-replaced'
        main._restore_active_matches(repo)
        assert main.ACTIVE_MATCHES[mid] is loaded
        assert loaded.state.turn == 99 and loaded.revision == 47
        assert loaded.mutation_receipts['unsaved'] == 'must-not-be-replaced'


def test_discovery_uses_loaded_state_over_stale_disk_without_private_fields(store):
    _, rows = store
    mid = rows[0][0]['id']
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        assert client.get(f'/matches/{mid}').status_code == 200
        loaded = main.ACTIVE_MATCHES[mid]
        loaded.state.turn = 99
        loaded.revision = 47
        listed = {row['id']: row for row in client.get('/matches').json()}
        assert listed[mid]['turn'] == 99 and listed[mid]['revision'] == 47
        assert len(listed) == len(rows)
        assert 'cards' not in listed[mid] and 'hand' not in listed[mid]
        loaded.match_complete = True
        assert mid not in {row['id'] for row in client.get('/matches').json()}


@pytest.mark.parametrize('state_json,controller_json', [('{', '{}'), ('null', '{}'), ('{}', '{}'), ('[]', '{}')])
def test_malformed_and_unknown_saved_ids_are_http_404(store, state_json, controller_json):
    db, _ = store
    bad = f'malformed-{uuid4()}'
    with Session(db) as session:
        Repository(session).save_active_match(bad, state_json, controller_json)
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        for mid in (bad, 'does-not-exist'):
            assert client.get(f'/matches/{mid}').status_code == 404
        assert bad not in {row['id'] for row in client.get('/matches').json()}
        assert bad not in main.ACTIVE_MATCHES
