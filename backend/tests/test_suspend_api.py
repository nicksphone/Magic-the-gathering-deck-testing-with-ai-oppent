"""Suspend through the actual HTTP contract, on a fresh isolated local DB only."""
import os
from pathlib import Path

import pytest
from sqlmodel import Session

import main
from game_state.state import Step, Zone
from persistence.db import DATABASE_PATH, engine
from persistence.repository import Repository
from rules_engine.events import emit_event
from tests.test_api_input_contracts import game, persist, rejected
from tests.test_suspend_lifecycle import setup


@pytest.fixture(autouse=True)
def isolated_database():
    root = Path(__file__).resolve().parents[2]
    declared = os.environ.get('MTG_ISOLATED_TEST_ROOT', '')
    assert declared and Path(declared).resolve() == root, 'Declare the isolated source checkout explicitly'
    assert root != Path('/home/nick/mtg-deck-testing-lab').resolve(), 'Never run against main SQLite'
    assert not str(root).startswith('/mnt/'), 'SQLite must stay local'
    assert DATABASE_PATH == root / 'backend/mtg_lab.db'


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('finish', ['cast', 'decline'])
def test_http_suspend_priority_upkeep_reload_and_cast_or_decline(game, seat, finish):
    client, controller = game
    state, cid = setup(seat)
    state.id = controller.state.id
    controller.state = state
    persist(controller)
    path = f'/matches/{state.id}'

    def post(player, action):
        response = client.post(path+'/action', json={'player_id': player, 'action': action})
        assert response.status_code == 200, response.text
        return main.ACTIVE_MATCHES[state.id]

    rejected(client, controller, {'type': 'suspend', 'card_id': cid, 'targets': {'target_player': 3-seat}}, seat)
    controller = post(seat, {'type': 'suspend', 'card_id': cid})
    assert controller.state.cards[cid].zone == Zone.EXILE
    assert controller.state.cards[cid].counters['time'] == 1 and controller.state.priority_player == seat
    controller.state.step = Step.UPKEEP
    emit_event(controller.state, 'begin_step', {'step': 'upkeep', 'active_player': seat})
    persist(controller)
    for _ in range(4):
        controller = post(controller.state.priority_player, {'type': 'pass_priority'})
    assert controller.state.pending_mechanic_choice['kind'] == 'suspend_cast'
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    assert client.get(path).status_code == 200
    controller = main.ACTIVE_MATCHES[state.id]
    assert controller.state.pending_mechanic_choice['kind'] == 'suspend_cast'
    rejected(client, controller, {'type': 'choose_mechanic', 'card_ids': ['decline']}, 3-seat)
    if finish == 'decline':
        controller = post(seat, {'type': 'choose_mechanic', 'card_ids': ['decline']})
        assert controller.state.cards[cid].zone == Zone.EXILE and not controller.state.stack
    else:
        rejected(client, controller, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True}, seat)
        controller = post(seat, {'type': 'cast_spell', 'card_id': cid, 'from_exile': True,
                                 'targets': {'target_player': 3-seat}})
        assert controller.state.cards[cid].zone == Zone.STACK
        before = controller.state.players[3-seat].life
        for _ in range(2):
            controller = post(controller.state.priority_player, {'type': 'pass_priority'})
        assert controller.state.players[3-seat].life == before-3
        assert controller.state.cards[cid].zone == Zone.GRAVEYARD
    assert not controller.state.pending_mechanic_choice
