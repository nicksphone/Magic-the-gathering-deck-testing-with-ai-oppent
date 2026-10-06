"""Actual ASGI paid Favor/response, SQL preservation, and cold-process choice."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client as base_client
from tests.test_batch_graveyard_publication_audit import client
from tests.test_builtin_metadata_refresh import repo, seed_cache
from tests.test_spell_admission_safety_http import sql_facts
from tests.favor_lifecycle_support import (
    position, favor_action, response_action, snap, record, assert_private, assert_outcome,
)


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('mode', ['none', 'zero', 'unsummon', 'veil'])
def test_favor_actual_http_response_choice_atomic_sql_and_cold_continuation(repo, client, seat, mode, tmp_path):
    import main
    seed_cache(repo, [{'card_name': 'Island'}])
    deck = [{'card_name': 'Island', 'quantity': 8}]
    started = client.post('/matches/start', json={'deck_a': deck, 'deck_b': deck,
        'sandbox': True, 'controller_a': 'human', 'controller_b': 'human', 'seed': 19476})
    assert started.status_code == 200, started.text
    controller = main.ACTIVE_MATCHES[started.json()['id']]
    state, data = position(seat, mode)
    state.id = controller.state.id
    controller.state, controller.engine = state, RulesEngine()
    main._persist_active_match(repo, controller)
    path = '/matches/' + state.id

    def post(actor, action):
        response = client.post(path + '/action', json={'player_id': actor, 'action': action})
        assert response.status_code == 200, response.text
        return main.ACTIVE_MATCHES[state.id]

    controller = post(seat, favor_action(data))
    data['stack_id'] = controller.state.stack[-1].id
    assert controller.state.stack[-1].controller == seat
    assert controller.state.stack[-1].payload['mana_spent'] == 4
    if data['response']:
        controller = post(seat, {'type': 'pass_priority'})
        controller = post(data['affected'], response_action(data))
        assert controller.state.stack[-1].payload['mana_spent'] == 1
        for _ in range(2):
            controller = post(controller.state.priority_player, {'type': 'pass_priority'})
        assert len(controller.state.stack) == 1
    data['counters_before_favor'] = dict(controller.state.cards[data['target']].counters)
    for _ in range(2):
        controller = post(controller.state.priority_player, {'type': 'pass_priority'})
    pending = controller.state.pending_mechanic_choice
    assert pending['player_id'] == data['affected'] and pending['min_count'] == 0
    assert pending['continuation_controller'] == pending['resolving_item']['controller'] == seat
    assert_private(controller.state, data['affected'])
    public = client.get(path)
    assert public.status_code == 200
    assert set(public.json()['pending_mechanic_choice']) <= {'kind', 'player_id', 'label', 'count', 'min_count'}
    assert client.get(path + f'/legal-moves?player_id={seat}').json()['moves'] == []
    moves = client.get(path + f'/legal-moves?player_id={data["affected"]}').json()['moves']
    assert any(move.get('type') == 'choose_mechanic' for move in moves)
    data['chosen'] = pending['options'][1]
    find = mode != 'zero'
    choice = {'type': 'choose_mechanic', 'card_ids': [data['chosen']] if find else []}
    invalid = [
        (seat, choice),
        (data['affected'], {**choice, 'card_ids': [data['caster_library'][0]]}),
        (data['affected'], {**choice, 'card_ids': [data['chosen'], data['chosen']]}),
        (data['affected'], {**choice, 'effect_payload': pending['effect_payload']}),
        (data['affected'], favor_action(data)),
    ]
    for actor, action in invalid:
        before = snap(controller.state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
        rejected = client.post(path + '/action', json={'player_id': actor, 'action': action})
        assert rejected.status_code in (403, 422), rejected.text
        assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    record(tmp_path, 'http-search-paused', controller.state, data)
    before = {'root': snap(controller.state), 'controller': deepcopy(main._controller_snapshot(controller)),
              'sql': sql_facts(repo)}
    database = repo.session.get_bind().url.database
    if database:
        expected = tmp_path / 'cold-expected.json'
        output = tmp_path / 'cold-actual.json'
        expected.write_text(json.dumps({'match_id': state.id, 'affected': data['affected'],
                                       'before': before, 'choice': choice}, sort_keys=True))
        repo.session.commit()
        worker = Path(__file__).with_name('favor_lifecycle_http_worker.py')
        result = subprocess.run([sys.executable, str(worker), database, str(expected), str(output)],
            capture_output=True, text=True, timeout=60, cwd=Path(__file__).parents[1],
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        (tmp_path / 'cold-worker.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        cold = json.loads(output.read_text())
        main.ACTIVE_MATCHES.pop(state.id)
        repo.session.expire_all()
        main._restore_active_matches(repo, state.id)
        controller = main.ACTIVE_MATCHES[state.id]
        actual = {'root': snap(controller.state), 'controller': main._controller_snapshot(controller),
                  'sql': sql_facts(repo)}
        assert json.loads(json.dumps(actual)) == cold
    else:
        main.ACTIVE_MATCHES.pop(state.id)
        main._restore_active_matches(repo, state.id)
        controller = main.ACTIVE_MATCHES[state.id]
        assert snap(controller.state) == before['root']
        controller = post(data['affected'], choice)
    record(tmp_path, 'http-actual-complete-before-desired-assertion', controller.state, data)
    assert_private(controller.state, data['affected'])
    assert sum('shuffles their library' in line for line in controller.state.log) == 1
    assert_outcome(controller.state, data, find)
