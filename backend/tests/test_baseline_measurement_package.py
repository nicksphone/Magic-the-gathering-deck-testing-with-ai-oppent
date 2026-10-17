"""Inert producer/receipt protocols, never played games or strength evidence."""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from analytics.resource_budget import RESOURCE_LIMITS, ResourceBudget, SimulationResourceLimit, checked_json
from scripts import baseline_report as report
from scripts import matchup_round_robin as runner
from tests.test_baseline_report_comparison import records as comparison_records, seal
from tests.test_matchup_round_robin_protocol import replay_namespace


def required(module, name):
    value = getattr(module, name, None)
    assert callable(value), 'Missing fixed producer boundary: ' + name
    return value


def test_long_tick_timeout_adapts_comparison_without_rewriting_legacy():
    package = comparison_records.__wrapped__()[0]
    package['measurement']['samples'][0].update(status='timeout', winner=None)
    pair = package['report']['win_rates_by_archetype_pair']['Control vs Ramp']
    pair.update(resolved_games=19, timeouts=1, wins_a=9, win_rate_a=47.37, win_rate_b=52.63,
                wilson_ci_a=report.AnalyticsService._wilson_interval(9, 19),
                wilson_ci_b=report.AnalyticsService._wilson_interval(10, 19))
    legacy = dict.fromkeys(report.ANOMALY_KEYS, 0)
    legacy['long_game_timeouts'] = 1
    saved = deepcopy(legacy)
    # The old report's actual passthrough is the RED baseline, not a fake failure.
    adapter = getattr(runner, 'comparison_gate_totals', lambda values: dict(values))
    package['report']['anomalies'] = adapter(legacy)
    report._comparison_admit(seal(package))
    assert package['report']['anomalies']['timeouts'] == 1
    assert legacy == saved and legacy['timeouts'] == 0


def test_full_result_cap_precedes_existing_encoders_and_writer():
    namespace = replay_namespace()
    calls = []
    original = namespace['json']
    namespace['json'] = SimpleNamespace(
        dumps=lambda *a, **kw: (calls.append('encoder'), original.dumps(*a, **kw))[1],
        loads=original.loads)
    budget = ResourceBudget(dict(RESOURCE_LIMITS), clock=lambda: 0)
    result = {'log': ['x' * (RESOURCE_LIMITS['result_json_bytes'] + 1)]}
    def writer(result, raw):
        calls.append('writer')
    def before_encode(result, raw):
        budget.checked_result(result)
        checked_json({'result': result, 'raw_log': raw}, budget.limits['result_json_bytes'], 'result_json')
    writer.before_encode = before_encode
    with pytest.raises(SimulationResourceLimit):
        namespace['_record_game_evidence'](result, list(result['log']), writer)
    assert calls == []


def test_default_receipt_path_keeps_original_writer_validation():
    namespace = replay_namespace()
    result = {'winner': 1, 'log': ['inert public protocol']}
    namespace['_record_game_evidence'](result, ['inert public protocol'], lambda *a: None)
    assert result['evidence'] is None
    assert result['stop_reason'] == 'evidence_error'


@pytest.mark.parametrize('fault', ['negative', 'bool', 'missing', 'long_exceeds'])
def test_comparison_totals_reject_unknown_legacy_counts(fault):
    totals = dict.fromkeys(report.ANOMALY_KEYS, 0)
    if fault == 'negative': totals['timeouts'] = -1
    if fault == 'bool': totals['timeouts'] = False
    if fault == 'missing': del totals['stall_streaks']
    if fault == 'long_exceeds': totals['other'] = 0
    with pytest.raises(ValueError):
        required(runner, 'comparison_gate_totals')(totals)


def trace(pid=1, *, passed=True, stall=True, land=False):
    return 'AI TRACE ' + json.dumps(dict(trace=True, pid=pid, turn=1,
        step='Step.PRECOMBAT_MAIN', active_player=pid, priority_player=pid,
        action={'type': 'pass_priority' if passed else 'play_land'},
        stall_actionable_options=stall, legal_has_land=land,
        legal_non_pass=stall, mana_pool={}, bad_blocks=0,
        lethal_attack_available=False, redundant_removal_casts=0))


