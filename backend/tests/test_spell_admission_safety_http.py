"""Production HTTP admission with exact root/RNG/SQL and private restore checks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys

import pytest
from game_state.state import Zone
from game_state.serializers import serialize_match_snapshot
from rules_engine.action_validation import checked_action, ActionRejected
from rules_engine.engine import RulesEngine
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.spell_admission_safety_support import (
    UNSUPPORTED, add, position, seed_cache, facts, resume,
)

TRACE = []


def sql_facts(repo):
    return list(repo.session.connection().connection.driver_connection.iterdump())


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', UNSUPPORTED)
def test_actual_http_full_unsupported_rejection_is_explicit_and_atomic(repo, client, seat, name):
    import main
    seed_cache(repo)
    deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': name, 'quantity': 1}]
    start = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
        'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7214})
    assert start.status_code == 200, start.text
    controller = main.ACTIVE_MATCHES[start.json()['id']]
    state = position(seat)
    state.id = controller.state.id
    state.players[seat].mana_pool = {'W': 20, 'U': 20, 'B': 20, 'R': 20, 'G': 20, 'C': 20}
    source = add(state, name, seat)
    controller.state = state
    main._persist_active_match(repo, controller)
    before = facts(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    source_oracle = source.oracle_text
    response = client.post('/matches/' + state.id + '/action', json={
        'player_id': seat, 'action': {'type': 'cast_spell', 'card_id': source.id,
        'targets': {'target_player': 3 - seat}}}, headers={
        'Idempotency-Key': 'unsupported-cast', 'X-Match-Revision': str(controller.revision)})
    assert response.status_code == 422, response.text
    detail = response.json()['detail']
    assert detail['code'] == 'illegal_action'
    assert detail['message'].startswith('Unsupported spell resolution: ')
    assert (facts(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    assert controller.state.cards[source.id].oracle_text == source_oracle
    snapshot = serialize_match_snapshot(controller.state)
    restored = resume(controller.state)
    assert serialize_match_snapshot(restored) == snapshot
    pure = pickle.dumps(restored)
    with pytest.raises(ActionRejected, match='Unsupported spell resolution'):
        checked_action(restored, RulesEngine(), seat, {'type': 'cast_spell', 'card_id': source.id,
                                                     'targets': {'target_player': 3 - seat}})
    assert pickle.dumps(restored) == pure
    TRACE.append({'name': name, 'seat': seat, 'status': 422, 'detail': detail,
                  'root_card_player_stack_rng_config_sql_exact': True,
                  'snapshot_exact': True, 'paid': False})


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Time Warp', "Day's Undoing", 'Worst Fears'])
def test_actual_startup_fresh_process_restart_remains_failclosed(seat, name, tmp_path):
    root = tmp_path / 'restart'
    root.mkdir()
    worker = Path(__file__).with_name('spell_admission_safety_restart_worker.py')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
           'PYTHONDONTWRITEBYTECODE': '1'}
    for phase in ('seed', 'restore'):
        proc = subprocess.run([sys.executable, str(worker), phase, str(seat), name, str(root)],
                              env=env, capture_output=True, text=True, timeout=60)
        (root / (phase + '.log')).write_text(proc.stdout + proc.stderr)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    first = json.loads((root / 'seed-evidence.json').read_text())
    second = json.loads((root / 'restore-evidence.json').read_text())
    assert first['pid'] != second['pid']
    assert second['restored_snapshot_config_rng_receipts_exact']
    assert second['rejected_root_sql_config_rng_equal']
    TRACE.extend([first, second])


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('face', [-1, 99])
def test_invalid_real_face_choices_remain_structured_and_root_pure(repo, client, seat, face):
    import main
    seed_cache(repo)
    deck = [{'card_name': 'Island', 'quantity': 8}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
        'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7214})
    assert response.status_code == 200, response.text
    controller = main.ACTIVE_MATCHES[response.json()['id']]
    state = position(seat)
    state.id = controller.state.id
    source = add(state, 'Commit // Memory', seat)
    target = add(state, 'Grizzly Bears', 3 - seat, Zone.BATTLEFIELD)
    controller.state = state
    main._persist_active_match(repo, controller)
    before = facts(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    response = client.post('/matches/' + state.id + '/action', json={'player_id': seat,
        'action': {'type': 'cast_spell', 'card_id': source.id, 'selected_face_index': face,
                   'targets': {'target_card_id': target.id}}})
    assert response.status_code == 422, response.text
    assert (facts(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before


def test_write_http_evidence():
    if destination := os.environ.get('SPELL_ADMISSION_HTTP_TRACE'):
        Path(destination).write_text(json.dumps(TRACE, indent=2, sort_keys=True) + '\n')
