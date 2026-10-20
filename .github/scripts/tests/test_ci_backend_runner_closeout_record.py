"""Actual owned Bash writer controls, reusing the unchanged public fixture."""
import importlib.util
import json
from pathlib import Path
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'runner_closeout_record_donor', SCRIPTS / 'tests/test_backend_ci_closeout.py')
donor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(donor)


class RunnerCloseoutRecordTests(unittest.TestCase):
    def setUp(self):
        self.control = donor.DiagnosticCloseoutTests('runTest')
        self.addCleanup(self.control.doCleanups)
        self.control.setUp()

    def assert_record(self, actual_exit, evidence, **changes):
        path = evidence / 'runner-closeout.json'
        self.assertFalse(path.is_symlink())
        self.assertTrue(path.is_file(), 'Actual Bash runner must write its status record')
        with path.open('rb') as stream:
            raw = stream.read(4097)
        self.assertLessEqual(len(raw), 4096)
        # Fresh parent-owned evidence survives fixture cleanup when configured.
        target = self.control.ledger_root / (self._testMethodName + '-runner-closeout.json')
        with target.open('xb') as stream:
            stream.write(raw)
        value = json.loads(raw)
        expected = dict(
            schema_version=1, work_exit_stage='AUDIT', entry_exit_code=0,
            final_exit_code=0, pytest_exit_code=0, evidence_exit_code=0,
            audit_exit_code=0, pressure_exit_code=0, sink_exit_code=0,
            watcher_exit_code=None, diagnostic_failed=False,
            group_after_wait_quiet=None, group_final_quiet=None,
            trap_changed_exit=False, closeout_complete=False)
        expected.update(changes)
        self.assertEqual(value, expected)
        self.assertIs(type(value['schema_version']), int)
        for key in ('entry_exit_code', 'final_exit_code', 'pytest_exit_code',
                    'evidence_exit_code', 'audit_exit_code', 'pressure_exit_code',
                    'sink_exit_code'):
            self.assertIs(type(value[key]), int)
        for key in ('diagnostic_failed', 'trap_changed_exit', 'closeout_complete'):
            self.assertIs(type(value[key]), bool)
        self.assertEqual(value['final_exit_code'], actual_exit)
        self.assertNotIn(donor.privacy.SENTINEL, raw.decode('utf-8'))
        for forbidden in ('pid', 'argv', 'runner.log', 'pytest.log'):
            self.assertNotIn(forbidden, raw.decode('utf-8'))
        spec = importlib.util.spec_from_file_location(
            'actual_runner_closeout_projector', SCRIPTS / 'ci_backend_metadata.py')
        reporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reporter)
        projected = reporter.closeout_fields(evidence, expected['pytest_exit_code'])
        self.assertEqual(projected, {'runner_closeout': {
            'schema_version': 1, 'status': 'partial', 'runner': expected,
            'diagnostics': [dict(role=role, finished=True, forced=False,
                                 wait_exit_code=expected['pressure_exit_code']
                                 if role == 'pressure' else 0)
                            for role in ('pressure', 'sink', 'sampler', 'logger')]}})

    def test_actual_natural_writer_serializes_observed_codes_and_unknown_legacy_fields(self):
        code, evidence = self.control.run_control()
        self.assertEqual(code, 0)
        self.assert_record(code, evidence)

    def test_actual_pressure_failure_is_distinct_from_true_pytest_zero(self):
        code, evidence = self.control.run_control(diagnostic_status=23)
        self.assertEqual(code, 2)
        self.assert_record(code, evidence, work_exit_stage='CONTROL',
                           entry_exit_code=2, final_exit_code=2,
                           pressure_exit_code=23, diagnostic_failed=True)

    def test_actual_pressure_failure_preserves_pytest_failure_priority(self):
        code, evidence = self.control.run_control(pytest_status=1, diagnostic_status=23)
        self.assertEqual(code, 1)
        self.assert_record(code, evidence, work_exit_stage='PYTEST',
                           entry_exit_code=1, final_exit_code=1, pytest_exit_code=1,
                           pressure_exit_code=23, diagnostic_failed=True)


if __name__ == '__main__':
    unittest.main()
