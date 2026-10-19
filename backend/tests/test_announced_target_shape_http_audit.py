"""Strict persisted-frame HTTP422 contract; no production compatibility adapter."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from rules_engine.engine import RulesEngine
from tests.generic_import_fixtures import client as base_client
from tests.test_builtin_metadata_refresh import repo
from tests.test_paid_counter_family_audit import http_position
from tests.test_spell_admission_safety_http import sql_facts
from tests.test_targeted_search_lifecycle_audit import cold_sql
from tests.test_announced_target_reference_product import early_path, act, snap

CASES = {
    'root-number': 1,
    'ids-null': {'target_card_ids': None},
    'mode-child-null': {'mode_targets': {'one': None}},
}


@pytest.fixture
def client(base_client, repo, monkeypatch):
    import main
    monkeypatch.setattr(main, 'engine', repo.session.get_bind())
    # Observe actual HTTP500, rather than rethrowing server exceptions into pytest.
    value = TestClient(main.app, raise_server_exceptions=False)
    yield value
    value.close()


@pytest.mark.parametrize('seat', [1, 2])
@pytest.mark.parametrize('case', ['root-number', 'ids-null', 'mode-child-null'])
def test_actual_persisted_paid_frame_shape_error_is_422_and_root_sql_immutable(seat, case, repo, client, tmp_path):
    import main
    state, _, _ = early_path(seat, 'conditional')
    # Explicit negative corruption AFTER real paid actions. Receipt remains genuine.
    state.stack[-1].payload['__announced_targets'] = deepcopy(CASES[case])
    state = act(state, state.priority_player, {'type': 'pass_priority'})
    controller, _, _, url = http_position(repo, client, seat, 'Fertilid')
    state.id = controller.state.id
    controller.state = state  # Install actual episode in fresh owned fixture, not runtime repair.
    controller.engine = RulesEngine()
    main._persist_active_match(repo, controller)
    mid = state.id
    before = snap(state), deepcopy(main._controller_snapshot(controller)), sql_facts(repo)
    cold_sql(repo, mid, before)
    main.ACTIVE_MATCHES.pop(mid)
    main._restore_active_matches(repo, mid)
    controller = main.ACTIVE_MATCHES[mid]
    assert (snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)) == before
    response = client.post(url + '/action', json={'player_id': state.priority_player,
        'action': {'type': 'pass_priority'}})
    after = snap(controller.state), main._controller_snapshot(controller), sql_facts(repo)
    (tmp_path/'actual-shape-http.json').write_text(json.dumps({
        'case': case, 'seat': seat, 'status': response.status_code, 'body': response.text,
        'before': before, 'after': after}, sort_keys=True, default=str))
    assert after == before
    cold_sql(repo, mid, after)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['code'] == 'illegal_action'
