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
def server():
    runtime = Path(tempfile.mkdtemp(prefix='mtg-private-choice-http-')).resolve()
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).strip().startswith('nfs')
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, runtime / 'backend', ignore=shutil.ignore_patterns(
        '*.db', '*.db-*', '*.sqlite*', '.env', '.env.*', '.venv', '__pycache__', '.pytest_cache', 'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    owned = Server(runtime, port)
    owned.start()
    try:
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps({'port': port, 'pids': owned.starts, 'stopped': owned.proc.poll() is not None}))
        # Caller archives/verifies this local evidence before cleanup, even REDs.
        print(f'OWN_HTTP_RUNTIME={runtime}')


def stable(row):
    return {key: value for key, value in row.items() if key != 'pid'}


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
    server.restart()
    restored = server.audit(identifier)
    assert restored['pid'] != before['pid'] and stable(restored) == stable(before)
    status, normalized = server.call(f'/fixture/private-choice/{identifier}/intent?seat={seat}', action)
    assert status == 200 and normalized['action'] == action
    assert stable(server.audit(identifier)) == stable(before)
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
    server.restart()
    final = server.audit(identifier)
    assert final['pid'] != after['pid'] and stable(final) == stable(after)


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