def test_gate_legacy_final_combined_run_not_per_player_streaks():
    fn = required(runner, 'fixed_game_counters')
    raw = [trace(1), trace(2), trace(1)]
    totals = fn(raw, False)
    assert totals['stall_streaks'] == 1 and totals['passed_with_options'] == 3
    assert fn(raw + [trace(2, passed=False)], False)['stall_streaks'] == 0
    assert fn([trace(1, land=True)], False)['missed_land_windows'] == 1


def test_tick_long_game_legacy_and_comparison_counts_differ_explicitly():
    totals = required(runner, 'fixed_game_counters')([trace(1, stall=False)] * 10, True)
    assert totals['timeouts'] == 0 and totals['long_game_timeouts'] == 1
    adapted = required(runner, 'comparison_gate_totals')({key: totals[key] for key in report.ANOMALY_KEYS})
    assert adapted['timeouts'] == adapted['long_game_timeouts'] == 1


def test_every_existing_scanner_failure_counter_comes_from_raw_log():
    raw = ['Invalid targets for protocol', 'Cannot pay mana cost for protocol',
           'Failed additional costs for protocol']
    result = required(runner, 'fixed_game_counters')(raw, False)
    assert (result['invalid_targets'], result['cost_failures'], result['additional_cost_failures']) == (1, 1, 1)


@pytest.mark.parametrize('fault', ['result', 'envelope', 'deadline'])
def test_preflight_checks_complete_envelope_not_only_raw_or_result(fault):
    limits = dict(RESOURCE_LIMITS)
    if fault == 'result': limits['result_json_bytes'] = 20
    if fault == 'envelope': limits['result_json_bytes'] = 130
    if fault == 'deadline': limits['deadline_seconds'] = 0
    budget = ResourceBudget(limits, clock=lambda: 0)
    with pytest.raises(SimulationResourceLimit):
        required(runner, 'preflight_game_record')({'winner': 1, 'log': ['x' * 50]}, ['x' * 50], budget)


def test_preflight_matches_exact_real_writer_envelope():
    import hashlib
    budget = ResourceBudget(dict(RESOURCE_LIMITS), clock=lambda: 0)
    result, raw = {'winner': 2, 'log': ['normalized']}, ['raw \\ public']
    encoded = required(runner, 'preflight_game_record')(result, raw, budget)
    expected_hash = hashlib.sha256(json.dumps(raw, separators=(',', ':')).encode()).hexdigest()
    assert json.loads(encoded) == dict(schema_version=1, result=result, raw_log=raw, raw_sha256=expected_hash)


def test_new_hook_error_identity_propagates_before_any_encoding():
    namespace = replay_namespace()
    failure = RuntimeError('inert protocol failure')
    def writer(*args):
        pytest.fail('writer must not run')
    def before(*args):
        raise failure
    writer.before_encode = before
    with pytest.raises(RuntimeError) as caught:
        namespace['_record_game_evidence']({}, [], writer)
    assert caught.value is failure


def partition_fixture(tmp_path, monkeypatch):
    import ast
    import hashlib
    import sys
    from types import ModuleType
    backend = tmp_path / 'backend'
    (backend / 'ai').mkdir(parents=True)
    text = ('import json, hashlib\ndef policy():\n    return 2\n'
            'def activation(configuration, features):\n'
            '    assert policy() == 2\n'
            '    return {"configuration_sha256": hashlib.sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "features": features}\n')
    path = backend / 'ai/policy.py'
    path.write_text(text)
    module = ModuleType('inert_baseline_partition_control')
    module.__file__ = str(path)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(text, str(path), 'exec'), module.__dict__)
    files = runner.collect_source_manifest(backend)
    binding = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_files=files, backend_sha256=runner.digest(files))
    controlled = ast.dump(ast.parse(text.replace('return 2', 'return 1')), include_attributes=False)
    partition = dict(schema_version=1, arm='protocol-after', configuration={'mode': 'protocol'},
        controlled_files={'ai/policy.py': hashlib.sha256(controlled.encode()).hexdigest()},
        features={'task2.3': [dict(path='ai/policy.py', kind='python', qualified_name='policy',
            reference='def policy():\n    return 1\n', active='def policy():\n    return 2\n')]},
        activation_control=dict(path='ai/policy.py', qualname='activation'))
    return backend, binding, partition, module.activation


def test_partition_checks_real_source_inverse_and_invokes_bound_control(tmp_path, monkeypatch):
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    result = required(runner, 'verify_measurement_partition')(
        binding, backend, partition, runner.digest(partition), {'mode': 'protocol'}, control)
    assert result['controlled_policy_sha256'] == runner.digest(dict(
        files=partition['controlled_files'], configuration={'mode': 'protocol'}))
    assert set(result['experimental_features']) == {'task2.3'}
    assert result['activation']['features'] == result['experimental_features']


