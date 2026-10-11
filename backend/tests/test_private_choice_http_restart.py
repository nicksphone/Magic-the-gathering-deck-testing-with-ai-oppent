"""Real loopback HTTP + process restart, independent of whole-view adapter REDs."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from tests.closed_http_runtime import archive_closed_http_runtime


class Server:
    def __init__(self, runtime, port):
        self.root, self.port, self.token = runtime, port, str(uuid4())
        self.proc = None
        self.starts = []
        (runtime / '.private-choice-owned').write_text(self.token)

    def call(self, route, body=None, headers=None):
        request = Request(f'http://127.0.0.1:{self.port}{route}',
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json', 'X-Private-Choice-Fixture': self.token, **(headers or {})})
        try:
            with urlopen(request, timeout=15) as response:
                status, result = response.status, json.load(response)
        except HTTPError as error:
            status, result = error.code, json.load(error)
        with (self.root / 'http-receipts.jsonl').open('a') as log:
            log.write(json.dumps({'method': request.get_method(), 'route': route,
                                  'request_body': request.data.decode() if request.data is not None else None,
                                  'revision_header': request.headers.get('X-match-revision'),
                                  'response_status': status, 'response_body': result}) + '\n')
        return status, result

    def start(self):
        env = {**os.environ, 'MTG_PRIVATE_CHOICE_ROOT': str(self.root), 'MTG_PRIVATE_CHOICE_TOKEN': self.token}
        with (self.root / 'backend-process.log').open('a') as log:
            self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.private_choice_boundary_fixture_server:app',
                                          '--host', '127.0.0.1', '--port', str(self.port)],
                                         cwd=self.root / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.proc.poll() is None, 'Owned server exited; see retained process log'
            try:
                status, row = self.call('/fixture/private-choice/status')
                assert status == 200 and row['pid'] == self.proc.pid and row['root'] == str(self.root)
                self.starts.append(self.proc.pid)
                return
            except (OSError, TimeoutError):
                time.sleep(.1)
        raise AssertionError('Owned process readiness timed out')

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=5)

    def restart(self):
        prior = self.proc.pid
        self.stop()
        self.start()
        assert self.proc.pid != prior

    def audit(self, identifier):
        status, _ = self.call(f'/matches/{identifier}')
        assert status == 200
        status, row = self.call(f'/fixture/private-choice/{identifier}/audit')
        assert status == 200
        return row


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    runtime = Path(tempfile.mkdtemp(prefix='mtg-private-choice-http-')).resolve()
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).strip().startswith('nfs')
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, runtime / 'backend', ignore=shutil.ignore_patterns(
        '*.db', '*.db-*', '*.sqlite*', '.env', '.env.*', '.venv', '__pycache__', '.pytest_cache', 'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    owned = Server(runtime, port)
    try:
        owned.start()
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps({'port': port, 'pids': owned.starts, 'stopped': owned.proc is not None and owned.proc.poll() is not None}))
        # Caller archives/verifies this local evidence before cleanup, even REDs.
        print(f'OWN_HTTP_RUNTIME={runtime}')
        if owned.proc is not None:
            evidence = (Path(os.environ['MTG_CI_EVIDENCE']) if 'MTG_CI_EVIDENCE' in os.environ
                        else tmp_path_factory.getbasetemp() / 'closed-http-evidence')
            evidence.mkdir(parents=True, exist_ok=True)
            archive_closed_http_runtime(owned, runtime=runtime, data=None, evidence_root=evidence)


def _audit_json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise AssertionError('Audit must contain finite JSON values') from error


def _validate_restart_audit(row):
    assert type(row) is dict
    assert set(row) == {'pid', 'state', 'revision', 'controller', 'database_sha256',
                        'restart_stable_database_sha256', 'capacity_owner_epoch', 'capacity_ledger'}
    assert type(row['pid']) is int and row['pid'] > 0
    assert type(row['revision']) is int and row['revision'] >= 0
    assert type(row['state']) is dict and type(row['controller']) is dict
    for key, length in (('database_sha256', 64), ('restart_stable_database_sha256', 64),
                        ('capacity_owner_epoch', 32)):
        value = row[key]
        assert type(value) is str and len(value) == length and set(value) <= set('0123456789abcdef')
    ledger = row['capacity_ledger']
    numbers = {'id', 'version', 'durable_bytes', 'snapshot_rows', 'reserved_bytes', 'reserved_snapshot_rows'}
    assert type(ledger) is dict and set(ledger) == numbers | {'owner_epoch'}
    assert all(type(ledger[key]) is int and ledger[key] >= 0 for key in numbers)
    assert ledger['id'] == ledger['version'] == 1
    assert type(ledger['owner_epoch']) is str and ledger['owner_epoch'] == row['capacity_owner_epoch']
    _audit_json(row)


def stable(row, *, restart=False):
    """Default remains raw identity; only explicit restart comparison omits epoch operands."""
    assert type(row) is dict and type(restart) is bool
    new_schema = 'restart_stable_database_sha256' in row or 'capacity_owner_epoch' in row
    if new_schema:
        _validate_restart_audit(row)
    if not restart:
        return {key: value for key, value in row.items() if key != 'pid'}
    assert new_schema, 'Restart proof requires the complete epoch audit contract'
    projected = {key: value for key, value in row.items()
                 if key not in {'pid', 'database_sha256', 'capacity_owner_epoch'}}
    projected['capacity_ledger'] = {key: value for key, value in row['capacity_ledger'].items()
                                    if key != 'owner_epoch'}
    return projected


def assert_restart_audit(before, after, *, previous_pid, current_pid, previous_returncode):
    """Bind the typed SQL/epoch proof to the actual stopped and current child processes."""
    _validate_restart_audit(before)
    _validate_restart_audit(after)
    assert type(previous_pid) is int and type(current_pid) is int
    assert previous_pid > 0 and current_pid > 0 and previous_pid != current_pid
    assert before['pid'] == previous_pid and after['pid'] == current_pid
    assert type(previous_returncode) is int and previous_returncode in (0, -signal.SIGTERM)
    assert before['capacity_owner_epoch'] != after['capacity_owner_epoch']
    assert before['database_sha256'] != after['database_sha256']
    assert before['restart_stable_database_sha256'] == after['restart_stable_database_sha256']
    assert _audit_json(stable(before, restart=True)) == _audit_json(stable(after, restart=True))


def fixture(server, family, seat):
    status, row = server.call(f'/fixture/private-choice?family={family}&seat={seat}', {})
    assert status == 200, row
    return row


def choice(view, family, decline):
    token = ('decline' if decline else 'reveal') if family == 'delver' else '__none__' if decline else next(x for x in view['options'] if x != '__none__')
    return {'type': 'choose_mechanic', 'card_ids': [token]}


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_real_http_explicit_choice_privacy_stale_database_and_two_restarts(server, family, seat, decline):
    data = fixture(server, family, seat)
    identifier = data['id']
    base = f'/matches/{identifier}'
    before = server.audit(identifier)
    status, legal = server.call(base + f'/legal-moves?player_id={seat}')
    assert status == 200
    view = legal['moves'][0]
    assert [c['id'] for c in view['inspected_cards']] == data['inspected_ids']
    action = choice(view, family, decline)
    _, other = server.call(base + f'/legal-moves?player_id={3-seat}')
    assert not other['moves'] and not any(cid in json.dumps(other) for cid in data['inspected_ids'])
    _, actor = server.call(f'/fixture/private-choice/{identifier}/observe?seat={seat}')
    _, foreign = server.call(f'/fixture/private-choice/{identifier}/observe?seat={3-seat}')
    assert data['foreign_hand_id'] not in json.dumps(actor)
    assert all(cid in actor['known_cards'] and cid not in foreign['known_cards'] for cid in data['inspected_ids'])
    assert stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(base + '/action', {'player_id': 3-seat, 'action': action})
    assert status in (403, 422) and stable(server.audit(identifier)) == stable(before)
    for extra in ({'unknown': None}, {'targets': {'card_ids': action['card_ids']}}, {'card_ids': None}):
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': {**action, **extra}})
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': {**view, **action}})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    previous_process = server.proc
    server.restart()
    restored = server.audit(identifier)
    assert_restart_audit(before, restored, previous_pid=previous_process.pid,
                         current_pid=server.proc.pid, previous_returncode=previous_process.poll())
    assert restored['pid'] != before['pid'] and stable(restored, restart=True) == stable(before, restart=True)
    status, normalized = server.call(f'/fixture/private-choice/{identifier}/intent?seat={seat}', action)
    assert status == 200 and normalized['action'] == action
    assert stable(server.audit(identifier)) == stable(restored)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': normalized['action']},
                            {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 200
    after = server.audit(identifier)
    assert after['revision'] == before['revision'] + 1
    assert not after['state']['pending_mechanic_choice'] and not after['state']['stack']
    if family == 'delver':
        source = before['state']['pending_mechanic_choice']['effect_payload']['target_card_id']
        assert (after['state']['cards'][source]['selected_face_index'] or 0) == (0 if decline else 1)
        assert after['state']['players'][str(seat)]['library'] == before['state']['players'][str(seat)]['library']
        if decline:
            assert not any('reveals' in line for line in after['state']['log'])
    else:
        assert after['state']['players'][str(seat)]['hand'] == ([] if decline else action['card_ids'])
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': action},
                            {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 409 and stable(server.audit(identifier)) == stable(after)
    previous_process = server.proc
    server.restart()
    final = server.audit(identifier)
    assert_restart_audit(after, final, previous_pid=previous_process.pid,
                         current_pid=server.proc.pid, previous_returncode=previous_process.poll())
    assert final['pid'] != after['pid'] and stable(final, restart=True) == stable(after, restart=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['delver', 'officer'])
@pytest.mark.parametrize('decline', [False, True])
def test_real_http_whole_owned_view_normalizes_only_explicit_selection(server, family, seat, decline):
    data = fixture(server, family, seat)
    identifier = data['id']
    before = server.audit(identifier)
    _, legal = server.call(f'/matches/{identifier}/legal-moves?player_id={seat}')
    view = legal['moves'][0]
    action = choice(view, family, decline)
    status, normalized = server.call(f'/fixture/private-choice/{identifier}/intent?seat={seat}', {**view, **action})
    assert stable(server.audit(identifier)) == stable(before)
    assert status == 200 and normalized['action'] == action, normalized
