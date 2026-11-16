"""Fresh-process application acceptance for a restored pytest-owned database."""
import json
import os
from pathlib import Path
import sys


def main():
    database, expected_path = sys.argv[1:]
    assert str(Path(database).resolve()) == os.environ['MTG_DATABASE_PATH']
    expected = json.loads(Path(expected_path).read_text())
    import main as app
    from fastapi.testclient import TestClient
    from tests.temporary_characteristics_http_fixture import owned_database
    from tests.saved_game_rows import saved_rows

    def stored():
        # JSON representation only converts SQLite tuples to lists, no filtering.
        return json.loads(json.dumps(saved_rows(database)))

    with owned_database(app.engine):
        assert app.ACTIVE_MATCHES == {}
        assert stored() == expected['rows']
        client = TestClient(app.app)
        try:
            for mid, view in expected['views'].items():
                current = client.get(f'/matches/{mid}')
                assert current.status_code == 200, current.text
                assert current.json() == view
            mid = expected['match_id']
            path = f'/matches/{mid}/action'
            action = client.post(path, json=expected['action'], headers={
                'Idempotency-Key': 'backed-up-action', 'X-Match-Revision': '0'})
            assert action.status_code == 200, action.text
            assert action.json() == expected['views'][mid]
            stale = client.post(path, json=expected['action'], headers={
                'Idempotency-Key': 'new-intent', 'X-Match-Revision': '0'})
            assert stale.status_code == 409, stale.text
            assert stale.json()['detail']['code'] == 'stale_revision'
            conflict = client.post(path, json={**expected['action'],
                'action': {'type': 'pass_priority'}}, headers={
                'Idempotency-Key': 'backed-up-action', 'X-Match-Revision': '1'})
            assert conflict.status_code == 409, conflict.text
            assert conflict.json()['detail']['code'] == 'idempotency_conflict'
            start = client.post('/matches/start', json=expected['start_body'],
                                headers={'Idempotency-Key': 'backed-up-start'})
            assert start.status_code == 200, start.text
            assert start.json() == expected['views'][expected['start_id']]
            later = client.get('/matches/' + expected['later_id'])
            assert later.status_code == 404, later.text
            assert stored() == expected['rows']
            print(json.dumps({'matches': 2, 'revision': 1,
                'action_retry': action.status_code, 'start_retry': start.status_code,
                'stale': stale.status_code, 'conflict': conflict.status_code,
                'later_match': later.status_code, 'saved_rows_unchanged': True}))
        finally:
            client.close()
    app.engine.dispose()


if __name__ == '__main__':
    main()
