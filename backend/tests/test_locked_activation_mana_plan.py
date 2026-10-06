"""Canonical locked-cost payment must not convert unrelated fuel into a pool."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from card_data.token_definitions import named_artifact_token
from effects.handlers import create_token
from game_state.serializers import serialize_match_snapshot, deserialize_match_snapshot
from rules_engine.action_validation import checked_action
from rules_engine.engine import RulesEngine
from tests.test_ability_cost_discounts import source, board, view, resolve
from tests.test_activation_modifiers import add
from tests.test_api_input_contracts import game, persist, rejected, snapshot


def position(seat, family, prefunded=False):
    state = board(seat)
    if family == 'artifact':
        card = source(state, "Tamiyo's Logbook", seat)
        color = 'U'
    elif family == 'counters':
        card = source(state, 'Deepwood Denizen', seat)
        card.counters['+1/+1'] = 5
        color = 'G'
    else:
        card = add(state, 'Azure Mage', seat)
        add(state, 'Training Grounds', seat)
        add(state, 'Heartstone', seat)
        color = 'U'
    create_token(state, seat, {**named_artifact_token('Treasure'), 'amount': 5,
                              'types': ['Artifact', 'Token']})
    if prefunded:
        state.players[seat].mana_pool[color] = 1
    return state, card, color


def move_for(state, seat, card):
    return next(m for m in RulesEngine().legal_moves(state, seat)
                if m['type'] == 'activate_ability' and m['card_id'] == card.id)


def assert_paid(result, seat, prefunded):
    assert sum(result.players[seat].mana_pool.values()) == 0
    assert sum(result.cards[cid].name == 'Treasure'
               for cid in result.players[seat].battlefield) == (5 if prefunded else 4)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['artifact', 'counters', 'external'])
@pytest.mark.parametrize('prefunded', [False, True])
def test_checked_locked_cost_exact_fuel_and_replay(seat, family, prefunded, monkeypatch):
    import rules_engine.mana as mana
    state, card, color = position(seat, family, prefunded)
    before = serialize_match_snapshot(state)
    rng = state.rng.getstate()
    assert view(state, card)['generic'] == 0
    assert view(state, card)[color] == 1
    move = move_for(state, seat, card)
    assert serialize_match_snapshot(state) == before
    original = mana._spell_payment_plan
    records = []

    def record(*args, **kwargs):
        plan = original(*args, **kwargs)
        if kwargs.get('source_card_id') == card.id:
            records.append((deepcopy(args[2]), deepcopy(plan)))
        return plan

    monkeypatch.setattr(mana, '_spell_payment_plan', record)
    result = checked_action(state, RulesEngine(), seat, move)
    assert records and all(req['generic'] == 0 and req[color] == 1 for req, _ in records)
    assert all(len(plan[2][0]) == (0 if prefunded else 1) for _, plan in records)
    assert_paid(result, seat, prefunded)
    if family == 'artifact':
        assert view(result, result.cards[card.id])['generic'] == (0 if prefunded else 1)
    assert serialize_match_snapshot(state) == before
    assert state.rng.getstate() == rng
    replay = checked_action(deserialize_match_snapshot(before), RulesEngine(), seat, move)
    assert serialize_match_snapshot(replay) == serialize_match_snapshot(result)
    assert result.cards[card.id] is not state.cards[card.id]
    assert len(resolve(result).players[seat].hand) == 1
    evidence = os.environ.get('LOCKED_MANA_EVIDENCE')
    if evidence:
        with (Path(evidence) / f'core-{seat}-{family}-{prefunded}.json').open('x') as stream:
            json.dump({'root': before, 'move': move, 'result': serialize_match_snapshot(replay),
                       'locked_requirements': [req for req, _ in records]}, stream, sort_keys=True)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('family', ['artifact', 'counters', 'external'])
def test_http_locked_payment_reject_restore_and_resolution(game, seat, family):
    import main
    from sqlmodel import Session
    from persistence.db import DATABASE_PATH, engine
    from persistence.repository import Repository
    assert DATABASE_PATH.parent == Path(__file__).resolve().parents[1]
    assert str(DATABASE_PATH) != '/home/nick/mtg-deck-testing-lab/backend/mtg_lab.db'
    assert not str(DATABASE_PATH).startswith('/mnt/')
    client, match = game
    state, card, _ = position(seat, family)
    state.id = match.state.id
    match.state = state
    persist(match)
    offered = move_for(state, seat, card)
    move = {key: offered[key] for key in ('type', 'card_id', 'ability_index')}
    move['targets'] = {}
    before = snapshot(match)
    invalid = {**move, 'ability_index': 999}
    rejected(client, match, invalid, seat)
    assert snapshot(match) == before
    expected = checked_action(state, RulesEngine(), seat, move)
    response = client.post(f'/matches/{state.id}/action', json={'player_id': seat, 'action': move})
    assert response.status_code == 200, response.text
    assert_paid(match.state, seat, False)
    assert serialize_match_snapshot(match.state) == serialize_match_snapshot(expected)
    committed = snapshot(match)
    main.ACTIVE_MATCHES.pop(state.id)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session), state.id)
    restored = main.ACTIVE_MATCHES[state.id]
    assert snapshot(restored) == committed
    child = subprocess.run([sys.executable, '-c', '''
import json, sqlite3, sys
path, match_id = sys.argv[1:]
uri = 'file:' + path + '?mode=ro'
def guard(event, args):
    if event in ('socket.connect', 'socket.connect_ex'):
        raise AssertionError(event)
    if event == 'sqlite3.connect' and str(args[0]) != uri:
        raise AssertionError('Unexpected SQLite open')
sys.addaudithook(guard)
import main
from sqlmodel import Session, create_engine
from persistence.repository import Repository
from game_state.serializers import serialize_match_snapshot
engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(uri, uri=True))
with Session(engine) as session:
    main._restore_active_matches(Repository(session), match_id)
match = main.ACTIVE_MATCHES[match_id]
print(json.dumps({'state': serialize_match_snapshot(match.state),
                  'controller': main._controller_snapshot(match)}, sort_keys=True))
''', str(DATABASE_PATH), state.id], check=True, capture_output=True, text=True, timeout=30,
        env={**os.environ, 'PYTHONPATH': str(DATABASE_PATH.parent), 'PYTHONDONTWRITEBYTECODE': '1'})
    recovered = json.loads(child.stdout)
    assert recovered['state'] == json.loads(committed[0])
    assert recovered['controller'] == committed[1]
    assert snapshot(restored) == committed
    for _ in range(2):
        player = restored.state.priority_player
        response = client.post(f'/matches/{state.id}/action',
                               json={'player_id': player, 'action': {'type': 'pass_priority'}})
        assert response.status_code == 200, response.text
    assert len(restored.state.players[seat].hand) == 1
    evidence = os.environ.get('LOCKED_MANA_EVIDENCE')
    if evidence:
        with (Path(evidence) / f'http-{seat}-{family}.json').open('x') as stream:
            json.dump({'root': json.loads(before[0]), 'committed': json.loads(committed[0]),
                       'fresh_process_recovered': recovered,
                       'resolved': serialize_match_snapshot(restored.state)}, stream, sort_keys=True)