@pytest.mark.parametrize('fault', ['source', 'unlisted_file', 'configuration', 'manifest', 'foreign_control'])
def test_partition_rejects_resealed_undeclared_drift(tmp_path, monkeypatch, fault):
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    approved = runner.digest(partition)
    configuration = {'mode': 'protocol'}
    if fault == 'source':
        path = backend / 'ai/policy.py'
        path.write_text(path.read_text() + '\ndef unrelated():\n    return 7\n')
    if fault == 'unlisted_file': (backend / 'other.txt').write_text('unlisted')
    if fault == 'configuration': configuration['mode'] = 'different'
    if fault == 'manifest': partition['arm'] = 'unreviewed'
    if fault == 'foreign_control': control = lambda *args: {}
    binding['backend_files'] = runner.collect_source_manifest(backend)
    binding['backend_sha256'] = runner.digest(binding['backend_files'])
    with pytest.raises(ValueError):
        required(runner, 'verify_measurement_partition')(
            binding, backend, partition, approved, configuration, control)


def test_activation_control_really_runs_and_cannot_be_replaced_by_receipt(tmp_path, monkeypatch):
    fn = required(runner, 'verify_measurement_partition')
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    # A genuine failing branch control must not become a positive label/hash.
    control.__globals__['policy'] = lambda: 0
    with pytest.raises(AssertionError):
        fn(
            binding, backend, partition, runner.digest(partition), {'mode': 'protocol'}, control)


def test_missing_artifact_guard_prevents_any_game_or_output(tmp_path):
    fn = required(runner, 'run_fixed_game_measurement')
    with pytest.raises(ValueError, match='artifact'):
        fn({}, [], selected_pair=[], selected_token=0, difficulty='master', max_ticks=1,
           limits=dict(RESOURCE_LIMITS), private_directory=tmp_path/'absent',
           source_binding={}, partition={}, partition_sha256='', activation_check=None,
           artifact_guard=None, oracle_path=tmp_path/'oracle.json', log_priors_path=tmp_path/'priors.json')
    assert not (tmp_path/'absent').exists()


def test_packager_requires_real_closed_files_not_just_counter_dictionary(tmp_path):
    fn = required(report, 'package_measurement')
    with pytest.raises((ValueError, FileNotFoundError)):
        fn({}, directory=tmp_path, oracle_path=tmp_path/'oracle.json',
           log_priors_path=tmp_path/'priors.json', budget=ResourceBudget(dict(RESOURCE_LIMITS)),
           artifact_guard=lambda *args: None)
    assert list(tmp_path.iterdir()) == []


def test_full_builtin_admission_rejects_unselected_inventory_tamper():
    from card_data.seed_cards import seed_card_payload
    rows = []
    for name, text in runner.builtin_templates().items():
        inventory = runner._template_inventory(text)
        boards = {key: [dict(deepcopy(seed_card_payload(card)), card_name=seed_card_payload(card)['name'], quantity=count)
                        for card, count in board.items()] for key, board in inventory.items()}
        rows.append(dict(source='builtin', id=None, name=name, classification_status='resolved',
                         archetype='Protocol', **boards))
    runner.admit_execution_rows(runner.validate_export(runner.make_export(rows, corpus_sha256='a' * 64)))
    rows[-1]['mainboard'][0]['quantity'] += 1
    with pytest.raises(ValueError, match='inventory'):
        runner.admit_execution_rows(rows)


@pytest.mark.parametrize('key', list(RESOURCE_LIMITS))
def test_all_fourteen_real_resource_boundaries_remain_enforced(key):
    from analytics.resource_budget import checked_text
    from types import SimpleNamespace
    limits = dict(RESOURCE_LIMITS)
    limits[key] = 0 if key in ('deadline_seconds', 'trace_depth', 'game_log_entries', 'batch_log_entries') else 1
    budget = ResourceBudget(limits, clock=lambda: 0)
    with pytest.raises(SimulationResourceLimit):
        if key == 'request_json_bytes': checked_json({}, limits[key], 'request_json')
        elif key in ('result_json_bytes', 'snapshot_json_bytes'): budget.checked_result({})
        elif key == 'error_utf8_bytes': checked_text('xx', limits[key], 'error_utf8')
        elif key in ('trace_entry_utf8_bytes', 'trace_scalar_utf8_bytes', 'trace_value_nodes', 'trace_depth'):
            budget.trace_line({'x': ['xx']})
        elif key in ('game_log_utf8_bytes', 'batch_log_utf8_bytes'): budget.begin_game(['xx'])
        elif key in ('game_log_entries', 'batch_log_entries'): budget.begin_game(['x'])
        elif key == 'action_log_growth_reserve':
            budget.begin_game([])
            budget.accept_candidate(SimpleNamespace(log=[]), SimpleNamespace(cards={}, log=['xx']))
        else: budget.check_deadline()


