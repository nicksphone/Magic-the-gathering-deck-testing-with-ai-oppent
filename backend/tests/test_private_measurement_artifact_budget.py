"""Inert private writer/reader protocols, not games or policy-strength evidence."""
from copy import deepcopy
import hashlib
import inspect
import json
from types import SimpleNamespace

import pytest

from analytics.replay_tools import normalize_log_line
from analytics.resource_budget import RESOURCE_LIMITS, ResourceBudget, SimulationResourceLimit
from scripts import baseline_report as report
from scripts import matchup_round_robin as runner
from scripts import regression_matrix_replay as replay
from tests.test_baseline_measurement_package import protocol_run


def private(result, raw, budget):
    assert 'private_artifact' in inspect.signature(runner.preflight_game_record).parameters, 'Explicit PRIVATE path is missing'
    return runner.preflight_game_record(result, raw, budget, True)


def checker():
    value = getattr(runner, 'checked_private_artifact', None)
    assert callable(value), 'Typed private-artifact checker is missing'
    return value


def logs():
    return ['inert public line ' + 'x' * 16384 for _ in range(70)]


def result_for(raw):
    return dict(winner=1, turn=2, ticks=70, timeout=False, starting_player=1,
                log=[normalize_log_line(line) for line in raw], log_hash='0' * 64)


def test_large_private_record_is_lossless_while_default_result_stays_bounded(tmp_path):
    raw = logs(); result = result_for(raw)
    budget = ResourceBudget(dict(RESOURCE_LIMITS)); budget.begin_game(raw)
    before = (budget.deadline, budget.game_bytes, budget.batch_bytes, budget.batch_entries)
    with pytest.raises(SimulationResourceLimit):
        runner.preflight_game_record(result, raw, budget)
    encoded = private(result, raw, budget)
    assert len(encoded) > RESOURCE_LIMITS['result_json_bytes']
    receipt = runner.write_private_game(tmp_path, 1, result, raw)
    actual = (tmp_path / receipt['reference']).read_bytes()
    assert actual == runner.canonical_bytes(json.loads(encoded))
    assert json.loads(actual)['result'] == result and json.loads(actual)['raw_log'] == raw
    assert hashlib.sha256(actual).hexdigest() == receipt['record_sha256']
    assert (budget.deadline, budget.game_bytes, budget.batch_bytes, budget.batch_entries) == before


@pytest.mark.parametrize('key', ['padding', 'other_log'])
def test_private_optin_cannot_hide_large_result_metadata(key):
    raw = ['inert']; result = dict(result_for(raw), **{key: 'x' * (RESOURCE_LIMITS['result_json_bytes'] + 1)})
    with pytest.raises(SimulationResourceLimit) as caught:
        private(result, raw, ResourceBudget(dict(RESOURCE_LIMITS)))
    assert caught.value.dimension == 'result_json'


@pytest.mark.parametrize('key', ['result_json_bytes', 'snapshot_json_bytes'])
def test_private_metadata_retains_both_original_small_result_boundaries(key):
    limits = dict(RESOURCE_LIMITS); limits[key] = 20
    with pytest.raises(SimulationResourceLimit) as caught:
        private(result_for(['inert']), ['inert'], ResourceBudget(limits))
    assert caught.value.dimension == 'result_json'


@pytest.mark.parametrize('kind', ['bytes', 'entries', 'normalized'])
def test_private_logs_retain_original_log_boundaries(kind):
    limits = dict(RESOURCE_LIMITS); limits['game_log_utf8_bytes'] = 20; limits['game_log_entries'] = 2
    raw = ['x' * 21] if kind == 'bytes' else ['x'] * 3 if kind == 'entries' else ['inert']
    result = result_for(raw)
    if kind == 'normalized': result['log'] = ['x' * 21]
    with pytest.raises(SimulationResourceLimit) as caught:
        private(result, raw, ResourceBudget(limits))
    assert caught.value.dimension == ('game_log_entries' if kind == 'entries' else 'game_log')


