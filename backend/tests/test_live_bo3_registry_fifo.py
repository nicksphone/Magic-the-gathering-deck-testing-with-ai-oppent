"""Three genuine FIFO stages; no registry repair or persisted-row cleanup."""
from copy import deepcopy
import json
import os
from pathlib import Path

import main
from sqlmodel import Session
from persistence.db import engine
from persistence.repository import Repository
from game_state.serializers import serialize_match_snapshot
from tests import test_api_input_contracts as api
from tests import test_live_bo3_policy as legacy
from tests.test_selected_mana_http import retain
from tests.test_training_choice_coverage import position


def finish(generator):
    try:
        next(generator)
    except StopIteration:
        return
    raise AssertionError('Original fixture yielded twice')


def test_real_fixture_eager_reload_fixture_fifo(monkeypatch):
    original = dict(main.ACTIVE_MATCHES)
    report = {'stages': [], 'original_registry_count': len(original)}
    private_report = os.environ.get('MTG_FIFO_PRIVATE_REPORT')
    output = Path(private_report) if private_report else None
    first = api.game.__wrapped__(monkeypatch)
    try:
        _, controller = next(first)
        env = position(1)
        target = env._state.id
        report['first_controller_id'] = controller.state.id
        report['target_id'] = target
        retain(controller, env)
        snapshot = serialize_match_snapshot(controller.state)
        assert controller.state.sideboard_facts['game_id'] == target
        with Session(engine) as session:
            saved = Repository(session).get_active_match(target)
            assert saved is not None
            assert json.loads(saved.state_json) == json.loads(json.dumps(snapshot))
        report['stages'].append('first_real_adoption_saved')
    finally:
        finish(first)
        report['registry_after_first_equals_original'] = main.ACTIVE_MATCHES == original
        if output is not None:
            output.write_text(json.dumps(report, indent=2) + '\n')
    assert main.ACTIVE_MATCHES == original

    # Execute the whole existing body, including every original HTTP/assertion.
    legacy.test_http_choice_and_restored_seed_provenance()
    report['stages'].append('unchanged_real_legacy_body_complete')
    report['target_cached_after_eager_body'] = target in main.ACTIVE_MATCHES
    if target in main.ACTIVE_MATCHES:
        report['loaded_target_snapshot_equal'] = (
            serialize_match_snapshot(main.ACTIVE_MATCHES[target].state) == snapshot)
    if output is not None:
        output.write_text(json.dumps(report, indent=2) + '\n')

    second = api.game.__wrapped__(monkeypatch)
    try:
        _, controller = next(second)
        env = position(1)
        assert env._state.id == target
        report['second_controller_id'] = controller.state.id
        report['target_is_foreign_controller'] = (
            target in main.ACTIVE_MATCHES and main.ACTIVE_MATCHES[target] is not controller)
        if output is not None:
            output.write_text(json.dumps(report, indent=2) + '\n')
        retain(controller, env)  # Expected RED is the actual unchanged line-63 guard.
        report['stages'].append('second_real_adoption_complete')
    finally:
        finish(second)
        report['original_controllers_preserved'] = all(
            main.ACTIVE_MATCHES.get(key) is value for key, value in original.items())
        if output is not None:
            output.write_text(json.dumps(report, indent=2) + '\n')
