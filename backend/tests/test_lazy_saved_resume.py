"""Cold saved IDs resume canonical private choices and BO3 without eager startup."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

import main
from game_state.serializers import serialize_match_snapshot
from persistence.repository import Repository
from tests.test_lazy_saved_matches import store, template
from tests.test_library_reorder import setup, cast_and_resolve


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_actual_cold_private_choice_replay_and_continuation(store, seat, name):
    db, rows = store
    state, source = setup(name, seat)
    state = cast_and_resolve(state, source, seat)
    mid = rows[0][0]['id']
    state.id = mid
    raw = serialize_match_snapshot(state)
    config = rows[0][1]
    with Session(db) as session:
        Repository(session).save_active_match(mid, json.dumps(raw), json.dumps(config))
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        replay = client.get(f'/matches/{mid}/replay')
        assert replay.status_code == 200, replay.text
        assert set(main.ACTIVE_MATCHES) == {mid}
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == raw
        moves = client.get(f'/matches/{mid}/legal-moves?player_id={seat}')
        assert moves.status_code == 200
        assert client.get(f'/matches/{mid}/legal-moves?player_id={3-seat}').json()['moves'] == []
        order = list(reversed(state.pending_mechanic_choice['options']))
        main.ACTIVE_MATCHES.clear()
        accepted = client.post(f'/matches/{mid}/action', json={
            'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': order}})
        assert accepted.status_code == 200, accepted.text
        if name == 'Ponder':
            assert main.ACTIVE_MATCHES[mid].state.pending_mechanic_choice['kind'] == 'library_shuffle'
            saved = serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state)
            main.ACTIVE_MATCHES.clear()
            assert client.get(f'/matches/{mid}').status_code == 200
            assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved
            accepted = client.post(f'/matches/{mid}/action', json={
                'player_id': seat, 'action': {'type': 'choose_mechanic', 'card_ids': ['keep']}})
            assert accepted.status_code == 200, accepted.text
            assert main.ACTIVE_MATCHES[mid].state.players[seat].hand == [order[0]]
        assert main.ACTIVE_MATCHES[mid].state.pending_mechanic_choice is None
        assert main.ACTIVE_MATCHES[mid].state.cards[source.id].zone.value == 'graveyard'


def test_actual_cold_bo3_play_draw_choice_and_saved_next_game(store):
    db, rows = store
    raw, config = deepcopy(rows[0])
    mid = raw['id']
    raw.update(winner=1, score={'1': 1, '2': 0}, best_of=3)
    config['current_game_recorded'] = True
    with Session(db) as session:
        Repository(session).save_active_match(mid, json.dumps(raw), json.dumps(config))
    with TestClient(main.app) as client:
        main.ACTIVE_MATCHES.clear()
        wrong = client.post(f'/matches/{mid}/next-game', json={'player_id': 1, 'play_first': True})
        assert wrong.status_code == 422
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == raw
        main.ACTIVE_MATCHES.clear()
        selected = client.post(f'/matches/{mid}/next-game', json={'player_id': 2, 'play_first': False})
        assert selected.status_code == 200, selected.text
        assert selected.json()['game_number'] == 2
        assert selected.json()['score'] == {'1': 1, '2': 0}
        saved = serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state)
        saved_config = main._controller_snapshot(main.ACTIVE_MATCHES[mid])
        main.ACTIVE_MATCHES.clear()
        assert client.get(f'/matches/{mid}').status_code == 200
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state) == saved
        assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == saved_config
