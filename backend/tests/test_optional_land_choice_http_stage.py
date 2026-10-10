"""Actual HTTP/restart; handler-only slice explicitly separate from paid paths."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

import pytest

from tests.test_private_choice_http_restart import stable
from tests.cold_restart_http_support import Server


class LandServer(Server):
    def start(self):
        env = self.environment()
        with (self.root / 'backend-process.log').open('a') as log:
            self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'tests.optional_land_choice_http_fixture_server:app', '--host', '127.0.0.1',
                '--port', str(self.port)], cwd=self.root / 'backend', env=env,
                stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.proc.poll() is None, 'Owned fixture server exited'
            try:
                status, row = self.call('/fixture/private-choice/status')
                if status == 200:
                    assert row['pid'] == self.proc.pid and row['root'] == str(self.root)
                    self.starts.append(self.proc.pid)
                    return
            except (OSError, TimeoutError):
                time.sleep(.1)
        raise AssertionError('Owned readiness bound exceeded')


@pytest.fixture(scope='module')
def server():
    parent = os.environ.get('MTG_LAND_CHOICE_STAGE_EVIDENCE')
    assert parent and Path(parent).is_dir()
    runtime = Path(tempfile.mkdtemp(prefix='http-local-', dir=parent)).resolve()
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source, runtime / 'backend', ignore=shutil.ignore_patterns(
        '*.db', '*.db-*', '*.sqlite*', '.env*', '.venv', '__pycache__', '.pytest_cache',
        'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    owned = LandServer(runtime, port)
    try:
        owned.start()
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps(
            {'port': port, 'pids': owned.starts, 'stopped': owned.proc.poll() is not None}))


@pytest.mark.parametrize('seat', [1, 2])
def test_actual_api_slice_private_selected_cold_restore_reject_root_db(server, seat):
    status, data = server.call(f'/fixture/private-choice?family=Growth%20Spiral&seat={seat}&slice_only=true', {})
    assert status == 200 and data['slice_only'] is True
    base = '/matches/' + data['id']
    before = server.audit(data['id'])
    status, public = server.call(base)
    assert status == 200 and set(public['pending_mechanic_choice']) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    status, actor = server.call(base + f'/legal-moves?player_id={seat}')
    assert status == 200 and actor['moves'][0]['options'] == [data['land_id']]
    status, other = server.call(base + f'/legal-moves?player_id={3-seat}')
    assert status == 200 and not other['moves']
    assert data['land_id'] not in json.dumps(other)
    choice = {'type': 'choose_mechanic', 'card_ids': [data['land_id']]}
    for actor_id, payload in [(3-seat, choice), (seat, {**choice, 'unknown': None}),
                              (seat, {**choice, 'card_ids': None}),
                              (seat, {'type': 'choose_mechanic', 'choice_id': data['land_id']})]:
        status, _ = server.call(base + '/action', {'player_id': actor_id, 'action': payload})
        assert status in (403, 422) and stable(server.audit(data['id'])) == stable(before)
    before = server.restart(data['id'], before)
    assert stable(server.audit(data['id'])) == stable(before)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': choice})
    assert status == 200
    after = server.audit(data['id'])
    assert data['land_id'] in after['state']['players'][str(seat)]['battlefield']
    assert after['state']['players'][str(seat)]['lands_played_this_turn'] == 1
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': choice})
    assert status == 422 and stable(server.audit(data['id'])) == stable(after)
    after = server.restart(data['id'], after)
    assert stable(server.audit(data['id'])) == stable(after)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['Growth Spiral', 'Arboreal Grazer'])
def test_real_paid_http_family_has_optional_continuation_desired(server, seat, family):
    status, data = server.call(f'/fixture/private-choice?family={quote(family)}&seat={seat}', {})
    assert status == 200 and data['slice_only'] is False
    base = '/matches/' + data['id']
    status, _ = server.call(base + '/action', {'player_id': seat,
        'action': {'type': 'cast_spell', 'card_id': data['source_id'], 'cost_choice': {'id': 'base'}}})
    assert status == 200
    announced = server.audit(data['id'])
    assert announced['state']['stack'][-1]['payload']['mana_spent'] == (2 if family == 'Growth Spiral' else 1)
    announced = server.restart(data['id'], announced)
    assert stable(server.audit(data['id'])) == stable(announced)
    for _ in range(8):
        row = server.audit(data['id'])
        if row['state']['pending_mechanic_choice'] or row['state']['pending_trigger_order'] or not row['state']['stack']:
            break
        status, _ = server.call(base + '/action', {'player_id': row['state']['priority_player'],
                                                   'action': {'type': 'pass_priority'}})
        assert status == 200
    resolved = server.audit(data['id'])
    assert data['land_id'] in resolved['state']['players'][str(seat)]['hand']
    assert resolved['state']['pending_mechanic_choice'] or resolved['state']['pending_trigger_order'], \
        'Actual paid path still lacks frozen compiler dependency; no caller-forced put'