def protocol_run(tmp_path, monkeypatch, *, outcomes=(1, 2), stop=None, fail_writer=False,
                 oracle_fault=None, pre_encode_stop=False):
    from card_data.seed_cards import seed_card_payload
    from scripts import regression_matrix_replay as replay
    from scripts.oracle_corpus_report import collect_corpus
    rows = []
    for name, text in runner.builtin_templates().items():
        inventory = runner._template_inventory(text)
        boards = {key: [dict(deepcopy(seed_card_payload(card)), card_name=seed_card_payload(card)['name'], quantity=count)
                        for card, count in board.items()] for key, board in inventory.items()}
        rows.append(dict(source='builtin', id=None, name=name, classification_status='resolved',
                         archetype='Protocol', **boards))
    corpus = collect_corpus()
    export = runner.make_export(rows, corpus_sha256=runner.digest(corpus))
    pair = sorted(r['name'] for r in rows)[:2]
    oracle = tmp_path / 'oracle.json'
    cards = [dict(value, cached=True, status='structured_effect') for value in corpus.values()]
    if oracle_fault == 'missing': cards.pop()
    oracle.write_text(json.dumps(dict(cards=cards,
        status_unique={'structured_effect': len(cards)},
        status_weighted={'structured_effect': sum(c['copies'] for c in cards)})))
    files = runner.collect_source_manifest(runner.BACKEND)
    binding = dict(schema_version=1, source_base_commit='a' * 40,
                   backend_files=files, backend_sha256=runner.digest(files))
    provenance = dict(controlled_policy_sha256='c' * 64, engine_rules_sha256='e' * 64,
        metric_definitions_sha256='d' * 64, experimental_features={'task2.3': 'f' * 64},
        activation={'protocol_only': True})
    monkeypatch.setattr(runner, 'verify_measurement_partition', lambda *args: deepcopy(provenance))
    # Explicit inert runner/source-boundary doubles, not native activation proof.
    monkeypatch.setattr(runner, 'verify_measurement_callable', lambda *args: None)
    calls, charges = [], []
    def game(one, two, seed, level, ticks, **options):
        calls.append(dict(one=deepcopy(one), two=deepcopy(two), seed=seed, options=options))
        raw = [trace(1, stall=False), trace(2, stall=False)]
        options['budget'].begin_game(raw)
        winner = outcomes[len(calls)-1]
        result = dict(winner=winner, turn=1, ticks=2, log=list(raw),
                      log_hash='0' * 64, timeout=winner is None, starting_player=1)
        if stop: result['stop_reason'] = stop
        if pre_encode_stop:
            oversized = dict(result, log=['x' * (RESOURCE_LIMITS['result_json_bytes'] + 1)])
            options['record_game'].before_encode(oversized, raw)
        replay._record_game_evidence(result, raw, options['record_game'])
        return result
    monkeypatch.setattr(replay, 'run_game', game)
    def charge(path, count):
        assert not path.exists(), 'external charger must precede output creation'
        if fail_writer and path.name == 'game-02.json': raise OSError('inert writer failure')
        charges.append((path, count))
    result = required(runner, 'run_fixed_game_measurement')(export, [7], selected_pair=pair,
        selected_token=7, difficulty='master', max_ticks=2, limits=dict(RESOURCE_LIMITS),
        private_directory=tmp_path/'measurement', source_binding=binding,
        partition={'arm': 'protocol'}, partition_sha256='0' * 64, activation_check=None,
        artifact_guard=charge, oracle_path=oracle, log_priors_path=runner.BACKEND/'ai/data/log_priors.json')
    return result, calls, charges, pair


