"""Actual lifespan restart with synthetic owned SQL; no listeners/default DB."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sqlite3
import sys

from tests.import_identity_fix_support import alias_text, assert_provenance, entry, facts_inventory, full_name, rows, wire


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def semantic_rows(inventory):
    return {rid: {**row, 'mainboard_json': facts_inventory(json.loads(row['mainboard_json'])),
                  'sideboard_json': facts_inventory(json.loads(row['sideboard_json']))}
            for rid, row in inventory.items()}


def run(phase, mode, root):
    root = root.resolve()
    assert str(root).startswith('/home/nick/') or str(root).startswith('/tmp/')
    import persistence.db as db
    from sqlmodel import Session, create_engine
    db.DATABASE_PATH = root / 'owned.sqlite'
    db.DATABASE_URL = 'sqlite:///' + str(db.DATABASE_PATH)
    db.engine = create_engine(db.DATABASE_URL, connect_args={'check_same_thread': False})
    def audit(event, args):
        if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
            assert Path(args[0]).resolve().is_relative_to(root), args[0]
        if event in {'socket.connect', 'socket.bind'}:
            raise AssertionError('No external network/listening sockets')
    sys.addaudithook(audit)
    from card_data import hydration
    from card_data.sync import ScryfallSyncService
    def forbidden(*a, **k):
        raise AssertionError('No remote synchronization')
    ScryfallSyncService.sync_card_by_name = forbidden
    from persistence.repository import Repository
    from fastapi.testclient import TestClient
    from game_state.serializers import serialize_match_snapshot
    from game_state.state import Step
    import main
    if phase == 'restart' and mode == 'missing':
        hydration.fallback_card_payload = lambda _: None
    evidence = {'phase': phase, 'mode': mode, 'pid': os.getpid()}
    with TestClient(main.app) as client:
        def inventory():
            with Session(db.engine) as session:
                return rows(Repository(session))
        if phase == 'seed':
            pair = {'deck_a': [{'card_name': 'Mountain', 'quantity': 8}],
                    'deck_b': [{'card_name': 'Island', 'quantity': 8}], 'sandbox': True,
                    'controller_a': 'human' if mode == 'offline' else 'ai',
                    'controller_b': 'ai' if mode == 'offline' else 'human', 'seed': 917}
            response = client.post('/matches/start', json=pair, headers={'Idempotency-Key': 'identity-root'})
            assert response.status_code == 200, response.text
            mid = response.json()['id']
            body = {'player_id': 1 if mode == 'offline' else 2, 'stops': [Step.DRAW.value]}
            write = {'Idempotency-Key': 'identity-settings', 'X-Match-Revision': '0'}
            assert client.post(f'/matches/{mid}/priority-stops', json=body, headers=write).status_code == 200
            match = main.ACTIVE_MATCHES[mid]
            root_pickle = pickle.dumps(match.state)
            snapshot = wire(serialize_match_snapshot(match.state))
            config = deepcopy(wire(main._controller_snapshot(match)))
            if mode == 'missing':
                hydration.fallback_card_payload = lambda _: None
            observations = []
            for code, front in [('LEA', 'Kumano Faces Kakkazan'), ('ARN', 'Delver of Secrets')]:
                item = entry(code)
                before = inventory()
                response = client.post('/decks/expansion-top/' + code.lower() + '/import')
                assert response.status_code == 200, response.text
                result = response.json(); assert not result['errors']
                rid = str(result['deck_id'])
                assert rid in before and inventory()[rid]['source'] == 'expansion_top:' + code.lower()
                assert any(row['source'] == 'expansion_top:' + code.lower() for row in before.values())
                with Session(db.engine) as session:
                    assert assert_provenance(Repository(session), result) == (mode == 'offline')
                text = alias_text(item['deck_text'], front, full_name(front))
                alias = client.post('/decks/import', json={'name': item['deck_name'], 'source': 'expansion_top:' + code.lower(),
                    'deck_text': text})
                assert alias.status_code == 200 and alias.json()['deck_id'] == result['deck_id']
                with Session(db.engine) as session:
                    assert assert_provenance(Repository(session), alias.json()) == (mode == 'offline')
                before_invalid = inventory()
                with sqlite3.connect(db.DATABASE_PATH) as conn:
                    sql_before = list(conn.iterdump())
                for source in ('expansion_top:' + code.lower(), 'user'):
                    oversized = client.post('/decks/import', json={'name': item['deck_name'], 'source': source,
                        'deck_text': item['deck_text'].split('Sideboard:')[0] + '\nSideboard:\n16 Mountain'})
                    assert oversized.status_code == 422
                    assert oversized.json()['detail'] == {'code': 'sideboard_limit_exceeded', 'maximum': 15, 'actual': 16}
                for source in ('expansion_top:' + code.lower(), 'user'):
                    invalid = client.post('/decks/import', json={'name': item['deck_name'], 'source': source,
                        'deck_text': item['deck_text'] + '\n! invalid syntax'})
                    assert invalid.status_code == 200 and invalid.json()['errors'] and invalid.json()['deck_id'] is None
                    assert inventory() == before_invalid
                with sqlite3.connect(db.DATABASE_PATH) as conn:
                    assert list(conn.iterdump()) == sql_before
                assert pickle.dumps(match.state) == root_pickle
                assert wire(main._controller_snapshot(match)) == config
                observations.append({'code': code, 'first': result, 'alias': alias.json(),
                                     'alias_left_saved_across_restart': True, 'unexpected_second_catalog_id': False})
            assert pickle.dumps(match.state) == root_pickle
            assert wire(main._controller_snapshot(match)) == config
            for route in (f'/matches/{mid}', f'/matches/{mid}/replay', f'/matches/{mid}/legal-moves?player_id={body["player_id"]}'):
                assert client.get(route).status_code == 200
            assert pickle.dumps(match.state) == root_pickle
            public = client.get(f'/matches/{mid}').json()
            ai_seat = '2' if mode == 'offline' else '1'
            assert public['players'][ai_seat]['hand'] == []
            assert all('library' not in p for p in public['players'].values())
            assert client.get(f'/matches/{mid}/debug/ai-hands').status_code == 403
            all_rows = inventory()
            saved = {'mid': mid, 'snapshot': snapshot, 'config': config, 'inventory': all_rows,
                     'pair': pair, 'body': body, 'write': write, 'public': public}
            (root / 'expected.json').write_text(json.dumps(saved, sort_keys=True))
            evidence.update(snapshot_hash=digest(snapshot), inventory_hash=digest(all_rows), imports=observations,
                            semantic_inventory_hash=digest(semantic_rows(all_rows)),
                            all_match_root_fields_unchanged=True, settings_receipt_unchanged=True)
        else:
            saved = json.loads((root / 'expected.json').read_text())
            match = main.ACTIVE_MATCHES[saved['mid']]
            snapshot = wire(serialize_match_snapshot(match.state))
            actual_inventory = inventory()
            (root / 'restart-inventory.json').write_text(json.dumps(actual_inventory, sort_keys=True))
            assert snapshot == saved['snapshot']
            assert wire(main._controller_snapshot(match)) == saved['config']
            assert set(actual_inventory) == set(saved['inventory'])
            changes = []
            for rid, old in saved['inventory'].items():
                new = actual_inventory[rid]
                fields = {key: [old[key], new[key]] for key in old if old[key] != new[key]}
                if fields:
                    assert old['source'].startswith('expansion_top:')
                    assert set(fields) <= {'mainboard_json', 'sideboard_json'}
                    changes.append({'id': rid, 'source': old['source'], 'changes': fields})
            assert semantic_rows(actual_inventory) == semantic_rows(saved['inventory'])
            assert client.get('/matches/' + saved['mid']).json() == saved['public']
            assert client.post('/matches/start', json=saved['pair'],
                headers={'Idempotency-Key': 'identity-root'}).json() == saved['public']
            replay = client.post('/matches/' + saved['mid'] + '/priority-stops',
                                 json=saved['body'], headers=saved['write'])
            assert replay.status_code == 200 and match.revision == 1
            assert wire(serialize_match_snapshot(match.state)) == saved['snapshot']
            evidence.update(snapshot_hash=digest(snapshot), inventory_hash=digest(actual_inventory),
                            semantic_inventory_hash=digest(semantic_rows(actual_inventory)),
                            alias_literal_startup_changes=changes,
                            ids_source_other_columns_and_physical_inventory_preserved=True,
                            all_match_root_fields_unchanged=True, settings_receipt_unchanged=True)
    db.engine.dispose()
    with sqlite3.connect(db.DATABASE_PATH) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    (root / (phase + '-evidence.json')).write_text(json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
