"""Owned SQLite backup/restore, then saved-game retries in a fresh app process.

Battle positions are declared canonical midgame fixtures. HTTP is ASGI
TestClient, not TCP/browser refresh. The cold worker opens only the restored
file, never the original database. No pool disposal while its owner is live.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlmodel import Session, create_engine

from persistence.capacity import owner_for_engine
from scripts.verify_storage_restore import fingerprint, verify_restore
from tests.temporary_characteristics_http_fixture import owned_database
from tests.test_battle_http_recovery import combat, headers, recovery_api  # noqa: F401


def saved_rows(path):
    """Application records only; capacity epochs legitimately change on startup."""
    queries = {'activematchrecord': 'SELECT * FROM activematchrecord ORDER BY id',
               'matchstartreceipt': 'SELECT * FROM matchstartreceipt ORDER BY key'}
    with closing(sqlite3.connect(path)) as conn:
        return {name: conn.execute(query).fetchall() for name, query in queries.items()}


def test_registered_owner_backup_restores_populated_schema_without_overwrite(tmp_path, monkeypatch):
    import main
    import persistence.db as db
    from starlette.requests import Request
    from persistence.repository import Repository
    source, backup = tmp_path / 'source.db', tmp_path / 'backup.db'
    directory = tmp_path / 'clean'
    directory.mkdir(mode=0o700)
    restored = directory / 'restored.db'
    engine = create_engine('sqlite:///' + str(source))
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(main, 'ACTIVE_MATCHES', {})
    try:
        with owned_database(engine) as owner:
            controller, _, _, body = combat(SimpleNamespace(main=main, engine=engine), 1)
            request = Request({'type': 'http', 'headers': [
                (b'idempotency-key', b'owner-backup'), (b'x-match-revision', b'0')]})
            with Session(engine) as session:
                accepted = main.take_action(controller.state.id,
                    main.ActionRequest.model_validate(body), Repository(session), request)
            assert accepted['revision'] == 1
            assert 'owner-backup' in controller.mutation_receipts
            before = saved_rows(source)
            expected = owner.backup(backup)
            result = verify_restore(None, backup, restored)
            assert {key: result[key] for key in expected} == expected
            assert saved_rows(restored) == before
            with closing(sqlite3.connect(restored)) as conn:
                assert fingerprint(conn) == expected
            original = backup.read_bytes()
            with pytest.raises(FileExistsError):
                owner.backup(backup)
            assert backup.read_bytes() == original
            original = restored.read_bytes()
            with pytest.raises(FileExistsError):
                verify_restore(None, backup, restored)
            assert restored.read_bytes() == original
            assert owner_for_engine(engine) is owner  # owner/pool still usable
            # Reconstruct through the real saved-game loader, independently of
            # the HTTP/child cases. Only capacity bookkeeping may change.
            from game_state.serializers import serialize_match_snapshot
            expected_state = serialize_match_snapshot(controller.state)
            expected_controller = main._controller_snapshot(controller)
            recovered_engine = create_engine('sqlite:///' + str(restored))
            try:
                with owned_database(recovered_engine):
                    main.ACTIVE_MATCHES.pop(controller.state.id)
                    with Session(recovered_engine) as session:
                        main._restore_active_matches(Repository(session), controller.state.id)
                    recovered = main.ACTIVE_MATCHES[controller.state.id]
                    assert recovered is not controller
                    assert serialize_match_snapshot(recovered.state) == expected_state
                    assert main._controller_snapshot(recovered) == expected_controller
                    assert saved_rows(restored) == before
            finally:
                recovered_engine.dispose()
    finally:
        engine.dispose()


@pytest.mark.parametrize('seat', [1, 2])
def test_backup_restores_real_start_and_action_receipts_in_cold_app(
        recovery_api, tmp_path, seat):
    api = recovery_api
    controller, _, _, body = combat(api, seat)
    mid = controller.state.id
    accepted = api.client.post(f'/matches/{mid}/action', json=body,
                               headers=headers('backed-up-action'))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['revision'] == 1
    start_body = {'deck_a': [{'card_name': 'Island', 'quantity': 60}],
                  'deck_b': [{'card_name': 'Island', 'quantity': 60}],
                  'controller_a': 'human', 'controller_b': 'human',
                  'mode': 'human_vs_human', 'seed': 71931}
    started = api.client.post('/matches/start', json=start_body,
                              headers={'Idempotency-Key': 'backed-up-start'})
    assert started.status_code == 200, started.text
    start_id = started.json()['id']
    views = {}
    for match_id in (mid, start_id):
        view = api.client.get(f'/matches/{match_id}')
        assert view.status_code == 200, view.text
        views[match_id] = view.json()
    rows = saved_rows(api.path)
    backup = tmp_path / 'backup.db'
    expected_fingerprint = owner_for_engine(api.engine).backup(backup)
    # Real later commit must not appear in this point-in-time backup.
    later = api.client.post('/matches/start', json={**start_body, 'seed': 71932},
                            headers={'Idempotency-Key': 'after-backup'})
    assert later.status_code == 200, later.text
    later_id = later.json()['id']
    assert saved_rows(api.path) != rows
    directory = tmp_path / 'clean-restore'
    directory.mkdir(mode=0o700)
    restored = directory / 'restored.db'
    result = verify_restore(None, backup, restored)
    assert {key: result[key] for key in expected_fingerprint} == expected_fingerprint
    assert saved_rows(restored) == rows
    evidence = tmp_path / 'expected.json'
    evidence.write_text(json.dumps({'views': views, 'rows': rows, 'action': body,
        'match_id': mid, 'start_id': start_id, 'start_body': start_body,
        'later_id': later_id}))
    # The source remains live under its original owner; the child uses a
    # different file/owner. This also catches accidental source-path fallback.
    source_before = saved_rows(api.path)
    environment = os.environ.copy()
    environment['MTG_DATABASE_PATH'] = str(restored)
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    worker = Path(__file__).with_name('saved_game_restore_worker.py')
    child = subprocess.run([sys.executable, '-B', str(worker), str(restored),
                            str(evidence)], env=environment, text=True,
                           capture_output=True, timeout=45,
                           cwd=Path(__file__).resolve().parents[1])
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {'matches': 2, 'revision': 1,
        'action_retry': 200, 'start_retry': 200, 'stale': 409,
        'conflict': 409, 'later_match': 404, 'saved_rows_unchanged': True}
    assert saved_rows(api.path) == source_before
