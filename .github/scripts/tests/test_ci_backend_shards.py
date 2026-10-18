"""Authored stdlib protocol controls; no project/private input or real subprocess."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_backend_shards.py'
BINDING = {'run_id': '17', 'attempt': '2', 'commit': 'a' * 40,
           'archive_sha256': 'b' * 64, 'lock_sha256': 'c' * 64}
CONTEXT = {'rootdir': 'backend', 'config': None, 'importmode': 'prepend',
           'plugins': ['ci_backend_evidence', 'ci_backend_snapshot_cleanup',
                       'ci_backend_storage', 'ci_backend_shards']}
VERSIONS = {
    'annotated-doc': '0.0.5', 'annotated-types': '0.8.0', 'anyio': '4.15.1',
    'certifi': '2026.7.22', 'click': '8.5.0', 'fastapi': '0.142.2',
    'greenlet': '3.5.6', 'h11': '0.16.0', 'httpcore': '1.0.9', 'httpx': '0.27.2',
    'idna': '3.20', 'iniconfig': '2.3.1', 'opentelemetry-api': '1.45.1',
    'packaging': '26.3', 'pluggy': '1.6.0', 'pydantic-core': '2.23.4',
    'pydantic': '2.9.2', 'pygments': '2.21.0', 'pytest': '9.0.3',
    'python-multipart': '0.0.31', 'rapidfuzz': '3.9.7', 'sniffio': '1.3.1',
    'sqlalchemy': '2.0.54', 'sqlmodel': '0.0.22', 'starlette': '1.3.1',
    'typing-extensions': '4.16.0', 'typing-inspection': '0.4.4', 'uvicorn': '0.30.6',
}
RUNTIME = {'implementation': 'CPython', 'python': '3.12.3', 'system': 'Linux',
           'machine': 'x86_64', 'libc': ['glibc', '2.39'], 'packages': VERSIONS}
MODULES = ['backend/audit/body-goldens/test_outside.py'] + [
    'backend/tests/test_' + name + '.py' for name in 'abcd']
ITEMS = [{'path': path, 'nodeid': path.removeprefix('backend/') + '::test_one'}
         for path in MODULES]


def observation():
    return {'mode': 'reference', 'context': deepcopy(CONTEXT), 'items': deepcopy(ITEMS),
            'discovered': [x['nodeid'] for x in ITEMS], 'deselections': [],
            'collection_errors': [], 'session_finished': True, 'pytest_exit': 0}


def metadata(nodes):
    return {'schema_version': 1, 'source_commit': BINDING['commit'], 'pytest_exit_code': 0,
            'coverage': {'all_collected_completed': True, 'ci_success_consistent': True,
                         'collected_count': len(nodes), 'unique_count': len(nodes),
                         'phase_counts': {'setup/passed': len(nodes), 'call/passed': len(nodes),
                                          'teardown/passed': len(nodes)},
                         'missing_phases': [], 'duplicate_phases': [], 'unexpected_node_sha256': []},
            'collected_node_sha256': list(nodes), 'discovered_node_sha256': list(nodes),
            'deselected_node_sha256': [], 'deselection_row_count': 0,
            'phases': [{'nodeid_sha256': node, 'phase': phase, 'outcome': 'passed',
                        'xfail_marker': False} for node in nodes
                       for phase in ('setup', 'call', 'teardown')],
            'subtests': [], 'failures': [], 'collection_errors': [],
            'sessions': [{'event': 'start'}, {'event': 'finish', 'exitstatus': 0}],
            'unresolved_failure_count': 0, 'rows_exported': True,
            'skips_and_xfails_are_not_passes': True, 'metadata_error_codes': []}


class ShardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise AssertionError('Required shard capability is not implemented')
        spec = importlib.util.spec_from_file_location('shard_contract_subject', SCRIPT)
        cls.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.subject)

    def plan(self):
        return self.subject.make_plan(observation(), deepcopy(BINDING), deepcopy(RUNTIME), MODULES)

    def workers(self, plan):
        return [self.subject.worker_envelope(
            plan, index, metadata([node for module in plan['modules'] if module['shard'] == index
                                   for node in module['node_sha256']]),
            {'runner': 0, 'metadata': 0}, deepcopy(RUNTIME)) for index in range(4)]

    def rejected(self, function, *args):
        with self.assertRaises(self.subject.ContractError):
            function(*args)

    def test_reference_kind_has_no_execution_success_or_phase_claim(self):
        plan = self.plan()
        self.assertEqual(plan['kind'], 'collect-only-reference')
        self.assertNotIn('ci_success_consistent', plan)
        self.assertNotIn('phases', plan)

    def test_outside_tests_module_is_preserved_and_round_robin_is_deterministic(self):
        plan = self.plan()
        self.assertEqual([m['path'] for m in plan['modules']], MODULES)
        self.assertEqual([m['shard'] for m in plan['modules']], [0, 1, 2, 3, 0])
        self.assertEqual(plan, self.plan())

    def test_full_parameter_identity_is_hashed_without_public_parameter_bytes(self):
        obs = observation()
        obs['items'][0]['nodeid'] += '[PRIVATE_SENTINEL]'
        obs['discovered'][0] = obs['items'][0]['nodeid']
        plan = self.subject.make_plan(obs, BINDING, RUNTIME, MODULES)
        digest = hashlib.sha256(obs['items'][0]['nodeid'].encode()).hexdigest()
        self.assertEqual(plan['modules'][0]['node_sha256'], [digest])
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(plan))

    def test_foreign_or_traversing_or_uncommitted_module_is_rejected(self):
        for path in ('../test_x.py', '/tmp/test_x.py', 'backend/tests/../test_x.py',
                     'backend/tests/test_uncommitted.py'):
            obs = observation(); obs['items'][0]['path'] = path
            self.rejected(self.subject.make_plan, obs, BINDING, RUNTIME, MODULES)

    def test_reference_duplicates_discovery_drift_errors_and_deselection_reject(self):
        for key, value in [('discovered', []), ('collection_errors', ['x']),
                           ('deselections', [[]]), ('session_finished', False), ('pytest_exit', 1)]:
            obs = observation(); obs[key] = value
            self.rejected(self.subject.make_plan, obs, BINDING, RUNTIME, MODULES)
        obs = observation(); obs['items'].append(deepcopy(obs['items'][0]))
        self.rejected(self.subject.make_plan, obs, BINDING, RUNTIME, MODULES)

    def test_context_and_all_binding_fields_are_required_not_optional(self):
        for key in BINDING:
            binding = deepcopy(BINDING); del binding[key]
            self.rejected(self.subject.make_plan, observation(), binding, RUNTIME, MODULES)
        for key in CONTEXT:
            obs = observation(); del obs['context'][key]
            self.rejected(self.subject.make_plan, obs, BINDING, RUNTIME, MODULES)

    def test_python_platform_and_complete_application_closure_are_admitted(self):
        self.subject.validate_runtime(deepcopy(RUNTIME), VERSIONS)
        for key, value in [('python', '3.12.4'), ('machine', 'aarch64'),
                           ('libc', ['glibc', '2.40']), ('system', 'Darwin')]:
            runtime = deepcopy(RUNTIME); runtime[key] = value
            self.rejected(self.subject.validate_runtime, runtime, VERSIONS)

    def test_missing_extra_and_changed_packages_cannot_claim_runtime_equality(self):
        for operation in ('missing', 'extra', 'changed'):
            runtime = deepcopy(RUNTIME)
            if operation == 'missing': del runtime['packages']['pytest']
            elif operation == 'extra': runtime['packages']['pip'] = 'unknown'
            else: runtime['packages']['pytest'] = '8.3.0'
            self.rejected(self.subject.validate_runtime, runtime, VERSIONS)

    def test_four_actual_worker_sessions_join_without_counterfeit_single_session(self):
        plan = self.plan(); result = self.subject.join(plan, self.workers(plan),
                                                     {'reference': 'success', 'workers': 'success'})
        self.assertEqual(result['kind'], 'four-serial-shards')
        self.assertEqual(len(result['workers']), 4)
        self.assertNotIn('pytest_exit_code', result)

    def test_reporter_zero_describing_failed_pytest_is_never_accepted(self):
        plan = self.plan(); nodes = [x for m in plan['modules'] if m['shard'] == 0 for x in m['node_sha256']]
        meta = metadata(nodes); meta['pytest_exit_code'] = 1
        meta['coverage']['ci_success_consistent'] = False
        self.rejected(self.subject.worker_envelope, plan, 0, meta,
                      {'runner': 1, 'metadata': 0}, RUNTIME)

    def test_failed_prerequisite_or_worker_job_cannot_be_hidden_by_good_artifacts(self):
        plan = self.plan()
        for role in ('reference', 'workers'):
            for state in ('failure', 'cancelled', 'skipped', ''):
                jobs = {'reference': 'success', 'workers': 'success'}; jobs[role] = state
                self.rejected(self.subject.join, plan, self.workers(plan), jobs)

    def test_missing_duplicate_wrong_shard_and_replayed_attempt_are_rejected(self):
        plan = self.plan(); workers = self.workers(plan); jobs = {'reference': 'success', 'workers': 'success'}
        self.rejected(self.subject.join, plan, workers[:3], jobs)
        self.rejected(self.subject.join, plan, [workers[0]] * 4, jobs)
        for key, value in [('shard', True), ('plan_sha256', 'd' * 64)]:
            altered = deepcopy(workers); altered[0][key] = value
            self.rejected(self.subject.join, plan, altered, jobs)
        altered = deepcopy(workers); altered[0]['binding']['attempt'] = '1'
        self.rejected(self.subject.join, plan, altered, jobs)

    def test_assigned_nodes_and_global_union_require_identities_not_equal_counts(self):
        plan = self.plan(); workers = self.workers(plan)
        workers[0]['metadata']['collected_node_sha256'][0] = 'f' * 64
        self.rejected(self.subject.join, plan, workers, {'reference': 'success', 'workers': 'success'})

    def test_worker_order_drift_is_not_silently_sorted_away(self):
        plan = self.plan(); workers = self.workers(plan)
        workers[0]['metadata']['collected_node_sha256'].reverse()
        self.rejected(self.subject.join, plan, workers, {'reference': 'success', 'workers': 'success'})

    def test_missing_or_duplicate_phase_and_incomplete_session_remain_failures(self):
        plan = self.plan(); workers = self.workers(plan)
        for mutation in ('missing', 'duplicate', 'finish'):
            altered = deepcopy(workers)
            if mutation == 'missing': altered[0]['metadata']['phases'].pop()
            elif mutation == 'duplicate': altered[0]['metadata']['phases'].append(deepcopy(altered[0]['metadata']['phases'][0]))
            else: altered[0]['metadata']['sessions'].pop()
            self.rejected(self.subject.join, plan, altered, {'reference': 'success', 'workers': 'success'})

    def test_subreport_occurrences_remain_distinct_and_failed_subreport_vetoes(self):
        plan = self.plan(); workers = self.workers(plan)
        node = workers[0]['metadata']['collected_node_sha256'][0]
        rows = [{'nodeid_sha256': node, 'subtest_index': i, 'phase': 'call',
                 'outcome': 'passed', 'xfail_marker': False, 'duration_seconds': 0.1} for i in range(2)]
        workers[0]['metadata']['subtests'] = rows
        result = self.subject.join(plan, workers, {'reference': 'success', 'workers': 'success'})
        self.assertEqual(result['workers'][0]['metadata']['subtests'], rows)
        workers[0]['metadata']['subtests'][1]['outcome'] = 'failed'
        self.rejected(self.subject.join, plan, workers, {'reference': 'success', 'workers': 'success'})

    def test_unknown_private_fields_and_boolean_numeric_aliases_fail_closed(self):
        plan = self.plan(); workers = self.workers(plan)
        for mutation in ('unknown', 'bool_exit', 'bad_count'):
            altered = deepcopy(workers)
            if mutation == 'unknown': altered[0]['PRIVATE_SENTINEL'] = {'raw': 'secret'}
            elif mutation == 'bool_exit': altered[0]['exits']['runner'] = False
            else: altered[0]['metadata']['coverage']['collected_count'] = True
            self.rejected(self.subject.join, plan, altered, {'reference': 'success', 'workers': 'success'})

    def test_reference_cannot_be_submitted_as_a_worker_envelope(self):
        plan = self.plan()
        self.rejected(self.subject.join, plan, [plan] * 4, {'reference': 'success', 'workers': 'success'})

    def test_absolute_deadline_has_no_per_step_reset_or_nonfinite_admission(self):
        self.assertEqual(self.subject.remaining_seconds(19800.0, 19790.0), 10.0)
        for deadline, now in [(19800.0, 19800.0), (19800.0, 19801.0),
                              (float('inf'), 1.0), (True, 1.0), (19800.0, float('nan'))]:
            self.rejected(self.subject.remaining_seconds, deadline, now)

    def test_deadline_watcher_uses_only_exact_registered_group_and_two_signals(self):
        expected = {'pid': 101, 'parent': 100, 'start': 12345, 'pgrp': 101, 'session': 101}
        clock = [9.0]; signals = []
        def pause(seconds): clock[0] += seconds
        def send(group, kind): signals.append((group, kind, clock[0]))
        result = self.subject.watch_deadline(expected, 10.0, lambda: deepcopy(expected),
                                             lambda: clock[0], pause, send)
        self.assertEqual([(group, kind) for group, kind, _ in signals], [(101, 'INT'), (101, 'KILL')])
        self.assertGreaterEqual(signals[0][2], 10.0)
        self.assertGreaterEqual(signals[1][2], 25.0)
        self.assertLessEqual(clock[0], 27.3)
        self.assertEqual(result['status'], 'UNKNOWN_UNREAPED')
        self.assertNotIn('actual_wait', result)

    def test_deadline_watcher_rechecks_incarnation_before_later_kill(self):
        expected = {'pid': 101, 'parent': 100, 'start': 12345, 'pgrp': 101, 'session': 101}
        clock = [10.0]; signals = []
        def probe():
            result = deepcopy(expected)
            if signals: result['start'] += 1
            return result
        def pause(seconds): clock[0] += seconds
        result = self.subject.watch_deadline(expected, 10.0, probe,
            lambda: clock[0], pause, lambda group, kind: signals.append((group, kind)))
        self.assertEqual(signals, [(101, 'INT')])
        self.assertEqual(result['status'], 'UNKNOWN_IDENTITY')

    def test_deadline_watcher_does_not_signal_unbound_or_already_absent_group(self):
        expected = {'pid': 101, 'parent': 100, 'start': 12345, 'pgrp': 101, 'session': 101}
        for actual in [None, dict(expected, pgrp=999), dict(expected, pid=True)]:
            signals = []
            self.subject.watch_deadline(expected, 10.0, lambda: actual, lambda: 10.0,
                lambda seconds: self.fail('Unexpected wait'),
                lambda group, kind: signals.append((group, kind)))
            self.assertEqual(signals, [])


if __name__ == '__main__':
    unittest.main()
