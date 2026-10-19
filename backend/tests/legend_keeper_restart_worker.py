"""Owned SQLite and actual HTTP across three distinct keeper processes."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


def run(phase, seat, destination, root):
    from sqlmodel import Session, create_engine
    import persistence.db as db
    db.DATABASE_PATH = root / 'owned.sqlite'
    db.DATABASE_URL = 'sqlite:///' + str(db.DATABASE_PATH)
    db.engine = create_engine(db.DATABASE_URL, connect_args={'check_same_thread': False})

    def guard(event, args):
        if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
            address = str(args[0])
            if address.startswith('file:'):
                address = unquote(urlsplit(address).path)
            assert Path(address).resolve().is_relative_to(root.resolve()), address
        if event in ('socket.connect', 'socket.bind'):
            raise AssertionError('No remote network/listeners')
    sys.addaudithook(guard)
    from card_data.sync import ScryfallSyncService
    def no_sync(*args, **kwargs):
        raise AssertionError('No remote sync')
    ScryfallSyncService.sync_card_by_name = no_sync
    from fastapi.testclient import TestClient
    from persistence.repository import Repository
    from rules_engine.engine import RulesEngine
    from ai.information import decision_view, is_unknown
    from tests import test_human_legend_keeper_audit as audit
    from tests.test_self_graveyard_replacement_audit import snap
    import main

    def sql():
        with db.engine.connect() as connection:
            return list(connection.connection.driver_connection.iterdump())

    path = root / 'checkpoint.json'
    evidence = {'phase': phase, 'pid': os.getpid(), 'seat': seat, 'destination': destination,
                'setup': 'Full canonical funded paid casts, not naturally developed mana',
                'transport': 'Real TestClient lifespan + HTTP on persisted SQLite in distinct processes'}
    with TestClient(main.app) as client, Session(db.engine) as session:
        repo = Repository(session)
        if phase == 'seed':
            h = audit.Legend(seat, 'Progenitus', replacement=True, client=client, repo=repo)
            h.first()
            h.pay_cast(h.new)
            audit.require_keeper(h)
            checkpoint = {'id': h.state.id, 'old': h.old, 'new': h.new, 'rip': h.rip}
            controller = h.controller
        else:
            checkpoint = json.loads(path.read_text())
            assert client.get('/matches/' + checkpoint['id']).status_code == 200
            controller = main.ACTIVE_MATCHES[checkpoint['id']]
            assert snap(controller.state) == checkpoint['snapshot']
            assert main._controller_snapshot(controller) == checkpoint['controller']

        def rejected(actor, action):
            before = (snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql())
            response = client.post('/matches/' + checkpoint['id'] + '/action',
                                   json={'player_id': actor, 'action': action})
            assert response.status_code == 422, response.text
            assert (snap(controller.state), main._controller_snapshot(controller), sql()) == before

        if phase == 'keeper':
            assert controller.state.pending_mechanic_choice['kind'] == 'legend_keeper'
            action = {'type': 'choose_mechanic', 'card_ids': [checkpoint['new']]}
            rejected(3-seat, action)
            rejected(seat, {**action, 'card_ids': [checkpoint['new'], checkpoint['new']]})
        elif phase == 'replacement':
            assert controller.state.pending_replacement_choice['resume_kind'] == 'legend_keeper_die'
            action = {'type': 'choose_replacement', 'replacement_source_id': (
                checkpoint['old'] if destination == 'library' else checkpoint['rip'])}
            rejected(3-seat, action)
            rejected(seat, {**action, 'replacement_source_id': 'not-offered'})
        if phase != 'seed':
            body = {'player_id': seat, 'action': action}
            headers = {'Idempotency-Key': 'keeper-' + phase,
                       'X-Match-Revision': str(controller.revision)}
            response = client.post('/matches/' + checkpoint['id'] + '/action', json=body, headers=headers)
            assert response.status_code == 200, response.text
            before = (snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql())
            replay = client.post('/matches/' + checkpoint['id'] + '/action', json=body, headers=headers)
            assert replay.status_code == 200 and replay.json() == response.json(), replay.text
            assert (snap(controller.state), main._controller_snapshot(controller), sql()) == before
        state = controller.state
        if phase == 'keeper':
            assert state.pending_replacement_choice['resume_kind'] == 'legend_keeper_die'
            assert state.cards[checkpoint['old']].zone.value == 'battlefield'
        if phase == 'replacement':
            assert not state.pending_mechanic_choice and not state.pending_replacement_choice
            assert state.cards[checkpoint['old']].zone.value == destination
            assert state.cards[checkpoint['new']].zone.value == 'battlefield'
        moves = RulesEngine().legal_moves(state, seat)
        private, _ = decision_view(state, seat, moves)
        assert all(is_unknown(private.cards[cid]) for cid in state.players[3-seat].hand + state.players[3-seat].library)
        if phase in ('seed', 'keeper'):
            assert RulesEngine().legal_moves(state, 3-seat) == []
        checkpoint['snapshot'] = snap(state)
        checkpoint['controller'] = deepcopy(main._controller_snapshot(controller))
        path.write_text(json.dumps(checkpoint))
        evidence.update(checkpoint)
        evidence['moves'] = moves
        (root / (phase + '.json')).write_text(json.dumps(evidence))
    import sqlite3
    with sqlite3.connect(root / 'owned.sqlite') as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]).resolve())
