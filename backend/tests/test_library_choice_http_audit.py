"""Actual checked HTTP actions, private views and restart; raw-view audit REDs."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from tests.test_private_choice_http_restart import Server, stable
from tests.test_library_choice_intent_audit import PHASES, explicit, expected_transition


class LibraryServer(Server):
    def start(self):
        env = {**os.environ, 'MTG_PRIVATE_CHOICE_ROOT': str(self.root), 'MTG_PRIVATE_CHOICE_TOKEN': self.token}
        with (self.root / 'backend-process.log').open('a') as log:
            self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'tests.library_choice_fixture_server:app',
                                          '--host', '127.0.0.1', '--port', str(self.port)],
                                         cwd=self.root / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.proc.poll() is None, 'See owned process log'
            try:
                status, row = self.call('/fixture/private-choice/status')
                assert status == 200 and row['pid'] == self.proc.pid and row['root'] == str(self.root)
                self.starts.append(self.proc.pid)
                return
            except (OSError, TimeoutError):
                time.sleep(.1)
        raise AssertionError('Owned process readiness timed out')


@pytest.fixture(scope='module')
def server():
    runtime = Path(tempfile.mkdtemp(prefix='mtg-library-choice-http-')).resolve()
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).strip().startswith('nfs')
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, runtime / 'backend', ignore=shutil.ignore_patterns(
        '*.db', '*.db-*', '*.sqlite*', '.env', '.env.*', '.venv', '__pycache__', '.pytest_cache', 'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    owned = LibraryServer(runtime, port)
    try:
        owned.start()
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps({'port': port, 'pids': owned.starts,
                                                               'stopped': owned.proc.poll() is not None}))
        print(f'OWN_HTTP_RUNTIME={runtime}')


def fixture(server, name, seat, order):
    query = urlencode({'name': name, 'seat': seat, 'order': str(order).lower()})
    status, data = server.call('/fixture/library-choice?' + query, {})
    assert status == 200, data
    return data


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_http_policy_minimal_actions_private_roots_and_restart(server, name, order, seat):
    data = fixture(server, name, seat, order)
    identifier = data['id']
    base = f'/matches/{identifier}'
    intent = f'/fixture/private-choice/{identifier}/intent?seat={seat}'
    for stage in range(3):
        before = server.audit(identifier)
        state = deserialize_match_snapshot(before['state'])
        chosen = explicit(state)
        status, legal = server.call(base + f'/legal-moves?player_id={seat}')
        assert status == 200
        view = legal['moves'][0]
        status, actor = server.call(f'/fixture/private-choice/{identifier}/observe?seat={seat}')
        assert status == 200
        hint = actor['pending_choice']['prompts'][0]['hint']
        status, other = server.call(f'/fixture/private-choice/{identifier}/observe?seat={3-seat}')
        assert status == 200
        assert data['foreign_hand_id'] not in json.dumps(actor)
        assert all(cid in actor['known_cards'] and cid not in other['known_cards'] for cid in view['options'])
        assert all(cid not in actor['known_cards'] for cid in data['outside_ids'])
        status, foreign = server.call(base + f'/legal-moves?player_id={3-seat}')
        assert status == 200 and not foreign['moves']
        assert not any(cid in json.dumps(foreign) for cid in view['options'])
        assert stable(server.audit(identifier)) == stable(before)
        status, _ = server.call(base + '/action', {'player_id': 3-seat, 'action': chosen})
        assert status in (403, 422) and stable(server.audit(identifier)) == stable(before)
        for extra in ({'unknown': None}, {'selected_card_ids': None}, {'targets': {'card_ids': chosen['card_ids']}}, {'card_ids': None}):
            for route, body in ((intent, {**chosen, **extra}),
                                (base + '/action', {'player_id': seat, 'action': {**chosen, **extra}})):
                status, _ = server.call(route, body)
                assert status == 422 and stable(server.audit(identifier)) == stable(before)
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': {**view, **chosen}})
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
        server.restart()
        assert stable(server.audit(identifier)) == stable(before)
        for request in (chosen, {**hint, **chosen}, {**chosen, 'choice_id': None, 'damage_assignment': None}):
            status, normalized = server.call(intent, request)
            assert status == 200 and normalized['action'] == chosen
            assert stable(server.audit(identifier)) == stable(before)
        expected = json.loads(json.dumps(serialize_match_snapshot(expected_transition(state, chosen))))
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': normalized['action']},
                               {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
        assert status == 200
        after = server.audit(identifier)
        assert after['state'] == expected and after['revision'] == before['revision'] + 1
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': chosen},
                               {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
        assert status == 409 and stable(server.audit(identifier)) == stable(after)
        status, _ = server.call(intent, {**hint, **chosen})
        assert status == 422 and stable(server.audit(identifier)) == stable(after)
        server.restart()
        assert stable(server.audit(identifier)) == stable(after)
        if not after['state']['pending_mechanic_choice']:
            break
    assert not server.audit(identifier)['state']['pending_mechanic_choice']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name,order', PHASES)
def test_http_actual_raw_whole_view_requires_exact_consumer_support(server, name, order, seat):
    data = fixture(server, name, seat, order)
    identifier = data['id']
    before = server.audit(identifier)
    _, legal = server.call(f'/matches/{identifier}/legal-moves?player_id={seat}')
    chosen = explicit(deserialize_match_snapshot(before['state']))
    request = {**deepcopy(legal['moves'][0]), **chosen}
    status, result = server.call(f'/fixture/private-choice/{identifier}/intent?seat={seat}', request)
    assert stable(server.audit(identifier)) == stable(before)
    assert status == 200 and result['action'] == chosen, result
