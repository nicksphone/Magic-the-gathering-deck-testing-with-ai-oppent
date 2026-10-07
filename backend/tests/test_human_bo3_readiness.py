"""Controlled intergame HTTP contracts; native-game certificate is separate."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

import main
from game_state.serializers import serialize_match_snapshot
from persistence.db import DATABASE_PATH
from tests.test_api_input_contracts import game, persist, snapshot


def finished(controller, winner=1):
    # Explicit controlled intergame fixture, NOT an actual game-over certificate.
    controller.state.winner = winner
    controller.state.score = {1: int(winner == 1), 2: int(winner == 2)}
    controller.current_game_recorded = True
    controller.sideboards = {1: [{'card_name': 'Forest', 'quantity': 4}],
                            2: [{'card_name': 'Swamp', 'quantity': 4}]}
    persist(controller)


def inventory(controller):
    return {seat: Counter({}) + sum((Counter({row['card_name']: row['quantity']})
            for row in controller.mainboards[seat] + controller.sideboards[seat]), Counter())
            for seat in (1, 2)}


def evidence(label, controller, **extra):
    path = Path(os.environ['MTG_HUMAN_BO3_EVIDENCE']) / (label + '.json')
    path.write_text(json.dumps({'state': serialize_match_snapshot(controller.state),
        'controller': main._controller_snapshot(controller), 'scope': 'controlled intergame fixture',
        **extra}, indent=2, default=str))


@pytest.mark.parametrize('winner', [1, 2])
@pytest.mark.parametrize('confirmed', [[], [1], [2]])
def test_unfinished_human_seats_cannot_be_bypassed(game, winner, confirmed):
    client, controller = game
    finished(controller, winner)
    url = '/matches/' + controller.state.id
    for seat in confirmed:
        response = client.post(url + '/sideboard', json={'player_id': seat, 'cards_out': [], 'cards_in': []})
        assert response.status_code == 200, response.text
    before, cards = snapshot(controller), inventory(controller)
    response = client.post(url + '/next-game', json={'player_id': 3-winner, 'play_first': True})
    evidence(f'baseline-w{winner}-ready{confirmed}', controller, status=response.status_code,
             response=response.json(), before=before, database=str(DATABASE_PATH))
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'sideboarding_not_ready'
    assert response.json()['detail']['players'] == [seat for seat in (1, 2) if seat not in confirmed]
    assert snapshot(controller) == before
    assert inventory(controller) == cards


@pytest.mark.parametrize('winner', [1, 2])
@pytest.mark.parametrize('swap', [False, True])
def test_both_humans_confirm_then_choose_play_draw(game, winner, swap):
    client, controller = game
    finished(controller, winner)
    url = '/matches/' + controller.state.id
    cards = inventory(controller)
    for seat in (1, 2):
        payload = {'player_id': seat, 'cards_out': [], 'cards_in': []}
        if swap:
            payload.update(cards_out=[{'card_name': 'Island', 'quantity': 4}],
                           cards_in=[{'card_name': 'Forest' if seat == 1 else 'Swamp', 'quantity': 4}])
        response = client.post(url + '/sideboard', json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['sideboarding'][str(seat)]['applied']
        before = snapshot(controller)
        assert client.post(url + '/sideboard', json=payload).status_code == 400
        assert snapshot(controller) == before
    assert inventory(controller) == cards
    before = snapshot(controller)
    assert client.post(url + '/next-game', json={'player_id': winner, 'play_first': False}).status_code == 422
    assert snapshot(controller) == before
    result = client.post(url + '/next-game', json={'player_id': 3-winner, 'play_first': False})
    assert result.status_code == 200, result.text
    assert controller.game_number == 2 and controller.state.active_player == winner
    assert controller.sideboarded_players == set()
    assert controller.state.score == {1: int(winner == 1), 2: int(winner == 2)}
    assert controller.root_seed == 4 and inventory(controller) == cards
    assert sum(controller.mainboards[1][i]['quantity'] for i in range(len(controller.mainboards[1]))) == 60
    assert sum(item['quantity'] for item in controller.mainboards[2]) == 60


@pytest.mark.parametrize('seat', [1, 2])
def test_empty_human_sideboard_requires_explicit_no_swaps(game, seat):
    client, controller = game
    finished(controller, 3-seat)
    controller.controllers = {seat: 'human', 3-seat: 'ai'}
    controller.sideboards = {1: [], 2: []}
    persist(controller)
    url = '/matches/' + controller.state.id
    before = snapshot(controller)
    response = client.post(url + '/next-game', json={'player_id': seat, 'play_first': True})
    assert response.status_code == 409
    assert snapshot(controller) == before
    assert client.post(url + '/sideboard', json={'player_id': 3-seat, 'cards_out': [], 'cards_in': []}).status_code == 403
    assert snapshot(controller) == before
    assert client.post(url + '/sideboard', json={'player_id': seat, 'cards_out': [], 'cards_in': []}).status_code == 200
    response = client.post(url + '/next-game', json={'player_id': seat, 'play_first': True})
    assert response.status_code == 200 and response.json()['active_player'] == seat


def test_ai_only_transition_does_not_require_human_confirmation(game):
    client, controller = game
    finished(controller)
    controller.controllers = {1: 'ai', 2: 'ai'}
    controller.sideboards = {1: [], 2: []}
    persist(controller)
    response = client.post('/matches/' + controller.state.id + '/next-game')
    assert response.status_code == 200, response.text
    assert response.json()['game_number'] == 2 and response.json()['active_player'] == 2


def test_revision_duplicate_and_conflicting_retry_preserve_complete_roots(game):
    client, controller = game
    finished(controller)
    url = '/matches/' + controller.state.id
    old = controller.revision
    for seat in (1, 2):
        assert client.post(url + '/sideboard', json={'player_id': seat, 'cards_out': [], 'cards_in': []}).status_code == 200
    before = snapshot(controller)
    payload = {'player_id': 2, 'play_first': True}
    stale = {'Idempotency-Key': 'stale', 'X-Match-Revision': str(old)}
    assert client.post(url + '/next-game', json=payload, headers=stale).status_code == 409
    assert snapshot(controller) == before
    headers = {'Idempotency-Key': 'next-game-once', 'X-Match-Revision': str(controller.revision)}
    accepted = client.post(url + '/next-game', json=payload, headers=headers)
    assert accepted.status_code == 200, accepted.text
    before = snapshot(controller)
    retry = client.post(url + '/next-game', json=payload, headers=headers)
    assert retry.status_code == 200 and retry.json() == accepted.json()
    assert snapshot(controller) == before
    conflict = client.post(url + '/next-game', json={**payload, 'play_first': False}, headers=headers)
    assert conflict.status_code == 409 and snapshot(controller) == before


def test_partial_confirmation_survives_real_cold_read_and_parent_reload(game):
    import subprocess
    import sys
    client, controller = game
    finished(controller)
    url = '/matches/' + controller.state.id
    assert client.post(url + '/sideboard', json={'player_id': 1, 'cards_out': [], 'cards_in': []}).status_code == 200
    before = snapshot(controller)
    root = Path(__file__).resolve().parents[2]
    child = subprocess.run([sys.executable, str(root / 'gate.py'), '--cold', controller.state.id],
        cwd=root / 'backend', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, timeout=60, check=True)
    read = json.loads(child.stdout)
    assert read['view']['sideboarding']['1']['applied']
    assert not read['view']['sideboarding']['2']['applied']
    assert read['snapshot'] == json.loads(json.dumps(serialize_match_snapshot(controller.state)))
    assert snapshot(controller) == before
    main.ACTIVE_MATCHES.pop(controller.state.id)
    restored = client.get(url)
    assert restored.status_code == 200
    assert restored.json()['sideboarding'] == read['view']['sideboarding']
    current = main.ACTIVE_MATCHES[controller.state.id]
    before = snapshot(current)
    assert client.post(url + '/next-game', json={'player_id': 2, 'play_first': True}).status_code == 409
    assert snapshot(current) == before
    assert client.post(url + '/sideboard', json={'player_id': 2, 'cards_out': [], 'cards_in': []}).status_code == 200
    assert client.post(url + '/next-game', json={'player_id': 2, 'play_first': True}).status_code == 200