def test_encoded_private_bytes_still_respect_existing_batch_ceiling():
    limits = dict(RESOURCE_LIMITS); limits['batch_log_utf8_bytes'] = 2048
    raw = ['\x01' * 500]
    with pytest.raises(SimulationResourceLimit) as caught:
        private(result_for(raw), raw, ResourceBudget(limits))
    assert caught.value.dimension == 'batch_log'


def test_unmatched_oversized_normalized_field_is_not_a_metadata_escape():
    result = result_for(['inert']); result['log'] = ['x' * (RESOURCE_LIMITS['result_json_bytes'] + 1)]
    with pytest.raises(SimulationResourceLimit) as caught:
        private(result, ['inert'], ResourceBudget(dict(RESOURCE_LIMITS)))
    assert caught.value.dimension == 'result_json'


@pytest.mark.parametrize('value', [None, 1, 'private'])
def test_private_optin_is_an_exact_boolean(value):
    assert 'private_artifact' in inspect.signature(runner.preflight_game_record).parameters
    with pytest.raises((ValueError, TypeError)):
        runner.preflight_game_record(result_for([]), [], ResourceBudget(dict(RESOURCE_LIMITS)), value)


def test_private_paths_are_closed_and_nested_metadata_is_not_a_log():
    check = checker(); budget = ResourceBudget(dict(RESOURCE_LIMITS))
    for name in ('unknown.json', '../producer.json', 'game-03.json'):
        with pytest.raises(ValueError): check(name, {}, budget)
    value = dict(rows=[], game_records=[], configuration={'log': 'x' * (RESOURCE_LIMITS['result_json_bytes'] + 1)})
    with pytest.raises(SimulationResourceLimit): check('producer.json', value, budget)


def test_actual_fixed_producer_and_packager_roundtrip_large_private_rows(tmp_path, monkeypatch):
    original = replay._record_game_evidence
    expected = []
    def deliver(result, raw, writer):
        budget = inspect.getclosurevars(writer).nonlocals['budget']
        current = list(raw)
        for line in logs():
            candidate = [*current, line]
            budget.accept_candidate(SimpleNamespace(log=current), SimpleNamespace(cards={}, log=candidate))
            current = candidate
        result['log'] = [normalize_log_line(line) for line in current]
        expected.append((deepcopy(result), list(current)))
        return original(result, current, writer)
    monkeypatch.setattr(replay, '_record_game_evidence', deliver)
    output, calls, charges, _ = protocol_run(tmp_path, monkeypatch)
    assert len(calls) == len(expected) == 2 and output['production']['complete']
    assert output['package']['eligible'] and output['production']['not_run_games'] == 0
    directory = tmp_path / 'measurement'
    for index, (result, raw) in enumerate(expected, 1):
        record = json.loads((directory / f'game-{index:02d}.json').read_bytes())
        assert record['result'] == result and record['raw_log'] == raw
        assert output['production']['rows'][index - 1]['log'] == raw
    assert (directory / 'producer.json').stat().st_size > RESOURCE_LIMITS['result_json_bytes']
    assert (directory / 'package.json').stat().st_size <= RESOURCE_LIMITS['result_json_bytes']
    assert all(path.stat().st_size == count for path, count in charges)
    assert sum(count for _, count in charges) < RESOURCE_LIMITS['batch_log_utf8_bytes']
    assert output['package']['package']['report']['unavailable_metrics'] == {}


def test_private_package_charge_keeps_aggregate_guard_and_late_raw_checks(tmp_path, monkeypatch):
    calls = []
    def charge(path, count):
        calls.append((path.name, count))
        assert sum(row[1] for row in calls) <= 1, 'Inert actual aggregate guard rejection'
    package = report.package_measurement
    def guarded(production, **kwargs):
        return package(production, **{**kwargs, 'artifact_guard': charge})
    monkeypatch.setattr(report, 'package_measurement', guarded)
    with pytest.raises(AssertionError, match='aggregate'):
        protocol_run(tmp_path, monkeypatch)
    assert calls
