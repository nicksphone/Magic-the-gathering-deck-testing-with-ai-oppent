"""Private-file/clock protocols with inert run_game, never actual gameplay."""
from copy import deepcopy
import hashlib
import json

import pytest

from analytics import resource_budget
from scripts import baseline_report as report
from scripts import matchup_round_robin as runner
from tests.test_baseline_measurement_package import protocol_run


@pytest.mark.parametrize('ordinal', [1, 2])
@pytest.mark.parametrize('fault', ['missing', 'mutated', 'symlink'])
def test_packaging_reopens_each_actual_raw_record(tmp_path, monkeypatch, ordinal, fault):
    package = report.package_measurement

    def altered(production, **kwargs):
        directory = kwargs['directory']
        path = directory / f'game-{ordinal:02d}.json'
        actual = path.read_bytes()
        if fault == 'missing':
            path.unlink()
        elif fault == 'mutated':
            path.write_bytes(actual + b' ')
        else:
            target = directory / 'not-the-actual-record.json'
            target.write_bytes(actual)
            path.unlink()
            path.symlink_to(target)
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises((OSError, ValueError)):
        protocol_run(tmp_path, monkeypatch)


def test_packaging_rejects_an_unjoined_raw_file(tmp_path, monkeypatch):
    package = report.package_measurement

    def altered(production, **kwargs):
        directory = kwargs['directory']
        (directory / 'game-99.json').write_bytes((directory / 'game-01.json').read_bytes())
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises(ValueError):
        protocol_run(tmp_path, monkeypatch)


def test_packaging_rejects_the_same_physical_record_for_two_samples(tmp_path, monkeypatch):
    package = report.package_measurement

    def altered(production, **kwargs):
        first = kwargs['directory'] / 'game-01.json'
        second = kwargs['directory'] / 'game-02.json'
        assert first.read_bytes() == second.read_bytes(), 'Both inert results deliberately identical'
        second.unlink()
        second.hardlink_to(first)
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises(ValueError):
        protocol_run(tmp_path, monkeypatch, outcomes=(1, 1))


def test_packaging_bounds_the_actual_raw_record_before_decode(tmp_path, monkeypatch):
    package = report.package_measurement

    def altered(production, **kwargs):
        (kwargs['directory'] / 'game-01.json').write_bytes(
            b'x' * (kwargs['budget'].limits['result_json_bytes'] + 1))
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises(resource_budget.SimulationResourceLimit) as caught:
        protocol_run(tmp_path, monkeypatch)
    assert caught.value.dimension == 'result_json'


@pytest.mark.parametrize('fault', ['missing', 'mutated'])
def test_final_package_charge_cannot_hide_late_raw_record_changes(tmp_path, monkeypatch, fault):
    package = report.package_measurement

    def altered(production, **kwargs):
        charge = kwargs['artifact_guard']

        def late_charge(path, count):
            charge(path, count)
            if path.name == 'package.json':
                raw_path = kwargs['directory'] / 'game-02.json'
                if fault == 'missing':
                    raw_path.unlink()
                else:
                    raw_path.write_bytes(raw_path.read_bytes() + b' ')

        return package(production, **dict(kwargs, artifact_guard=late_charge))

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises((ValueError, OSError)):
        protocol_run(tmp_path, monkeypatch)


def capture_actual_writes(monkeypatch):
    write = runner.write_private_game
    observed = []

    def actual(directory, ordinal, result, raw):
        saved = deepcopy(result)
        receipt = write(directory, ordinal, result, raw)
        observed.append(dict(ordinal=ordinal, receipt=deepcopy(receipt), result=saved))
        return receipt

    monkeypatch.setattr(runner, 'write_private_game', actual)
    return observed


