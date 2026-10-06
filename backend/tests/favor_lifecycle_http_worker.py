"""Cold ASGI HTTP restore and deliberate action against the owned local SQLite."""
import json
import os
from pathlib import Path
import sys

root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve()
backend = Path(__file__).resolve().parents[1]
assert backend.parent == root
sys.path.insert(0, str(backend))
database, expected_path, output_path = map(Path, sys.argv[1:])
assert all(path.resolve().is_relative_to(root) for path in (database, expected_path, output_path))


def guard(event, args):
    if event == 'socket.connect':
        raise AssertionError('No network or live service in owned cold ASGI worker')
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        assert Path(str(args[0])).resolve().is_relative_to(root)


sys.addaudithook(guard)

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
import main
from persistence.repository import Repository
from tests.favor_lifecycle_support import assert_private, snap
from tests.test_spell_admission_safety_http import sql_facts

expected = json.loads(expected_path.read_text())
engine = create_engine('sqlite:///' + str(database), connect_args={'check_same_thread': False})
main.engine = engine
main.ACTIVE_MATCHES = {}
with Session(engine) as session:
    repo = Repository(session)
    main.app.dependency_overrides[main.get_repo] = lambda: repo

    def forbidden(*args, **kwargs):
        raise AssertionError('No startup or default database in owned cold ASGI worker')

    main.init_db = main.app.router.lifespan_context = forbidden
    main._restore_active_matches(repo, expected['match_id'])
    controller = main.ACTIVE_MATCHES[expected['match_id']]
    actual = {'root': snap(controller.state), 'controller': main._controller_snapshot(controller),
              'sql': sql_facts(repo)}
    assert json.loads(json.dumps(actual)) == expected['before']
    client = TestClient(main.app)  # Deliberately never enter lifespan.
    path = '/matches/' + expected['match_id']
    try:
        public = client.get(path)
        assert public.status_code == 200, public.text
        assert set(public.json()['pending_mechanic_choice']) <= {'kind', 'player_id', 'label', 'count', 'min_count'}
        for actor in (1, 2):
            response = client.get(path + f'/legal-moves?player_id={actor}')
            assert response.status_code == 200, response.text
            assert bool(response.json()['moves']) == (actor == expected['affected'])
        assert_private(controller.state, expected['affected'])
        before = snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)
        rejected = client.post(path + '/action', json={'player_id': 3-expected['affected'],
                                                      'action': expected['choice']})
        assert rejected.status_code in (403, 422), rejected.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
        response = client.post(path + '/action', json={'player_id': expected['affected'],
                                                      'action': expected['choice']})
        assert response.status_code == 200, response.text
        controller = main.ACTIVE_MATCHES[expected['match_id']]
        assert_private(controller.state, expected['affected'])
        result = {'root': snap(controller.state), 'controller': main._controller_snapshot(controller),
                  'sql': sql_facts(repo)}
        output_path.write_text(json.dumps(result, sort_keys=True))
        print(json.dumps({'cold_asgi_restore': True, 'both_seat_legal_queries': True,
                          'wrong_actor_atomic': True, 'actual_deliberate_choice_post': True,
                          'private_projection_checked': True}))
    finally:
        client.close()
engine.dispose()
