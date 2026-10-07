"""Once-only native human BO3 with genuine different-card sideboard swaps."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from sqlmodel import Session
from ai.agent import AIAgent
from ai.action_contract import complete_action
from card_data.sync import ScryfallSyncService
from game_state.serializers import serialize_match_snapshot
import main
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import snapshot


def canonical(value):
    return json.loads(json.dumps(value, default=str))


def quantities(lines):
    result = Counter()
    for line in lines:
        result[line['card_name']] += line['quantity']
    return result


def inventory(controller):
    return {str(pid): quantities(controller.mainboards[pid]) + quantities(controller.sideboards[pid])
            for pid in (1, 2)}


def test_native_swaps_between_checked_human_games():
    root = Path(__file__).resolve().parents[2]
    out = Path(os.environ['MTG_HUMAN_BO3_EVIDENCE'])
    out.mkdir(parents=True, exist_ok=True)
    decks = list(json.loads((root / 'evidence/selected-preflight.json').read_text())['decks'].values())
    families = {1: ('Soul-Scar Mage', 'Goblin Guide'), 2: ('Goblin Guide', 'Soul-Scar Mage')}
    sideboards = {pid: [{'quantity': 4, 'card_name': families[pid][1]}] for pid in (1, 2)}
    swapped = []
    for pid in (1, 2):
        before = quantities(decks[pid - 1])
        assert before[families[pid][0]] == 4 and before[families[pid][1]] == 0
        after = before.copy()
        after[families[pid][0]] -= 1
        after[families[pid][1]] += 1
        swapped.append([{'card_name': name, 'quantity': qty} for name, qty in after.items()])
        assert sum(after.values()) == 60
        assert all(qty <= 4 or name == 'Mountain' for name, qty in
                   (before + quantities(sideboards[pid])).items())
    payload = {'deck_a': decks[0], 'deck_b': decks[1], 'deck_a_sideboard': sideboards[1],
               'deck_b_sideboard': sideboards[2], 'controller_a': 'human', 'controller_b': 'human',
               'mode': 'human_vs_human', 'best_of': 3, 'seed': 1972639901}
    pilots = {pid: AIAgent(difficulty='strong', archetype='Aggro') for pid in (1, 2)}
    begin = time.monotonic()
    games, cold_games = set(), set()
    actions = 0

    def record(name, value):
        (out / name).write_text(json.dumps(canonical(value), indent=2))

    with TestClient(main.app) as client, (out / 'decisions.jsonl').open('x') as log:
        raw = json.loads((root / 'backend/tests/fixtures/human_transform_audit/canonical.json').read_text())['Shock']
        with Session(engine) as session:
            Repository(session).upsert_card(ScryfallSyncService._normalize_payload(raw, None))
        for label, pair in (('initial', decks), ('post-swap', swapped)):
            response = client.post('/simulate/batch/preflight', json={'deck_a': pair[0], 'deck_b': pair[1]})
            record('preflight-' + label + '.json', {'status': response.status_code, 'body': response.json()})
            assert response.status_code == 200, response.text
            assert response.json()['known_unsupported_cards'] == []
        record('configuration.json', payload)
        started = client.post('/matches/start', json=payload)
        assert started.status_code == 200, started.text
        view = started.json()
        mid = view['id']
        url = '/matches/' + mid
        controller = main.ACTIVE_MATCHES[mid]
        fixed_inventory = inventory(controller)
        record('initial-inventory.json', fixed_inventory)

        def reject(label, endpoint, body, status, headers=None):
            current = main.ACTIVE_MATCHES[mid]
            before = snapshot(current)
            response = client.post(url + endpoint, json=body, headers=headers or {})
            after = snapshot(current)
            record(label + '.json', {'before': before, 'after': after,
                                     'status': response.status_code, 'body': response.json()})
            assert response.status_code == status, response.text
            assert before == after, label
            assert inventory(current) == fixed_inventory

        def cold(label):
            current = main.ACTIVE_MATCHES[mid]
            before = snapshot(current)
            expected = canonical(serialize_match_snapshot(current.state))
            expected_controller = canonical(main._controller_snapshot(current))
            child = subprocess.run([sys.executable, str(root / 'gate.py'), '--cold', mid],
                cwd=root / 'backend', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, text=True, timeout=60)
            (out / (label + '.stderr')).write_text(child.stderr)
            assert child.returncode == 0, child.stderr
            read = json.loads(child.stdout)
            assert read['snapshot'] == expected
            assert read['controller'] == expected_controller
            assert snapshot(current) == before
            main.ACTIVE_MATCHES.pop(mid)
            restored = client.get(url)
            assert restored.status_code == 200, restored.text
            current = main.ACTIVE_MATCHES[mid]
            assert canonical(serialize_match_snapshot(current.state)) == expected
            assert canonical(main._controller_snapshot(current)) == expected_controller
            assert snapshot(current) == before
            assert inventory(current) == fixed_inventory
            record(label + '.json', read)
            return restored.json()

        try:
            while not view['match_complete']:
                assert time.monotonic() - begin < 1190, 'Supplement wall bound'
                assert actions < 6000, 'Supplement action bound'
                controller = main.ACTIVE_MATCHES[mid]
                number = view['game_number']
                games.add(number)
                if view['winner'] is not None:
                    record(f'game-{number}-end.json', {'view': view,
                        'snapshot': serialize_match_snapshot(controller.state),
                        'controller': main._controller_snapshot(controller)})
                    chooser = view['next_play_draw_chooser']
                    reject(f'g{number}-wrong-chooser', '/next-game',
                           {'player_id': 3 - chooser, 'play_first': True}, 422)
                    reject(f'g{number}-unfinished', '/next-game',
                           {'player_id': chooser, 'play_first': True}, 409)
                    for pid in (1, 2):
                        body = {'player_id': pid, 'cards_out': [], 'cards_in': []}
                        if number == 1:
                            old, new = families[pid]
                            body.update(cards_out=[{'quantity': 1, 'card_name': old}],
                                        cards_in=[{'quantity': 1, 'card_name': new}])
                            reject(f'g{number}-p{pid}-invalid-actor', '/sideboard', {**body, 'player_id': 3}, 422)
                            # Both seats are human: no authentication claim. Binding the other
                            # seat's DIFFERENT inventory to this swap must still reject atomically.
                            if pid == 1:
                                reject('g1-other-seat-inventory', '/sideboard', {**body, 'player_id': 2}, 400)
                        current = main.ACTIVE_MATCHES[mid]
                        stale = {'Idempotency-Key': f'stale-g{number}-p{pid}',
                                 'X-Match-Revision': str(current.revision + 1)}
                        reject(f'g{number}-p{pid}-stale', '/sideboard', body, 409, stale)
                        headers = {'Idempotency-Key': f'accepted-g{number}-p{pid}',
                                   'X-Match-Revision': str(current.revision)}
                        reply = client.post(url + '/sideboard', json=body, headers=headers)
                        record(f'g{number}-p{pid}-accepted.json', {'request': body,
                             'headers': headers, 'status': reply.status_code, 'view': reply.json()})
                        assert reply.status_code == 200, reply.text
                        current = main.ACTIVE_MATCHES[mid]
                        assert inventory(current) == fixed_inventory
                        assert sum(quantities(current.mainboards[pid]).values()) == 60
                        assert sum(quantities(current.sideboards[pid]).values()) == 4
                        assert reply.json()['sideboarding'][str(pid)]['applied'] is True
                        if number == 1:
                            assert quantities(current.mainboards[pid])[old] == 3
                            assert quantities(current.mainboards[pid])[new] == 1
                            assert quantities(current.sideboards[pid])[old] == 1
                            assert quantities(current.sideboards[pid])[new] == 3
                        reject(f'g{number}-p{pid}-duplicate', '/sideboard', body, 400,
                               {'Idempotency-Key': f'duplicate-g{number}-p{pid}',
                                'X-Match-Revision': str(current.revision)})
                        before = snapshot(current)
                        replay = client.post(url + '/sideboard', json=body, headers=headers)
                        assert replay.status_code == 200, replay.text
                        assert snapshot(current) == before
                    record(f'g{number}-swapped-controller.json', main._controller_snapshot(main.ACTIVE_MATCHES[mid]))
                    restored = cold(f'cold-g{number}')
                    assert restored['score'] == view['score']
                    assert restored['next_play_draw_chooser'] == chooser
                    for pid in (1, 2):
                        current = main.ACTIVE_MATCHES[mid]
                        public = restored['sideboarding'][str(pid)]
                        assert quantities(public['mainboard']) == quantities(current.mainboards[pid])
                        assert quantities(public['sideboard']) == quantities(current.sideboards[pid])
                        assert public['applied'] is True
                    cold_games.add(number)
                    response = client.post(url + '/next-game', json={'player_id': chooser,
                                           'play_first': number % 2 == 0})
                    assert response.status_code == 200, response.text
                    view = response.json()
                    current = main.ACTIVE_MATCHES[mid]
                    assert current.game_number == number + 1
                    assert current.sideboarded_players == set()
                    assert current.root_seed == 1972639901
                    assert view['active_player'] == (chooser if number % 2 == 0 else 3 - chooser)
                    assert view['root_seed'] is None and view['game_seed'] is None
                    assert inventory(current) == fixed_inventory
                    for pid in (1, 2):
                        pool = current.state.players[pid].hand + current.state.players[pid].library
                        actual = Counter(current.state.cards[cid].name for cid in pool)
                        old, new = families[pid]
                        assert len(pool) == 60 and actual[old] == 3 and actual[new] == 1
                    record(f'g{number + 1}-rebuilt.json', {'view': view,
                        'controller': main._controller_snapshot(current),
                        'derived_game_seed': main.game_seed(current.root_seed, current.game_number),
                        'snapshot': serialize_match_snapshot(current.state)})
                    continue
                legal = client.get(url + '/legal-moves')
                assert legal.status_code == 200, legal.text
                data = legal.json()
                pid, moves = data['player_id'], data['moves']
                checkpoint = {'index': actions, 'game': number, 'player_id': pid,
                              'snapshot': serialize_match_snapshot(controller.state), 'legal': moves}
                record('before-call.json', checkpoint)
                if moves:
                    decision = pilots[pid].choose_action(controller.state, moves, pid)
                    action = complete_action(decision.action)
                    checkpoint.update(action=action, reason=decision.reasoning)
                    response = client.post(url + '/action', json={'player_id': pid, 'action': action})
                else:
                    checkpoint.update(action={'endpoint': 'autoplay', 'ticks': 1},
                                      reason='Native no-priority transition through public endpoint')
                    response = client.post(url + '/autoplay', params={'ticks': 1})
                checkpoint.update(status=response.status_code, elapsed=time.monotonic() - begin)
                log.write(json.dumps(checkpoint, default=str) + '\n')
                log.flush()
                assert response.status_code == 200, response.text
                view = response.json()
                actions += 1
                record('progress.json', {'actions': actions, 'game': view['game_number'],
                    'turn': view['turn'], 'score': view['score'], 'elapsed': time.monotonic() - begin})
            current = main.ACTIVE_MATCHES[mid]
            assert max(view['score'].values()) == 2
            assert games == set(range(1, view['game_number'] + 1)) and len(games) >= 2
            assert cold_games == games - {view['game_number']}
            assert all(value == 'human' for value in current.controllers.values())
            assert inventory(current) == fixed_inventory
            assert not any(any(word in line.lower() for word in ('unsupported','not inferred','not implemented'))
                           for line in current.state.log)
            terminal = cold('cold-completed')
            assert terminal['match_complete'] and terminal['score'] == view['score']
            reject('completed-cannot-advance', '/next-game', {'player_id': 1, 'play_first': True}, 400)
            record('terminal.json', {'view': terminal, 'actions': actions, 'games': sorted(games),
                'cold_games': sorted(cold_games), 'elapsed': time.monotonic() - begin,
                'inventory': fixed_inventory, 'snapshot': serialize_match_snapshot(main.ACTIVE_MATCHES[mid].state)})
        finally:
            main.ACTIVE_MATCHES.pop(mid, None)
            engine.dispose()
