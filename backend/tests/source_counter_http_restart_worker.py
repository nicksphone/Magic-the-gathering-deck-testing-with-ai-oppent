"""Actual cold HTTP restore of an owned database; no lifespan/default DB."""
import json
import os
from pathlib import Path
import sys

def canonical_path(value):
    path = Path(value)
    assert path.is_absolute()
    assert not any(part.is_symlink() for part in (path, *path.parents))
    assert path == path.resolve()
    return path


root = canonical_path(os.environ['MTG_ISOLATED_TEST_ROOT'])
backend = Path(__file__).resolve().parents[1]
assert backend.parent == root
sys.path.insert(0, str(backend))
owned_roots = [root]
# CI keeps pytest databases beside, not inside, its immutable source tree.
temp_value = os.environ.get('PYTEST_DEBUG_TEMPROOT') or os.environ.get('TMPDIR')
if temp_value:
    temp = canonical_path(temp_value)
    assert temp.is_dir() and temp.parent == root.parent and temp != root
    owned_roots.append(temp)


def owned_path(value):
    path = canonical_path(value)
    assert any(path != base and path.is_relative_to(base) for base in owned_roots)
    return path


database, expected_path = map(Path, sys.argv[1:])
owned_path(database)
owned_path(expected_path)


def guard(event, args):
    if event == 'socket.connect':
        raise AssertionError('No remote connection in HTTP restore worker')
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        owned_path(str(args[0]))


sys.addaudithook(guard)

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
import main
from persistence.repository import Repository
from tests.test_batch_graveyard_publication_audit import assert_private
from tests.test_self_graveyard_replacement_audit import snap
from tests.test_spell_admission_safety_http import sql_facts

expected = json.loads(expected_path.read_text())
engine = create_engine('sqlite:///'+str(database), connect_args={'check_same_thread': False})
main.engine = engine
main.ACTIVE_MATCHES = {}
with Session(engine) as session:
    repo = Repository(session)
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    def forbidden(*args, **kwargs):
        raise AssertionError('No startup/default database in owned HTTP restore worker')
    main.init_db = main.app.router.lifespan_context = forbidden
    main._restore_active_matches(repo, expected['match_id'])
    match = main.ACTIVE_MATCHES[expected['match_id']]
    client = TestClient(main.app)  # No context entry: lifespan must not run.
    try:
        response = client.get('/matches/'+expected['match_id'])
        assert response.status_code == 200, response.text
        for seat in (1, 2):
            response = client.get('/matches/'+expected['match_id']+f'/legal-moves?player_id={seat}')
            assert response.status_code == 200, response.text
        assert_private(match.state)
        actual = {'match_id': match.state.id, 'root': snap(match.state),
                  'controller': main._controller_snapshot(match), 'sql': sql_facts(repo)}
        assert json.loads(json.dumps(actual)) == expected
        print(json.dumps({'cold_http_restore': True, 'both_seat_queries': True,
                          'root_controller_sql_exact': True, 'privacy': True}))
    finally:
        client.close()
engine.dispose()
