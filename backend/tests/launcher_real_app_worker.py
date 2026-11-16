"""Fresh real combined-app process; no fixture routes or test-module imports."""
import json
import os
from pathlib import Path
import socket
import sys


def main():
    phase, checkpoint_arg = sys.argv[1:]
    if phase not in ('create', 'restore'):
        raise ValueError('Expected create or restore')
    checkpoint = Path(checkpoint_arg)
    backend = Path(__file__).resolve().parent
    assert not (backend/'mtg_lab.db').exists()
    assert Path(os.environ['MTG_DATABASE_PATH']).parent != backend
    # Application startup must work from shipped data. No actual network call.
    attempts = []
    def offline(*args, **kwargs):
        attempts.append(True)
        raise AssertionError('Unexpected network connection')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from local_web import create_app
    import main as app
    from persistence.capacity import owner_for_engine
    from persistence.repository import Repository

    def checked(response, status=200):
        assert response.status_code == status, f'Unexpected HTTP status {response.status_code}'
        return response

    def saved(mid):
        with Session(app.engine) as session:
            row = Repository(session).get_active_match(mid)
            return row.state_json, row.controller_json

    application = create_app()
    with TestClient(application) as client:
        owner = owner_for_engine(app.engine)
        assert checked(client.get('/api/health')).json()['ok'] is True
        assert len(checked(client.get('/api/decks')).json()) >= 2
        assert 'Launcher ASGI fixture' in checked(client.get('/')).text
        assert 'Launcher ASGI fixture' in checked(client.get('/table/saved', headers={'Accept': 'text/html'})).text
        checked(client.get('/api/does-not-exist'), 404)
        checked(client.get('/assets/missing.js', headers={'Accept': 'text/html'}), 404)
        media = checked(client.get('/card-images/generic-token-creature.svg'))
        assert media.headers['content-type'].startswith('image/svg+xml') and '<svg' in media.text
        if phase == 'create':
            payload = {'deck_a': [{'card_name': 'Island', 'quantity': 60}],
                       'deck_b': [{'card_name': 'Island', 'quantity': 60}],
                       'controller_a': 'human', 'controller_b': 'human',
                       'mode': 'human_vs_human', 'seed': 97531}
            state = checked(client.post('/api/matches/start', json=payload,
                headers={'Idempotency-Key': 'launcher-smoke-start'})).json()
            mid, first = state['id'], None
            def act(action, pid):
                nonlocal state, first
                body = {'player_id': pid, 'action': action}
                headers = {'Idempotency-Key': f'launcher-smoke-{state["revision"]}',
                           'X-Match-Revision': str(state['revision'])}
                before = state['revision']
                state = checked(client.post(f'/api/matches/{mid}/action',
                                            json=body, headers=headers)).json()
                assert state['revision'] == before+1
                if first is None:
                    first = {'body': body, 'headers': headers}
            for _ in range(2):
                menu = checked(client.get(f'/api/matches/{mid}/legal-moves')).json()
                assert any(move['type'] == 'keep_hand' for move in menu['moves'])
                act({'type': 'keep_hand', 'bottom_card_ids': []}, menu['player_id'])
            assert not state['pregame_pending']
            for _ in range(12):
                menu = checked(client.get(f'/api/matches/{mid}/legal-moves')).json()
                move = next((move for move in menu['moves'] if move['type'] == 'play_land'), None)
                if move is not None:
                    act({'type': 'play_land', 'card_id': move['card_id']}, menu['player_id'])
                    break
                assert any(move['type'] == 'pass_priority' for move in menu['moves'])
                act({'type': 'pass_priority'}, menu['player_id'])
            else:
                raise AssertionError('Bounded opening never offered a land')
            assert any(card['id'] == move['card_id'] for card in state['players'][str(menu['player_id'])]['battlefield'])
            expected = {'state': state, 'payload': payload, 'first': first}
            fd = os.open(checkpoint, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(expected, stream)
            summary = {'phase': phase, 'revision': state['revision'], 'local_media': True}
        else:
            expected = json.loads(checkpoint.read_text())
            mid = expected['state']['id']
            state = checked(client.get(f'/api/matches/{mid}')).json()
            assert state == expected['state']
            before = saved(mid)
            start = checked(client.post('/api/matches/start', json=expected['payload'],
                headers={'Idempotency-Key': 'launcher-smoke-start'})).json()
            assert start == state
            first = expected['first']
            retry = checked(client.post(f'/api/matches/{mid}/action',
                json=first['body'], headers=first['headers'])).json()
            assert retry == state
            stale = checked(client.post(f'/api/matches/{mid}/action',
                json={'player_id': 1, 'action': {'type': 'pass_priority'}},
                headers={'Idempotency-Key': 'launcher-stale', 'X-Match-Revision': '0'}), 409)
            assert stale.json()['detail']['code'] == 'stale_revision'
            assert saved(mid) == before
            assert len(checked(client.get('/api/matches')).json()) == 1
            summary = {'phase': phase, 'revision': state['revision'], 'exact_restore': True,
                       'original_key_retry': True, 'stale_status': 409, 'local_media': True}
    assert owner.fd is None and app.engine.pool.checkedout() == 0
    assert not attempts and not (backend/'mtg_lab.db').exists()
    summary['owner_released'] = True
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
