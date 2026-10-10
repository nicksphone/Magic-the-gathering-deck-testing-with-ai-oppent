"""Real isolated HTTP and process restarts; no production endpoint additions."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import pytest

from tests.land_consumer_variant_support import VARIANTS
from tests.test_private_choice_http_restart import stable
from tests.cold_restart_http_support import Server
from game_state.serializers import deserialize_match_snapshot


class VariantServer(Server):
    def start(self):
        env = self.environment()
        with (self.root / 'backend-process.log').open('a') as log:
            self.proc = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                'tests.land_consumer_variant_fixture_server:app', '--host', '127.0.0.1',
                '--port', str(self.port)], cwd=self.root / 'backend', env=env,
                stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert self.proc.poll() is None
            try:
                status, row = self.call('/fixture/private-choice/status')
                assert status == 200 and row['pid'] == self.proc.pid and row['root'] == str(self.root)
                self.starts.append(self.proc.pid)
                return
            except (OSError, TimeoutError):
                time.sleep(.1)
        raise AssertionError('Owned variant server readiness timed out')


@pytest.fixture(scope='module')
def server():
    runtime = Path(tempfile.mkdtemp(prefix='mtg-land-consumer-http-')).resolve()
    assert not subprocess.check_output(['stat', '-f', '-c', '%T', str(runtime)], text=True).strip().startswith('nfs')
    shutil.copytree(Path(__file__).resolve().parents[1], runtime / 'backend', ignore=shutil.ignore_patterns(
        '*.db', '*.db-*', '*.sqlite*', '.env', '.env.*', '.venv', '__pycache__',
        '.pytest_cache', 'cache', 'image_cache', 'diagnostics', 'training_runs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    owned = VariantServer(runtime, port)
    try:
        owned.start()
        yield owned
    finally:
        owned.stop()
        (runtime / 'process-receipt.json').write_text(json.dumps({
            'port': port, 'pids': owned.starts, 'stopped': owned.proc.poll() is not None}))
        print(f'OWN_HTTP_RUNTIME={runtime}')


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('variant', VARIANTS)
def test_actual_http_whole_views_explicit_controls_private_root_rejection_restart(server, variant, seat):
    status, data = server.call(f'/fixture/land-consumer?variant={variant}&seat={seat}', {})
    assert status == 200
    identifier = data['id']; base = f'/matches/{identifier}'
    action = data['chosen_action']; endpoint = f'/fixture/private-choice/{identifier}/intent?seat={seat}'
    before = server.audit(identifier)
    status, legal = server.call(base + f'/legal-moves?player_id={seat}')
    assert status == 200
    view = next(m for m in legal['moves'] if m['type'] == 'play_land' and m['card_id'] == data['land']
                and m.get('entry_choice') == action.get('entry_choice'))
    _, actor = server.call(f'/fixture/private-choice/{identifier}/observe?seat={seat}')
    assert data['foreign_hand'] not in json.dumps(actor)
    assert all(cid not in actor['known_cards'] for cid in data['unseen'])
    for packet in (action, {**view, **action}):
        status, result = server.call(endpoint, packet)
        assert status == 200 and result['action'] == action
        assert stable(server.audit(identifier)) == stable(before)
    negatives = [({**view, **action, key: None}) for key in ('land_card_id', 'origin', 'permission', 'targets', 'player_id', 'card_view', 'graveyard_permission_name')]
    negatives.append({**view, **action, 'card_view': {**view['card_view'], 'unknown_choice': None}})
    for packet in negatives:
        status, _ = server.call(endpoint, packet)
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': packet})
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
    status, _ = server.call(endpoint.replace(f'seat={seat}', f'seat={3-seat}'), {**view, **action})
    assert status == 422 and stable(server.audit(identifier)) == stable(before)
    for raw in ({**view, **action}, {**action, 'card_id': data['foreign_hand']}):
        status, _ = server.call(base + '/action', {'player_id': seat, 'action': raw})
        assert status == 422 and stable(server.audit(identifier)) == stable(before)
    before = server.restart(identifier, before)
    assert stable(server.audit(identifier)) == stable(before)
    status, result = server.call(endpoint, {**view, **action})
    assert status == 200 and result['action'] == action
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': result['action']},
        {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 200
    after = server.audit(identifier)
    state = deserialize_match_snapshot(after['state'])
    assert state.cards[data['land']].zone.value == 'battlefield'
    assert data['first'] in getattr(state.players[seat], 'hand' if variant.startswith('shock') else 'graveyard')
    assert state.players[seat].life == (18 if variant == 'shock_pay' else 20)
    assert state.cards[data['land']].tapped == (variant == 'shock_tapped')
    assert state.players[seat].lands_played_this_turn == 1
    assert state.players[seat].library == before['state']['players'][str(seat)]['library']
    assert after['revision'] == before['revision'] + 1
    status, _ = server.call(endpoint, {**view, **action})
    assert status == 422 and stable(server.audit(identifier)) == stable(after)
    status, _ = server.call(base + '/action', {'player_id': seat, 'action': action},
        {'X-Match-Revision': str(before['revision']), 'Idempotency-Key': str(uuid4())})
    assert status == 409 and stable(server.audit(identifier)) == stable(after)
    after = server.restart(identifier, after)
    assert stable(server.audit(identifier)) == stable(after)
