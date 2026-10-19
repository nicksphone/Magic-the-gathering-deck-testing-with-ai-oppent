"""Inert producer protocol tests, not genuine games or AI-quality evidence."""
import json

import pytest

from analytics.resource_budget import SimulationResourceLimit
from scripts import matchup_round_robin as runner
from tests.test_baseline_measurement_package import protocol_run


def test_actual_preencoding_budget_failure_retains_its_dimension(tmp_path, monkeypatch):
    result, calls, _, _ = protocol_run(tmp_path, monkeypatch, pre_encode_stop=True)
    failure = result['production']['games'][0]
    assert len(calls) == 1 and not result['production']['complete']
    assert failure['status'] == 'resource_limit'
    assert failure.get('resource_limit_dimension') == 'result_json'
    assert not result['package']['eligible']
    assert result['production']['legacy_totals']['timeouts'] == 0


@pytest.mark.parametrize('dimension', [
    'deadline', 'action_log', 'game_log', 'game_log_entries', 'batch_log',
    'batch_log_entries', 'trace_entry', 'trace_scalar', 'trace_nodes', 'trace_depth',
    'result_json', 'request_json', 'error_utf8',
])
def test_known_resource_reason_survives_the_outer_producer_catch(tmp_path, monkeypatch, dimension):
    def reject(*args):
        raise SimulationResourceLimit(dimension)

    monkeypatch.setattr(runner, 'preflight_game_record', reject)
    result, calls, _, _ = protocol_run(tmp_path, monkeypatch)
    failure = result['production']['games'][0]
    assert failure.get('resource_limit_dimension') == dimension
    assert len(calls) == 1 and failure['status'] == 'resource_limit'
    assert not result['package']['eligible']
    assert result['production']['legacy_totals']['timeouts'] == 0


@pytest.mark.parametrize('resource_exception,dimension', [
    (False, 'result_json'), (True, 'UNREVIEWED-DIAGNOSTIC'), (True, None),
    (True, False), (True, {'value': 'result_json'}), (True, ['result_json']),
])
def test_arbitrary_error_attributes_and_messages_are_not_diagnostic_fields(
        tmp_path, monkeypatch, resource_exception, dimension):
    error = SimulationResourceLimit('UNREVIEWED-DIAGNOSTIC') if resource_exception else ValueError('UNREVIEWED-DIAGNOSTIC')
    error.dimension = dimension

    def reject(*args):
        raise error

    monkeypatch.setattr(runner, 'preflight_game_record', reject)
    result, calls, _, _ = protocol_run(tmp_path, monkeypatch)
    failure = result['production']['games'][0]
    assert failure.get('resource_limit_dimension') is None
    assert 'UNREVIEWED-DIAGNOSTIC' not in json.dumps(failure)
    assert failure['status'] == ('resource_limit' if resource_exception else 'execution_error')
    assert len(calls) == 1 and not result['package']['eligible']
