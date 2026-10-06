"""Actual tap costs, private identities, atomic API rejects and cold restart."""
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
from tests.test_private_choice_http_restart import Server, stable
from tests.test_activated_handland_instruction_audit import FAMILIES


class ActivatedServer(Server):
    def start(self):
        env = {**os.environ, 'MTG_PRIVATE_CHOICE_ROOT': str(self.root),
               'MTG_PRIVATE_CHOICE_TOKEN': self.token}
        with (self.root / 'backend-process.log').open('a') as log:
            self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'tests.activated_handland_http_fixture_server:app', '--host', '127.0.0.1',
                '--port', str(self.port)], cwd=self.root / 'backend', env=env,
                stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.proc.poll() is None, 'Owned fixture process exited'
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
    parent = Path(os.environ['MTG_LAND_CHOICE_STAGE_EVIDENCE']).resolve()
    runtime = Path(tempfile.mkdtemp(prefix='http-local-', dir=parent))
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).strip().startswith('nfs')
    shutil.copytree(Path(__file__).resolve().parents[1], runtime / 'backend',
        ignore=shutil.ignore_patterns('*.db*', '*.sqlite*', '.env*', '.venv',
          '__pycache__', '.pytest_cache', 'test-tmp*', 'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    owned = ActivatedServer(runtime, port)
    try:
        owned.start()
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps(
            {'port': port, 'pids': owned.starts, 'stopped': owned.proc.poll() is not None}))


def position(server, family, seat, sick=False):
    status, data = server.call('/fixture/activated-handland?family=' + quote(family)
                             + f'&seat={seat}&sick={str(sick).lower()}', {})
    assert status == 200, data
    return data, '/matches/' + data['id']


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('select', [False, True])
def test_real_http_tap_selected_second_or_decline_private_root_sql_cold_restart(server, seat, family, select):
    data, base = position(server, family, seat)
    before = server.audit(data['id'])
    assert before['state']['active_player'] == 3-seat
    request = {'type': 'activate_ability', 'card_id': data['source_id'], 'ability_index': 0, 'targets': {}}
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': request})
    assert status == 200
    paid = server.audit(data['id'])
    assert paid['state']['cards'][data['source_id']]['tapped']
    assert not before['state']['cards'][data['source_id']]['tapped']
    server.restart()
    assert stable(server.audit(data['id'])) == stable(paid)
    for _ in range(8):
        current = server.audit(data['id'])
        if current['state']['pending_mechanic_choice']:
            break
        assert current['state']['stack'], 'Missing real land-choice continuation'
        status, _ = server.call(base + '/action', {'player_id': current['state']['priority_player'],
                                                  'action': {'type': 'pass_priority'}})
        assert status == 200
    pending = server.audit(data['id'])
    assert pending['state']['pending_mechanic_choice']['kind'] == 'land_from_hand'
    status, public = server.call(base)
    assert status == 200 and set(public['pending_mechanic_choice']) == {'kind', 'player_id', 'label', 'count', 'min_count'}
    status, other = server.call(base + f'/legal-moves?player_id={3-seat}')
    assert status == 200 and not other['moves']
    assert not any(cid in json.dumps(other) for cid in data['land_ids'])
    choice = {'type': 'choose_mechanic', 'card_ids': [data['land_ids'][1]] if select else []}
    for actor, payload in [(3-seat, choice),
        (seat, {**choice, 'card_ids': [data['enemy_id']]}),
        (seat, {**choice, 'card_ids': [data['land_ids'][1]] * 2}),
        (seat, {**choice, 'unknown': None})]:
        status, _ = server.call(base + '/action', {'player_id': actor, 'action': payload})
        assert status in (403, 422) and stable(server.audit(data['id'])) == stable(pending)
    server.restart()
    assert stable(server.audit(data['id'])) == stable(pending)
    status, response = server.call(base + '/action', {'player_id': seat, 'action': choice})
    assert status == 200, response
    after = server.audit(data['id'])
    player = after['state']['players'][str(seat)]
    assert data['land_ids'][0] in player['hand']
    assert data['land_ids'][1] in player['battlefield' if select else 'hand']
    assert player['lands_played_this_turn'] == 1
    if select:
        assert not after['state']['cards'][data['land_ids'][1]]['tapped']
    server.restart()
    assert stable(server.audit(data['id'])) == stable(after)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', FAMILIES)
def test_summoning_sick_real_tap_rejected_http_full_root_and_database(server, seat, family):
    data, base = position(server, family, seat, sick=True)
    before = server.audit(data['id'])
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': {
        'type': 'activate_ability', 'card_id': data['source_id'], 'ability_index': 0, 'targets': {}}})
    assert status == 422 and stable(server.audit(data['id'])) == stable(before)
