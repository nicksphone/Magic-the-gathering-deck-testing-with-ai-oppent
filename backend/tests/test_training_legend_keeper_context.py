"""Exact server context is display-only; explicit keeper input stays authoritative."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine
from training.environment import TrainingEnvironment
from tests import test_human_legend_keeper_audit as audit
from tests.test_combat_graveyard_caller_audit import receipts
from tests.test_self_graveyard_replacement_audit import snap


@pytest.fixture
def position(request, receipts, tmp_path):
    seat = request.param
    h = audit.episode(seat, audit.ISAMARU, receipts, tmp_path)
    env = TrainingEnvironment()
    env._state = deepcopy(h.state)
    whole = {**RulesEngine().legal_moves(env._state, seat)[0], 'card_ids': [h.new]}
    return env, h, whole


@pytest.mark.parametrize('position', [1, 2], indirect=True)
def test_whole_view_exact_context_and_projected_hint(position, tmp_path):
    env, h, whole = position
    before, request = snap(env._state), deepcopy(whole)
    selected = env.lookup_intent(whole, h.seat)
    assert selected['action'] == {'type': 'choose_mechanic', 'card_ids': [h.new]}
    hint = env.observe(h.seat)['pending_choice']['prompts'][0]['hint']
    assert not {'legend_context', 'legend_group_index'} & set(hint)
    assert env.lookup_intent({**hint, 'card_ids': [h.new]}, h.seat) == selected
    reordered = deepcopy(whole)
    reordered['legend_context'] = dict(reversed(list(whole['legend_context'].items())))
    assert env.lookup_intent(reordered, h.seat) == selected
    assert snap(env._state) == before and whole == request
    (tmp_path / 'whole-consumer.json').write_text(json.dumps({
        'whole': whole, 'pending': env._state.pending_mechanic_choice,
        'selected': selected, 'projected': hint}))


@pytest.mark.parametrize('position', [1, 2], indirect=True)
@pytest.mark.parametrize('fault', [
    'index_null', 'index_bool', 'index_string', 'index_stale', 'context_null',
    'context_list', 'nested_extra', 'reference_bool', 'foreign_context',
    'missing_key', 'missing_index', 'nonlegend', 'wrongseat', 'unknown', 'missing_choice',
    'null_choice', 'empty_choice', 'duplicate_choice', 'multiple_choice',
    'foreign_choice', 'bool_choice', 'string_choice', 'tuple_choice',
])
def test_reject_before_completion_and_state_pure(position, fault, monkeypatch):
    env, h, whole = position
    request, actor = deepcopy(whole), h.seat
    if fault.startswith('index_'):
        request['legend_group_index'] = {'index_null': None, 'index_bool': False,
                                       'index_string': '0', 'index_stale': 1}[fault]
    elif fault == 'context_null':
        request['legend_context'] = None
    elif fault == 'context_list':
        request['legend_context'] = []
    elif fault == 'nested_extra':
        request['legend_context']['groups'][0]['unexpected'] = 'not authoritative'
    elif fault == 'reference_bool':
        refs = request['legend_context']['groups'][0]['references'][h.old]
        refs[0] = bool(refs[0])
    elif fault == 'foreign_context':
        request['legend_context']['groups'][0]['references'][h.old][1] += 1
    elif fault == 'missing_key':
        del env._state.pending_mechanic_choice['legend_context']
    elif fault == 'missing_index':
        del env._state.pending_mechanic_choice['legend_group_index']
    elif fault == 'nonlegend':
        env._state.pending_mechanic_choice['kind'] = 'discard'
    elif fault == 'wrongseat':
        actor = 3-h.seat
    elif fault == 'unknown':
        request['legend_extra'] = {}
    elif fault == 'missing_choice':
        del request['card_ids']
    else:
        request['card_ids'] = {'null_choice': None, 'empty_choice': [],
                               'duplicate_choice': [h.new, h.new],
                               'multiple_choice': [h.old, h.new],
                               'foreign_choice': ['not-offered'], 'bool_choice': [True],
                               'string_choice': h.new, 'tuple_choice': (h.new,)}[fault]
    before, original = snap(env._state), deepcopy(request)
    def forbidden(_):
        pytest.fail('Rejected legend intent reached complete_action')
    monkeypatch.setattr('ai.action_contract.complete_action', forbidden)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, actor)
    assert snap(env._state) == before and request == original


@pytest.mark.parametrize('position', [1, 2], indirect=True)
def test_copied_other_paid_state_context_rejects(position, receipts, tmp_path):
    env, h, whole = position
    (tmp_path / 'other').mkdir()
    other = audit.episode(h.seat, 'Progenitus', receipts, tmp_path / 'other')
    request = {**whole, 'legend_context': deepcopy(other.state.pending_mechanic_choice['legend_context'])}
    before = snap(env._state)
    with pytest.raises(ActionRejected):
        env.lookup_intent(request, h.seat)
    assert snap(env._state) == before


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('destination', ['library', 'exile'])
def test_cold_http_consumer_keeper_and_replacement(seat, destination, tmp_path):
    pids = []
    for phase in ('seed', 'keeper', 'replacement'):
        result = subprocess.run([sys.executable, '-m', 'tests.test_training_legend_keeper_context', phase, str(seat), destination, str(tmp_path)],
                                cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=120)
        (tmp_path / (phase + '-consumer.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        pids.append(json.loads((tmp_path / (phase + '.json')).read_text())['pid'])
    assert len(set(pids)) == 3
    evidence = json.loads((tmp_path / 'whole-http-materialization.json').read_text())
    assert evidence['whole']['legend_context'] == evidence['pending']['legend_context']
    assert evidence['typed']['card_ids'] == [evidence['keeper']]


def consumer_worker(phase, seat, destination, root):
    # Run the unchanged frozen U9 worker, retaining all its HTTP/privacy/SQL checks.
    from fastapi.testclient import TestClient
    from tests.legend_keeper_restart_worker import run
    original_post = TestClient.post
    def post(client, url, *args, **kwargs):
        body = kwargs.get('json') or {}
        action = body.get('action') or {}
        if phase == 'keeper' and action.get('type') == 'choose_mechanic':
            import main
            mid = url.split('/')[2]
            state = main.ACTIVE_MATCHES[mid].state
            pending = state.pending_mechanic_choice
            if (pending and body.get('player_id') == pending['player_id']
                    and len(action.get('card_ids', [])) == 1):
                public = client.get('/matches/' + mid).json()
                whole = client.get('/matches/' + mid + '/legal-moves',
                                   params={'player_id': seat}).json()['moves'][0]
                assert whole['legend_context'] == public['pending_mechanic_choice']['legend_context']
                env = TrainingEnvironment()
                env._state = deepcopy(state)
                before = snap(env._state)
                intent = {**whole, 'card_ids': action['card_ids']}
                typed = env.lookup_intent(intent, seat)['action']
                assert snap(env._state) == before
                # Raw API remains strict even though lookup_intent accepts display context.
                import persistence.db as db
                with db.engine.connect() as connection:
                    sql_before = list(connection.connection.driver_connection.iterdump())
                controller_before = deepcopy(main._controller_snapshot(main.ACTIVE_MATCHES[mid]))
                rejected = original_post(client, url, *args,
                                         **{**kwargs, 'json': {**body, 'action': intent}})
                assert rejected.status_code == 422
                assert snap(state) == before
                assert main._controller_snapshot(main.ACTIVE_MATCHES[mid]) == controller_before
                with db.engine.connect() as connection:
                    assert list(connection.connection.driver_connection.iterdump()) == sql_before
                kwargs['json'] = {**body, 'action': typed}
                (root / 'whole-http-materialization.json').write_text(json.dumps({
                    'whole': whole, 'pending': pending, 'typed': typed,
                    'keeper': action['card_ids'][0]}))
        return original_post(client, url, *args, **kwargs)
    TestClient.post = post
    run(phase, seat, destination, root)


if __name__ == '__main__':
    consumer_worker(sys.argv[1], int(sys.argv[2]), sys.argv[3], Path(sys.argv[4]).resolve())
