"""Checked HTTP choices and durable repository restore, without live services."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from game_state.serializers import serialize_match_snapshot
from game_state.state import Zone
from tests.test_builtin_metadata_refresh import repo
from tests.generic_import_fixtures import client
from tests.readiness_rules_seam_support import normalize
from tests.spell_admission_safety_support import seed_cache
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_library_reorder import FIXTURES, setup


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_http_order_choices_reject_wrong_seat_and_restore_pending(repo, client, seat, name):
    import main
    seed_cache(repo)
    raw = json.loads((FIXTURES / (name.lower() + '.json')).read_text())
    repo.upsert_card(normalize(raw))
    deck = [{'card_name': 'Island', 'quantity': 7}, {'card_name': name, 'quantity': 1}]
    response = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
                           'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 7221})
    assert response.status_code == 200, response.text
    identifier = response.json()['id']
    controller = main.ACTIVE_MATCHES[identifier]
    state, source = setup(name, seat)
    state.id = identifier
    controller.state = state
    main._persist_active_match(repo, controller)

    def post(actor, action):
        revision = main.ACTIVE_MATCHES[identifier].revision
        value = client.post(f'/matches/{identifier}/action', json={'player_id': actor, 'action': action},
                            headers={'Idempotency-Key': f'reorder-{revision}', 'X-Match-Revision': str(revision)})
        assert value.status_code == 200, value.text

    def reload():
        expected = deepcopy(serialize_match_snapshot(main.ACTIVE_MATCHES[identifier].state))
        main.ACTIVE_MATCHES.clear()
        main._restore_active_matches(repo, identifier)
        assert serialize_match_snapshot(main.ACTIVE_MATCHES[identifier].state) == expected

    post(seat, {'type': 'cast_spell', 'card_id': source.id, 'targets': {}})
    for _ in range(2):
        actor = main.ACTIVE_MATCHES[identifier].state.priority_player
        post(actor, {'type': 'pass_priority'})
    controller = main.ACTIVE_MATCHES[identifier]
    pending = controller.state.pending_mechanic_choice
    assert pending['kind'] in {'library_top_order', 'library_order_shuffle'}
    order = list(reversed(pending['options']))
    before = (deepcopy(serialize_match_snapshot(controller.state)),
              deepcopy(main._controller_snapshot(controller)), sql_facts(repo))
    rejected = client.post(f'/matches/{identifier}/action',
                           json={'player_id': 3 - seat, 'action': {'type': 'choose_mechanic', 'card_ids': order}})
    assert rejected.status_code == 422
    assert (serialize_match_snapshot(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    reload()
    post(seat, {'type': 'choose_mechanic', 'card_ids': order})
    if name == 'Ponder':
        assert main.ACTIVE_MATCHES[identifier].state.pending_mechanic_choice['kind'] == 'library_shuffle'
        reload()
        post(seat, {'type': 'choose_mechanic', 'card_ids': ['keep']})
        assert main.ACTIVE_MATCHES[identifier].state.players[seat].hand == [order[0]]
    final = main.ACTIVE_MATCHES[identifier].state
    assert final.cards[source.id].zone == Zone.GRAVEYARD
    assert final.pending_mechanic_choice is None
    reload()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('name', ['Index', 'Ponder'])
def test_actual_fresh_process_restores_order_or_shuffle_then_completes(seat, name, tmp_path):
    root = tmp_path / 'reorder-restart'
    root.mkdir()
    worker = Path(__file__).with_name('spell_admission_safety_restart_worker.py')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PYTHONDONTWRITEBYTECODE': '1'}
    for phase in ('seed', 'restore'):
        result = subprocess.run([sys.executable, str(worker), phase, str(seat), name, str(root), 'reorder'],
                                env=env, capture_output=True, text=True, timeout=90)
        (root / (phase + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    first = json.loads((root / 'seed-evidence.json').read_text())
    second = json.loads((root / 'restore-evidence.json').read_text())
    assert first['pid'] != second['pid']
    assert second['restored_snapshot_config_rng_exact']
    assert second['actual_order_draw_and_source_departure']
