"""Actual API startup/restore, local synthetic SQLite only; no scheduler fake."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pickle
import sys
from urllib.parse import unquote, urlsplit


def run(phase, seat, name, root):
    import persistence.db as db
    from sqlmodel import create_engine, Session
    db.DATABASE_PATH = root / 'owned.sqlite'
    db.DATABASE_URL = 'sqlite:///' + str(db.DATABASE_PATH)
    db.engine = create_engine(db.DATABASE_URL, connect_args={'check_same_thread': False})

    def audit(event, args):
        if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
            address = str(args[0])
            if address.startswith('file:'):
                address = unquote(urlsplit(address).path)
            assert Path(address).resolve().is_relative_to(root.resolve()), address
        if event in {'socket.connect', 'socket.bind'}:
            raise AssertionError('No network/listeners')
    sys.addaudithook(audit)
    from card_data.sync import ScryfallSyncService

    def forbidden(*a, **k):
        raise AssertionError('No remote sync')
    ScryfallSyncService.sync_card_by_name = forbidden
    from fastapi.testclient import TestClient
    from game_state.serializers import serialize_match_snapshot
    from game_state.state import Zone
    from persistence.repository import Repository
    from tests.extra_sequence_support import action, add, facts, position, seed_cache
    import main

    def wire(value):
        return json.loads(json.dumps(value))

    def sql_facts():
        with db.engine.connect() as connection:
            return list(connection.connection.driver_connection.iterdump())

    evidence = {'phase': phase, 'seat': seat, 'name': name, 'pid': os.getpid(),
                'http_transport': 'actual FastAPI TestClient; no listener',
                'extra_sequence_execution_certified': False}
    with TestClient(main.app) as client:
        if phase == 'seed':
            with Session(db.engine) as session:
                seed_cache(Repository(session))
            deck = [{'card_name': 'Island', 'quantity': 8}]
            response = client.post('/matches/start', json={
                'deck_a': deck, 'deck_b': deck, 'sandbox': True,
                'controller_a': 'human', 'controller_b': 'human', 'seed': 7214},
                headers={'Idempotency-Key': 'sequence-start'})
            assert response.status_code == 200, response.text
            controller = main.ACTIVE_MATCHES[response.json()['id']]
            state = position(seat)
            state.id = controller.state.id
            source = add(state, name, seat, Zone.HAND if name == 'Time Warp' else Zone.BATTLEFIELD)
            creature = add(state, 'Grizzly Bears', seat)
            creature.tapped = True
            controller.state = state
            with Session(db.engine) as session:
                main._persist_active_match(Repository(session), controller)
            before = facts(state), deepcopy(main._controller_snapshot(controller)), sql_facts()
            body = {'player_id': seat, 'action': action(source)}
            headers = {'Idempotency-Key': 'sequence-action', 'X-Match-Revision': str(controller.revision)}
            response = client.post('/matches/' + state.id + '/action', json=body,
                headers=headers)
            assert response.status_code == 422, response.text
            if name == 'Time Warp':
                assert response.json()['detail']['message'] == 'Unsupported spell resolution: extra-turn scheduling'
            assert (facts(controller.state), main._controller_snapshot(controller), sql_facts()) == before
            evidence.update(status=422, rejected_root_sql_config_rng_equal=True,
                            admission_blocks_payment_untap_and_phases=True)
            saved = {'mid': state.id, 'source': source.id, 'creature': creature.id,
                     'snapshot': wire(serialize_match_snapshot(controller.state)),
                     'config': wire(main._controller_snapshot(controller)),
                     'rng': wire(controller.state.rng.getstate())}
            (root / 'expected.json').write_text(json.dumps(saved, sort_keys=True))
        else:
            saved = json.loads((root / 'expected.json').read_text())
            controller = main.ACTIVE_MATCHES[saved['mid']]
            assert wire(serialize_match_snapshot(controller.state)) == saved['snapshot']
            assert wire(main._controller_snapshot(controller)) == saved['config']
            assert wire(controller.state.rng.getstate()) == saved['rng']
            before = pickle.dumps(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts()
            diagnostic = client.get('/matches/' + saved['mid'] + '/rules-diagnostics')
            assert diagnostic.status_code == 200, diagnostic.text
            assert (pickle.dumps(controller.state), main._controller_snapshot(controller), sql_facts()) == before
            evidence['rules_diagnostics'] = diagnostic.json()
            evidence['restored_snapshot_config_rng_receipts_exact'] = True
            if name == 'Time Warp':
                response = client.post('/matches/' + saved['mid'] + '/action', json={
                    'player_id': seat, 'action': action(controller.state.cards[saved['source']])})
                assert response.status_code == 422, response.text
                assert response.json()['detail']['message'] == 'Unsupported spell resolution: extra-turn scheduling'
                assert not controller.state.stack
                assert controller.state.cards[saved['source']].zone == Zone.HAND
                assert controller.state.turn == 5 and controller.state.active_player == seat
                evidence['restored_unsupported_rejected_through_actual_http'] = True
            assert controller.state.cards[saved['creature']].tapped
            assert controller.state.cards[saved['creature']].summoning_sick
    db.engine.dispose()
    (root / (phase + '-evidence.json')).write_text(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
