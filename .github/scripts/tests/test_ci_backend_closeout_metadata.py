"""Public synthetic closeout observations only; no shell/child/backend execution."""
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
COMMIT = '1' * 40  # Explicit protocol identity, not an observed CI head.
SECRET = 'PUBLIC_SYNTHETIC_PRIVATE_LIKE_SENTINEL'
NODE = 'tests/test_public.py::test_protocol[' + SECRET + ']'
DEGRADED = {'runner_closeout': {'schema_version': 1, 'status': 'degraded',
                               'runner': None, 'diagnostics': []}}


def load_module(name):
    spec = importlib.util.spec_from_file_location('protocol_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner_record(**changes):
    value = dict(schema_version=1, work_exit_stage='AUDIT',
                 entry_exit_code=0, final_exit_code=0, pytest_exit_code=0,
                 evidence_exit_code=0, audit_exit_code=0, pressure_exit_code=0,
                 sink_exit_code=0, watcher_exit_code=0, diagnostic_failed=False,
                 group_after_wait_quiet=True, group_final_quiet=True,
                 trap_changed_exit=False, closeout_complete=True)
    value.update(changes)
    return value


class CloseoutMetadataTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='ci-closeout-public-protocol-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.reporter = load_module('ci_backend_metadata')

    def write(self, name, value):
        (self.evidence / name).write_text(value, encoding='utf-8')

    def record(self, **changes):
        value = runner_record(**changes)
        self.write('runner-closeout.json', json.dumps(value))
        return value

    def project(self, pytest_exit_code=0):
        function = getattr(self.reporter, 'closeout_fields', None)
        self.assertTrue(callable(function), 'Missing optional finite closeout projector')
        result = function(self.evidence, pytest_exit_code)
        text = json.dumps(result, sort_keys=True)
        self.assertNotIn(SECRET, text)
        return result

    def export(self):
        self.write('source-head.txt', COMMIT + '\n')
        self.write('pytest-exit-code.txt', '0\n')
        self.write('collected.json', json.dumps({'nodeids': [NODE]}))
        self.write('discovered.jsonl', json.dumps({'nodeid': NODE}) + '\n')
        phases = [dict(nodeid=NODE, phase=phase, outcome='passed', duration_seconds=0.0)
                  for phase in ('setup', 'call', 'teardown')]
        self.write('phases.jsonl', ''.join(json.dumps(row) + '\n' for row in phases))
        self.write('session.jsonl', json.dumps({'event': 'start'}) + '\n'
                   + json.dumps({'event': 'finish', 'exitstatus': 0}) + '\n')
        audit = dict(all_collected_completed=True, ci_success_consistent=True,
                     collected_count=1, unique_count=1,
                     phase_counts={'setup/passed': 1, 'call/passed': 1, 'teardown/passed': 1},
                     missing_phases=[], duplicate_phases=[], unexpected_nodes=[])
        self.write('coverage.json', json.dumps(audit))
        for name in ('pytest.log', 'runner.log', 'disk-samples.log'):
            self.write(name, SECRET)
        original_open = io.open

        def safe_open(path, *args, **kwargs):
            self.assertNotIn(Path(path).name, ('pytest.log', 'runner.log', 'disk-samples.log'),
                             'Raw log access is not diagnostic metadata projection')
            return original_open(path, *args, **kwargs)

        with ExitStack() as stack:
            stack.enter_context(patch.object(self.reporter, 'git', return_value=COMMIT + '\n'))
            stack.enter_context(patch.object(self.reporter, 'PublicDefinitions',
                                              return_value=SimpleNamespace(resolve=lambda node: None)))
            stack.enter_context(patch.object(self.reporter, 'audit_evidence', return_value=(audit, 0)))
            stack.enter_context(patch.object(self.reporter, 'runtime_version_fields', return_value={}))
            stack.enter_context(patch('io.open', side_effect=safe_open))
            document, status = self.reporter.build_metadata(self.evidence, self.source)
        self.assertEqual(status, 0)
        self.assertEqual(document['pytest_exit_code'], 0)
        self.assertEqual(document['source_commit'], COMMIT)
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertEqual(document['metadata_error_codes'], [])
        self.assertEqual(document['failures'], [])
        self.assertNotIn(SECRET, json.dumps(document, sort_keys=True))
        return document

    def test_absent_optional_observations_preserve_legacy_core(self):
        document = self.export()
        self.assertNotIn('runner_closeout', document)
        self.assertEqual(document['coverage']['phase_counts'],
                         {'setup/passed': 1, 'call/passed': 1, 'teardown/passed': 1})

    def test_existing_tsv_projects_finite_roles_without_pid_or_unknown_text(self):
        self.write('diagnostic-closeout.tsv', 'pressure\t1234567\t1\t0\t0\n'
                   'sink\t1234568\t1\t1\t143\nlogger\t1234569\t0\t0\tUNKNOWN\n')
        expected = {'runner_closeout': {'schema_version': 1, 'status': 'partial', 'runner': None,
            'diagnostics': [dict(role='pressure', finished=True, forced=False, wait_exit_code=0),
                            dict(role='sink', finished=True, forced=True, wait_exit_code=143),
                            dict(role='logger', finished=False, forced=False, wait_exit_code=None)]}}
        self.assertEqual(self.project(), expected)
        self.assertNotIn('123456', json.dumps(expected))

    def test_complete_projection_distinguishes_pytest_zero_from_control_exits(self):
        cases = [dict(work_exit_stage='SINK', entry_exit_code=2, final_exit_code=2, sink_exit_code=2),
                 dict(work_exit_stage='CONTROL', entry_exit_code=2, final_exit_code=2,
                      pressure_exit_code=2, diagnostic_failed=True),
                 dict(work_exit_stage='CONTROL', entry_exit_code=2, final_exit_code=2,
                      watcher_exit_code=2, diagnostic_failed=True),
                 dict(work_exit_stage='AUDIT', entry_exit_code=2, final_exit_code=2, audit_exit_code=2),
                 dict(work_exit_stage='EVIDENCE', entry_exit_code=2, final_exit_code=2,
                      evidence_exit_code=2, group_after_wait_quiet=False),
                 dict(work_exit_stage='AUDIT', entry_exit_code=0, final_exit_code=2,
                      trap_changed_exit=True, diagnostic_failed=True, group_final_quiet=False)]
        self.write('diagnostic-closeout.tsv', 'logger\t123\t1\t0\t0\n')
        for fields in cases:
            with self.subTest(fields=fields):
                recorded = self.record(**fields)
                document = self.export()
                self.assertIn('runner_closeout', document, 'Actual exporter must wire the optional projector')
                self.assertEqual(document['runner_closeout'], {
                    'schema_version': 1, 'status': 'complete', 'runner': recorded,
                    'diagnostics': [dict(role='logger', finished=True, forced=False, wait_exit_code=0)]})
                self.assertEqual(document['runner_closeout']['runner']['final_exit_code'], 2)
                self.assertEqual(document['pytest_exit_code'], 0)
        self.record(watcher_exit_code=None, audit_exit_code=None, group_final_quiet=None,
                    closeout_complete=False)
        partial_document = self.export()
        self.assertIn('runner_closeout', partial_document)
        partial = partial_document['runner_closeout']
        self.assertEqual(partial['status'], 'partial')
        self.assertIsNone(partial['runner']['watcher_exit_code'])
        self.assertIsNone(partial['runner']['group_final_quiet'])

    def test_invalid_tsv_rejects_whole_optional_projection_without_echo(self):
        rows = [SECRET + '\t123\t1\t0\t0\n',
                'logger\t' + SECRET + '\t1\t0\t0\n',
                'logger\t123\ttrue\t0\t0\n', 'logger\t123\t1\t0\t256\n',
                'logger\t123\t1\t0\t0\t' + SECRET + '\n',
                'logger\t123\t1\t0\tUNKNOWN\n', 'logger\t123\t0\t0\t0\n']
        for value in rows:
            with self.subTest(value=value):
                self.write('diagnostic-closeout.tsv', value)
                self.assertEqual(self.project(), DEGRADED)

    def test_summary_types_unknown_fields_and_correlation_are_strict(self):
        cases = [dict(schema_version=True), dict(final_exit_code=True),
                 dict(group_final_quiet=0), dict(work_exit_stage=SECRET),
                 dict(argv=SECRET), dict(pytest_exit_code=1)]
        for fields in cases:
            with self.subTest(fields=fields):
                self.record(**fields)
                self.assertEqual(self.project(), DEGRADED)
        self.write('runner-closeout.json', '{"schema_version":1,"schema_version":1}')
        self.assertEqual(self.project(), DEGRADED)

    def test_optional_input_sizes_and_row_counts_are_bounded(self):
        cases = [('diagnostic-closeout.tsv', 'logger\t123\t1\t0\t0\n' * 33),
                 ('diagnostic-closeout.tsv', 'x' * 16385),
                 ('runner-closeout.json', 'x' * 4097)]
        for name, text in cases:
            with self.subTest(name=name, size=len(text)):
                for other in ('diagnostic-closeout.tsv', 'runner-closeout.json'):
                    (self.evidence / other).unlink(missing_ok=True)
                self.write(name, text)
                self.assertEqual(self.project(), DEGRADED)

    def test_symlinked_optional_input_is_rejected_without_reading_payload(self):
        foreign = self.root / 'not-evidence.json'
        foreign.write_text(SECRET)
        target = self.evidence / 'runner-closeout.json'
        target.symlink_to(foreign)
        original_open = io.open

        def no_follow(path, *args, **kwargs):
            self.assertNotIn(Path(path), (target, foreign), 'Unsafe path was opened before rejection')
            return original_open(path, *args, **kwargs)

        with patch('io.open', side_effect=no_follow):
            self.assertEqual(self.project(), DEGRADED)

    def test_strict_public_readers_accept_only_typed_additive_metadata(self):
        reader = load_module('ci_backend_shards')
        document = self.export()
        self.assertEqual(reader.metadata_check(document, [hashlib.sha256(NODE.encode()).hexdigest()], COMMIT)
                         ['pytest_exit_code'], 0)
        safe = {'schema_version': 1, 'status': 'partial', 'runner': None, 'diagnostics': []}
        document['runner_closeout'] = safe
        path = self.root / 'backend-metadata.json'
        path.write_text(json.dumps(document))
        try:
            reader.bound_diagnostic_file(path)
            admitted = reader.metadata_check(document, [hashlib.sha256(NODE.encode()).hexdigest()], COMMIT)
        except reader.ContractError:
            self.fail('Missing strict admission for the finite optional closeout projection')
        self.assertNotIn('runner_closeout', admitted, 'Local diagnostics must not alter the canonical core')
        for bad in ({**safe, 'argv': SECRET}, {**safe, 'schema_version': True},
                    {**safe, 'status': SECRET}, {**safe, 'diagnostics': [dict(role=SECRET)]},
                    {**safe, 'status': 'complete'},
                    {**safe, 'diagnostics': [dict(role='logger', finished=True,
                                                forced=False, wait_exit_code=True)]}):
            with self.subTest(bad=bad):
                document['runner_closeout'] = bad
                path.write_text(json.dumps(document))
                with self.assertRaises(reader.ContractError):
                    reader.bound_diagnostic_file(path)
                with self.assertRaises(reader.ContractError):
                    reader.metadata_check(document, [hashlib.sha256(NODE.encode()).hexdigest()], COMMIT)
        document['runner_closeout'] = safe
        document['pytest_exit_code'] = 1
        with self.assertRaises(reader.ContractError):
            reader.metadata_check(document, [hashlib.sha256(NODE.encode()).hexdigest()], COMMIT)

    def test_runner_wires_fixed_record_after_logger_without_changing_exit_priority(self):
        text = (SCRIPTS / 'run-backend-ci.sh').read_text()
        self.assertRegex(text, r'(?m)^write_runner_closeout\(\) \{')
        self.assertIn('runner-closeout.json', text)
        cleanup = re.search(r'(?ms)^cleanup_owned\(\) \{\n(.*?)^\}', text)
        self.assertIsNotNone(cleanup)
        body = cleanup.group(1)
        call = body.index('write_runner_closeout')
        self.assertLess(body.index('close_diagnostic logger'), call)
        self.assertLess(call, body.index('exit "$status"'))
        self.assertIn('if ((status == 0 && (diagnostic_status != 0 || diagnostic_failed != 0))); then status=2; fi', body)
        self.assertIn('if ((statuses[0] != 0)); then exit "${statuses[0]}"; fi', text)
        self.assertIn('if ((statuses[1] != 0)); then exit "${statuses[1]}"; fi', text)


if __name__ == '__main__':
    unittest.main()