def test_producer_retains_genuine_full_receipts_and_result_before_evidence(tmp_path, monkeypatch):
    observed = capture_actual_writes(monkeypatch)
    package = report.package_measurement

    def checked(production, **kwargs):
        records = production.get('game_records')
        assert type(records) is list and len(records) == len(observed) == 2
        for index, (binding, actual) in enumerate(zip(records, observed)):
            assert binding['ordinal'] == actual['ordinal'] == index + 1
            assert binding['receipt'] == actual['receipt']
            assert binding['result'] == actual['result']
            assert binding['coordinate'] == production['selected'][index]
            path = kwargs['directory'] / binding['receipt']['reference']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == binding['receipt']['record_sha256']
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', checked)
    result, calls, _, _ = protocol_run(tmp_path, monkeypatch)
    assert len(calls) == 2 and result['package']['eligible'] is True


@pytest.mark.parametrize('fault', [
    'missing_receipt', 'duplicate', 'foreign', 'record_hash', 'raw_hash',
    'result', 'coordinate', 'ordinal_bool', 'sample_result', 'row_raw',
])
def test_resealed_producer_cannot_substitute_a_receipt_or_join(tmp_path, monkeypatch, fault):
    capture_actual_writes(monkeypatch)
    package = report.package_measurement

    def altered(production, **kwargs):
        records = production.get('game_records')
        assert type(records) is list and len(records) == 2, 'Actual full writer receipts were discarded'
        row = records[0]
        if fault == 'missing_receipt':
            del row['receipt']
        elif fault == 'duplicate':
            records[1] = deepcopy(records[0])
        elif fault == 'foreign':
            row['receipt']['reference'] = '../game-01.json'
        elif fault == 'record_hash':
            row['receipt']['record_sha256'] = 'f' * 64
        elif fault == 'raw_hash':
            row['receipt']['raw_sha256'] = 'f' * 64
        elif fault == 'result':
            row['result']['winner'] = 2
        elif fault == 'coordinate':
            row['coordinate'] = deepcopy(production['selected'][1])
        elif fault == 'ordinal_bool':
            row['ordinal'] = True
        elif fault == 'sample_result':
            production['games'][0]['result']['ticks'] += 1
        elif fault == 'row_raw':
            production['rows'][0]['log'].append('unjoined protocol line')
        # Adversarial re-sealing is a negative: it must not replace physical evidence.
        (kwargs['directory'] / 'producer.json').write_bytes(runner.canonical_bytes(production))
        return package(production, **kwargs)

    monkeypatch.setattr(report, 'package_measurement', altered)
    with pytest.raises((ValueError, OSError)):
        protocol_run(tmp_path, monkeypatch)


def test_real_deadline_between_mirrors_retains_only_truthful_first_raw(tmp_path, monkeypatch):
    clock = [0.0]
    actual_type = resource_budget.ResourceBudget
    created = []

    def controlled(limits):
        budget = actual_type(limits, clock=lambda: clock[0])
        created.append(budget)
        return budget

    monkeypatch.setattr(resource_budget, 'ResourceBudget', controlled)
    counters = runner.fixed_game_counters
    boundaries = []

    def expire_between(raw, timed_out):
        value = counters(raw, timed_out)
        boundaries.append(dict(value))
        clock[0] = created[0].deadline  # Real monotonic expiry, not an injected exception.
        return value

    monkeypatch.setattr(runner, 'fixed_game_counters', expire_between)
    with pytest.raises(resource_budget.SimulationResourceLimit) as caught:
        protocol_run(tmp_path, monkeypatch)
    assert caught.value.dimension == 'deadline'
    assert len(created) == len(boundaries) == 1
    assert boundaries[0]['timeouts'] == boundaries[0]['long_game_timeouts'] == 0
    directory = tmp_path / 'measurement'
    assert sorted(path.name for path in directory.iterdir()) == ['game-01.json']
    record = json.loads((directory / 'game-01.json').read_bytes())
    assert record['result']['winner'] == 1 and record['result']['timeout'] is False
    assert record['raw_sha256'] == hashlib.sha256(json.dumps(
        record['raw_log'], separators=(',', ':')).encode('ascii')).hexdigest()
    assert not (directory / 'game-02.json').exists()
    assert not (directory / 'producer.json').exists() and not (directory / 'package.json').exists()