def test_fixed_producer_plays_two_independent_mirrors_and_shares_budget(tmp_path, monkeypatch):
    result, calls, charges, pair = protocol_run(tmp_path, monkeypatch)
    assert len(calls) == 2 and calls[0]['seed'] == calls[1]['seed']
    assert calls[0]['one'] == calls[1]['two'] and calls[0]['two'] == calls[1]['one']
    assert calls[0]['options']['budget'] is calls[1]['options']['budget']
    assert [c['options']['starting_player'] for c in calls] == [1, 1]
    production = result['production']
    assert production['complete'] and production['not_run_games'] == 0
    assert [(row['deck_a'], row['deck_b']) for row in production['rows']] == [tuple(pair), tuple(reversed(pair))]
    assert result['package']['eligible'] is True
    assert all(path.stat().st_size == count for path, count in charges)
    assert {p.name for p, _ in charges} == {p.name for p in (tmp_path/'measurement').iterdir()}


@pytest.mark.parametrize('kind', ['draw', 'resource', 'writer'])
def test_incomplete_draw_and_writer_stops_never_become_timeouts_or_retry(tmp_path, monkeypatch, kind):
    result, calls, charges, pair = protocol_run(tmp_path, monkeypatch,
        outcomes=(0, 2) if kind == 'draw' else (None, 2) if kind == 'resource' else (1, 2),
        stop='resource_limit' if kind == 'resource' else None, fail_writer=kind == 'writer')
    assert result['production']['complete'] is False and result['package']['eligible'] is False
    assert len(calls) == (2 if kind == 'writer' else 1)
    assert all(row['status'] != 'timeout' for row in result['production']['games'])
    assert result['production']['legacy_totals']['timeouts'] == 0


def test_incomplete_full_oracle_corpus_rejects_before_any_probe(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='corpus'):
        protocol_run(tmp_path, monkeypatch, oracle_fault='missing')
    assert not (tmp_path/'measurement').exists()


def test_pre_encoding_resource_stop_retains_actual_status(tmp_path, monkeypatch):
    result, calls, charges, pair = protocol_run(tmp_path, monkeypatch, pre_encode_stop=True)
    assert len(calls) == 1 and result['production']['complete'] is False
    assert result['production']['games'][0]['status'] == 'resource_limit'
    assert result['package']['eligible'] is False


def test_runtime_identity_observes_actual_qualified_prefix_without_writes():
    import hashlib
    import sys
    from pathlib import Path
    identity = required(runner, 'measurement_runtime_identity')()
    assert identity['files'] > 0 and identity['symlinks'] >= 0
    assert identity['directories_including_root'] > 0
    assert len(identity['sha256']) == len(identity['python_executable_sha256']) == 64
    assert identity['python_executable_sha256'] == hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()


def test_configuration_is_part_of_the_controlled_remainder(tmp_path, monkeypatch):
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    result = required(runner, 'verify_measurement_partition')(
        binding, backend, partition, runner.digest(partition), {'mode': 'protocol'}, control)
    assert result['controlled_policy_sha256'] == runner.digest(dict(
        files=partition['controlled_files'], configuration={'mode': 'protocol'}))


def test_source_bound_control_rejects_forged_code_even_with_correct_path_and_globals(tmp_path, monkeypatch):
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    control.__code__ = control.__code__.replace(co_name='forged')
    with pytest.raises(ValueError):
        required(runner, 'verify_measurement_partition')(
            binding, backend, partition, runner.digest(partition), {'mode': 'protocol'}, control)


def test_metric_or_producer_code_cannot_be_declared_an_ai_experiment(tmp_path, monkeypatch):
    backend, binding, partition, control = partition_fixture(tmp_path, monkeypatch)
    (backend/'scripts').mkdir()
    (backend/'scripts/report.py').write_bytes((backend/'ai/policy.py').read_bytes())
    reference_hash = partition['controlled_files']['ai/policy.py']
    binding['backend_files'] = runner.collect_source_manifest(backend)
    binding['backend_sha256'] = runner.digest(binding['backend_files'])
    partition['controlled_files'] = dict(binding['backend_files'])
    partition['controlled_files']['scripts/report.py'] = reference_hash
    partition['features']['task2.3'][0]['path'] = 'scripts/report.py'
    with pytest.raises(ValueError, match='policy'):
        required(runner, 'verify_measurement_partition')(
            binding, backend, partition, runner.digest(partition), {'mode': 'protocol'}, control)
