"""Opt-in ASGI boundary reproducers, memory-only DB, never a live API call."""
import json
import os
from pathlib import Path

import pytest

from game_state.serializers import serialize_match_snapshot
from tests.test_spell_cost_overlap_investigation import source_overlap


pytestmark = pytest.mark.skipif(os.environ.get('MTG_COST_OVERLAP_HTTP') != '1',
                               reason='Opt-in isolated-source memory-only HTTP qualification')


class UncontrolledSourceOverlap(AssertionError):
    """Do not mask fixture, root-purity, or persistence assertion failures."""


@pytest.fixture
def isolated_api(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    approved = os.environ.get('MTG_COST_OVERLAP_ROOT')
    assert approved and Path(approved).resolve() == root
    assert not (root / 'mtg_lab.db').exists() and not (root / 'mtg_lab.db').is_symlink()
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import create_engine
    import persistence.db as db
    import main

    assert Path(main.__file__).resolve().parent == root
    memory = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    monkeypatch.setattr(db, 'engine', memory)
    monkeypatch.setattr(main, 'engine', memory)
    for name in ('_ensure_builtin_decks', '_ensure_expansion_top_decks',
                 '_restore_active_matches', '_restore_simulation_jobs'):
        monkeypatch.setattr(main, name, lambda repo: None)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            yield main, memory, client
    finally:
        memory.dispose()
        assert not (root / 'mtg_lab.db').exists()


def database_dump(engine):
    connection = engine.raw_connection()
    try:
        return tuple(connection.driver_connection.iterdump())
    finally:
        connection.close()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Village Rites', 'Tormenting Voice'])
def test_http_source_overlap_is_controlled_rejection_with_atomic_root_and_db(isolated_api, seat, name):
    from sqlmodel import Session
    from persistence.repository import Repository

    main, memory, client = isolated_api
    state, spell, _, _, action = source_overlap(seat, name)
    state.id = f'cost-overlap-{seat}-{name.lower().replace(" ", "-")}'
    controller = main.MatchController(
        state=state, rules=main.RulesEngine(), controllers={1: 'human', 2: 'human'},
        ai={}, mode='human_vs_human', deck_ids=(None, None), mainboards={1: [], 2: []},
        sideboards={1: [], 2: []}, game_number=1, current_game_recorded=False,
        match_complete=False, best_of=1)
    main.ACTIVE_MATCHES[state.id] = controller
    with Session(memory) as session:
        main._persist_active_match(Repository(session), controller)
    before = serialize_match_snapshot(state)
    controller_before = main._controller_snapshot(controller)
    database_before = database_dump(memory)
    response = client.post(f'/matches/{state.id}/action',
                           json={'player_id': seat, 'action': action})
    root_equal = serialize_match_snapshot(controller.state) == before
    controller_equal = main._controller_snapshot(controller) == controller_before
    db_equal = database_dump(memory) == database_before
    assert root_equal and controller_equal and db_equal
    evidence = os.environ.get('MTG_COST_OVERLAP_EVIDENCE')
    if evidence:
        path = Path(evidence) / f'http-{state.id}.json'
        with path.open('x') as stream:
            json.dump({'seat': seat, 'spell': name, 'status': response.status_code,
                       'root_unchanged': root_equal, 'controller_unchanged': controller_equal,
                       'database_unchanged': db_equal, 'database_url': str(memory.url),
                       'transport': 'local ASGI TestClient, no live server',
                       'source_still_in_hand': spell.id in controller.state.players[seat].hand},
                      stream, indent=2, sort_keys=True)
    if response.status_code == 500:
        raise UncontrolledSourceOverlap('Source-consumption exception escaped as HTTP 500')
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'illegal_action'
