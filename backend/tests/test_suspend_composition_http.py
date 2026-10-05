"""Full frozen composition over loopback HTTP; no parent DB/process access."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

SOURCE = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.environ.get('MTG_SUSPEND_COMPOSITION_HTTP') != '1',
                              reason='Explicit isolated real-HTTP composition gate required')


class Server:
    def __init__(self, runtime, token, port):
        self.runtime, self.token, self.port = runtime, token, port
        self.process = None
        self.requests, self.pids = [], []

    def request(self, route, body=None, *, method=None, expected=200):
        method = method or ('POST' if body is not None else 'GET')
        data = json.dumps(body).encode() if body is not None else None
        request = Request(f'http://127.0.0.1:{self.port}{route}', data=data, method=method,
                          headers={'Content-Type': 'application/json', 'X-Suspend-Fixture': self.token})
        try:
            with urlopen(request, timeout=20) as response:
                status, payload = response.status, response.read()
        except HTTPError as error:
            status, payload = error.code, error.read()
        self.requests.append({'route': route, 'method': method, 'body': body, 'status': status})
        assert status == expected, (route, status, payload.decode())
        return json.loads(payload)

    def start(self):
        with (self.runtime / 'backend.log').open('ab') as log:
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'tests.suspend_composition_fixture:app',
                 '--host', '127.0.0.1', '--port', str(self.port)],
                cwd=self.runtime / 'backend', stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, 'MTG_SUSPEND_FIXTURE_ROOT': str(self.runtime),
                     'MTG_SUSPEND_FIXTURE_TOKEN': self.token, 'PYTHONDONTWRITEBYTECODE': '1',
                     'PYTHONPATH': str(self.runtime / 'backend')},
            )
        self.pids.append(self.process.pid)
        print(f'OWN HTTP PID={self.process.pid} port={self.port} root={self.runtime}', flush=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.process.poll() is None, (self.runtime / 'backend.log').read_text()
            try:
                status = self.request('/fixture/suspend/status')
                assert status['source_root'] == str(self.runtime)
                return
            except (URLError, ConnectionError, TimeoutError):
                time.sleep(0.1)
        raise AssertionError('Owned HTTP server startup exceeded 60 seconds')

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)


@pytest.fixture(scope='module')
def http_server():
    assert os.environ.get('MTG_SUSPEND_COMPOSITION_HTTP') == '1', 'Explicit composed HTTP gate required'
    archive_root = Path(os.environ['MTG_SUSPEND_COMPOSITION_ARCHIVE']).resolve()
    existing = archive_root
    while not existing.exists(): existing = existing.parent
    assert subprocess.check_output(['findmnt', '-n', '-T', str(existing), '-o', 'FSTYPE'],
                                   text=True).strip().splitlines()[-1] in {'nfs', 'nfs4'}
    archive_root.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix='mtg-suspend-composition-http-'))
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).startswith('nfs')
    inventory = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                         '--exclude-standard', '--', 'backend',
                                         'frontend/tests/suspend_fixture_server.py'], cwd=SOURCE).decode().split('\0')
    skipped = {'node_modules', '.venv', '__pycache__', '.pytest_cache', 'image_cache',
               'diagnostics', 'cache', 'training_runs'}
    manifest = []
    for relative in sorted(set(inventory) - {''}):
        path = Path(relative)
        if skipped.intersection(path.parts) or re.search(r'\.(db|sqlite|sqlite3)(-|$)', relative):
            continue
        original = SOURCE / path
        assert not path.is_absolute() and '..' not in path.parts
        assert original.resolve() == original and original.is_file()
        target = runtime / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        manifest.append({'file': relative, 'sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
    shutil.copyfile(runtime / 'frontend/tests/suspend_fixture_server.py',
                    runtime / 'backend/tests/suspend_fixture_server.py')
    token = secrets.token_hex(24)
    (runtime / '.suspend-browser-owned').write_text(token)
    (runtime / 'source-manifest.json').write_text(json.dumps(manifest, indent=2))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = Server(runtime, token, port)
    try:
        server.start()
        yield server
    finally:
        server.stop()
        (runtime / 'requests.json').write_text(json.dumps(server.requests, indent=2))
        (runtime / 'processes.json').write_text(json.dumps({'pids': server.pids, 'port': port,
                                                          'stopped': server.process.poll() is not None}))
        archive = archive_root / runtime.name
        archive.mkdir(mode=0o700)
        bundle = archive / 'private-runtime.tar.gz'
        with tarfile.open(bundle, 'w:gz') as tar:
            for path in sorted(runtime.rglob('*')):
                if path.is_file() and path.name != '.suspend-browser-owned':
                    tar.add(path, arcname=str(path.relative_to(runtime)))
        with tarfile.open(bundle) as tar:
            for member in tar:
                if member.isfile():
                    assert tar.extractfile(member).read() == (runtime / member.name).read_bytes()
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        (archive / 'SHA256SUMS').write_text(f'{digest}  {bundle.name}\n')
        print(f'VERIFIED HTTP archive={archive} SHA256={digest}', flush=True)
        # Successful or failed evidence is preserved before local SQLite removal.
        assert server.process.poll() is not None
        shutil.rmtree(runtime)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('scenario', ['burn', 'creature', 'draw', 'decline', 'unpayable'])
def test_composed_ai_real_http_lifecycle(http_server, seat, scenario):
    server = http_server
    fixture = server.request(f'/fixture/suspend-composition?seat={seat}&scenario={scenario}', {}, method='POST')
    match, cid = fixture['id'], fixture['source_id']
    query = f'?source_id={cid}'
    base = f'/fixture/suspend-composition/{match}'
    public = f'/matches/{match}'

    def audit(): return server.request(base + '/audit' + query)
    def restore():
        before = audit()
        after = server.request(base + '/restore' + query, {}, method='POST')
        assert before['snapshot_sha256'] == after['snapshot_sha256']
        assert after['ai_config'][str(seat)] == {'difficulty': 'strong', 'archetype': 'Midrange',
                                               'opponent_archetype': 'Aggro'}

    def tick():
        before = audit()
        pid = before['snapshot']['priority_player']
        if pid == seat:
            return server.request(public + '/autoplay?ticks=1', {}, method='POST')
        return server.request(public + '/action', {'player_id': pid, 'action': {'type': 'pass_priority'}})

    before = audit()
    # AI actions are deliberately not public in current main. Do not weaken that API.
    server.request(public + f'/legal-moves?player_id={seat}', expected=403)
    server.request(public + '/action', {'player_id': seat, 'action': {'type': 'suspend', 'card_id': cid}}, expected=403)
    assert audit()['snapshot_sha256'] == before['snapshot_sha256']
    probe = server.request(base + '/private-probe' + query)
    assert probe['offered_suspend'] == (scenario != 'unpayable')
    assert probe['root_immutable'] and probe['hidden_order_invariant'] and probe['opaque_cards'] > 0
    assert probe['action']['type'] == ('pass_priority' if scenario == 'unpayable' else 'suspend')
    restore()
    server.request(public + '/autoplay?ticks=1', {}, method='POST')
    suspended = audit()
    if scenario == 'unpayable':
        assert suspended['source']['zone'] == 'hand'
        assert not suspended['source']['counters'].get('time')
        return
    assert suspended['source']['zone'] == 'exile' and suspended['source']['counters']['time'] == fixture['count']
    assert not suspended['snapshot']['stack'] and suspended['snapshot']['spells_cast_this_turn'][str(seat)] == 0
    restore()
    for count in range(fixture['count'], 0, -1):
        entered = server.request(base + '/upkeep' + query, {}, method='POST')
        assert entered['snapshot']['stack'][-1]['effect_key'] == 'suspend_upkeep'
        tick(); tick()
        removed = audit()
        assert removed['source']['counters'].get('time', 0) == count - 1
        if count == 1: assert removed['snapshot']['stack'][-1]['effect_key'] == 'suspend_cast_trigger'
        else: assert not removed['snapshot']['stack']
    tick(); tick()
    pending = audit()
    assert pending['snapshot']['pending_mechanic_choice']['kind'] == 'suspend_cast'
    restore()
    if scenario == 'burn':
        before_restart = audit()
        old_pid = server.process.pid
        server.stop(); server.start()
        after_restart = audit()
        assert server.process.pid != old_pid
        assert after_restart['snapshot_sha256'] == before_restart['snapshot_sha256']
        assert after_restart['ai_config'] == before_restart['ai_config']
    probe = server.request(base + '/private-probe' + query)
    expected = 'choose_mechanic' if scenario == 'decline' else 'cast_spell'
    assert probe['action']['type'] == expected
    if scenario == 'burn': assert probe['action']['targets']['target_player'] == 3-seat
    if scenario == 'draw': assert probe['action']['targets']['target_player'] == seat
    hands_before = len(pending['snapshot']['players'][str(seat)]['hand'])
    server.request(public + '/autoplay?ticks=1', {}, method='POST')
    cast = audit()
    assert cast['snapshot']['pending_mechanic_choice'] is None
    if scenario == 'decline':
        assert cast['source']['zone'] == 'exile' and not cast['snapshot']['stack']
        restore()
        return
    assert cast['source']['zone'] == 'stack' and cast['snapshot']['spells_cast_this_turn'][str(seat)] == 1
    restore()
    tick(); tick()
    result = audit()
    if scenario == 'creature':
        assert result['source']['zone'] == 'battlefield' and result['source']['suspend_haste']['controller'] == seat
        view = server.request(public)
        assert 'haste' in next(c for c in view['players'][str(seat)]['battlefield'] if c['id'] == cid)['keywords']
    else:
        assert result['source']['zone'] == 'graveyard'
        if scenario == 'burn': assert result['snapshot']['players'][str(3-seat)]['life'] == 17
        if scenario == 'draw': assert len(result['snapshot']['players'][str(seat)]['hand']) == hands_before + 3
