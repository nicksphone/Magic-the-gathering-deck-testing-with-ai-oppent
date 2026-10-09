"""Seeded HTTP testpilot certificate; no injected wins or gameplay state edits."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from ai.agent import AIAgent
from ai.action_contract import complete_action
from game_state.serializers import serialize_match_snapshot
import main
from sqlmodel import Session
from persistence.db import engine
from persistence.repository import Repository
from card_data.sync import ScryfallSyncService
from tests.test_api_input_contracts import snapshot
from tests.ci_input_contracts import human_bo3_decks


def test_seeded_human_bo3_checked_http_cold_restart():
    root = Path(__file__).resolve().parents[2]
    out = Path(os.environ['MTG_HUMAN_BO3_EVIDENCE']) / 'interactive'
    out.mkdir(parents=True, exist_ok=True)
    decks = human_bo3_decks()
    pilots = {pid: AIAgent(difficulty='strong', archetype='Aggro') for pid in (1, 2)}
    payload = {'deck_a': decks[0], 'deck_b': decks[1], 'controller_a': 'human',
               'controller_b': 'human', 'mode': 'human_vs_human', 'best_of': 3, 'seed': 1972639901}
    # Legal optional sideboards; actual swaps are certified by the contract module.
    payload.update(deck_a_sideboard=[], deck_b_sideboard=[])
    begin = time.monotonic()
    games = set()
    cold_games = set()
    actions = 0
    with TestClient(main.app) as client, (out / 'decisions.jsonl').open('x') as log:
        raw = json.loads((root / 'backend/tests/fixtures/human_transform_audit/canonical.json').read_text())['Shock']
        with Session(engine) as session:
            Repository(session).upsert_card(ScryfallSyncService._normalize_payload(raw, None))
        check = client.post('/simulate/batch/preflight', json={'deck_a': decks[0], 'deck_b': decks[1]})
        assert check.status_code == 200, check.text
        (out / 'runtime-preflight.json').write_text(json.dumps(check.json(), indent=2))
        assert check.json()['known_unsupported_cards'] == []
        started = client.post('/matches/start', json=payload)
        assert started.status_code == 200, started.text
        view = started.json()
        mid = view['id']
        url = '/matches/' + mid
        (out / 'configuration.json').write_text(json.dumps(payload, indent=2))
        try:
            while not view['match_complete']:
                assert time.monotonic() - begin < 1190, 'Certificate wall bound'
                assert actions < 6000, 'Certificate action bound'
                controller = main.ACTIVE_MATCHES[mid]
                games.add(view['game_number'])
                if view['winner'] is not None:
                    # Only native checked-action game-over reaches this branch.
                    (out / f'game-{view["game_number"]}-end.json').write_text(json.dumps({
                        'view': view, 'snapshot': serialize_match_snapshot(controller.state),
                        'controller': main._controller_snapshot(controller)}, default=str))
                    for pid in (1, 2):
                        reply = client.post(url + '/sideboard', json={'player_id': pid, 'cards_out': [], 'cards_in': []})
                        assert reply.status_code == 200, reply.text
                    before = snapshot(controller)
                    child = subprocess.run([sys.executable, str(Path(__file__).with_name('human_bo3_cold_worker.py')), mid],
                        cwd=root / 'backend', env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                        capture_output=True, text=True, timeout=60)
                    (out / f'cold-{view["game_number"]}.stderr').write_text(child.stderr)
                    assert child.returncode == 0, child.stderr
                    read = json.loads(child.stdout)
                    assert read['snapshot'] == json.loads(json.dumps(serialize_match_snapshot(controller.state)))
                    assert snapshot(controller) == before
                    assert all(read['view']['sideboarding'][str(pid)]['applied'] for pid in (1, 2))
                    main.ACTIVE_MATCHES.pop(mid)
                    restored = client.get(url)
                    assert restored.status_code == 200, restored.text
                    assert restored.json()['score'] == view['score']
                    cold_games.add(view['game_number'])
                    chooser = restored.json()['next_play_draw_chooser']
                    response = client.post(url + '/next-game', json={'player_id': chooser,
                        'play_first': view['game_number'] % 2 == 0})
                    assert response.status_code == 200, response.text
                    view = response.json()
                    continue
                legal = client.get(url + '/legal-moves')
                assert legal.status_code == 200, legal.text
                data = legal.json()
                pid, moves = data['player_id'], data['moves']
                checkpoint = {'index': actions, 'game': view['game_number'], 'player_id': pid,
                    'snapshot': serialize_match_snapshot(controller.state), 'legal': moves}
                (out / 'before-call.json').write_text(json.dumps(checkpoint, default=str))
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
                (out / 'progress.json').write_text(json.dumps({'actions': actions, 'game': view['game_number'],
                    'turn': view['turn'], 'score': view['score'], 'elapsed': time.monotonic() - begin}))
            controller = main.ACTIVE_MATCHES[mid]
            assert max(view['score'].values()) == 2
            assert games == set(range(1, view['game_number'] + 1))
            assert cold_games == games - {view['game_number']}
            assert all(value == 'human' for value in controller.controllers.values())
            (out / 'terminal.json').write_text(json.dumps({'view': view, 'actions': actions,
                'games': sorted(games), 'cold_games': sorted(cold_games), 'elapsed': time.monotonic() - begin,
                'snapshot': serialize_match_snapshot(controller.state)}, default=str))
        finally:
            main.ACTIVE_MATCHES.pop(mid, None)
