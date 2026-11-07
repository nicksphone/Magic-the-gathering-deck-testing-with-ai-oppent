"""Pure synthetic failed-reference projection; no child, backend or private input."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
COMMIT = '1' * 40  # Synthetic protocol identity, not a CI observation.
PRIVATE = 'SYNTHETIC_PRIVATE_REFERENCE_PAYLOAD_19b7'
MODULE = 'backend/tests/test_public.py'
NODE = 'tests/test_public.py::test_example[' + PRIVATE + ']'


def load(name):
    spec = importlib.util.spec_from_file_location('reference_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReferenceFailureMetadataTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='reference-public-protocol-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.reporter = load('ci_backend_metadata')
        self.git_calls = []

    def write(self, name, value):
        (self.evidence / name).write_text(value, encoding='utf-8')

    def rows(self, name, values):
        self.write(name, ''.join(json.dumps(value) + '\n' for value in values))

    def ledger(self):
        self.write('source-head.txt', COMMIT + '\n')
        self.write('pytest-exit-code.txt', '2\n')
        self.write('collected.json', json.dumps({'nodeids': [NODE, NODE]}))
        self.rows('discovered.jsonl', [{'nodeid': NODE}, {'nodeid': NODE}])
        self.rows('collection-errors.jsonl', [
            {'nodeid': 'tests/test_public.py', 'exception': PRIVATE, 'message': PRIVATE},
            {'nodeid': 'tests/test_public.py::TestPrivate[' + PRIVATE + ']'},
            {'nodeid': 'scripts/test_public.py'},
            {'nodeid': '/private/' + PRIVATE + '/test_public.py'},
            {'nodeid': 'tests/../tests/test_public.py'},
            {'nodeid': 'tests/test_symlink.py'},
            {'nodeid': 'backend/' + PRIVATE + '.py'},
        ])
        self.rows('session.jsonl', [{'event': 'start', 'private': PRIVATE},
                                    {'event': 'finish', 'exitstatus': 2, 'message': PRIVATE}])
        self.write('runner-closeout.json', json.dumps(dict(
            schema_version=1, work_exit_stage='PYTEST', entry_exit_code=2,
            final_exit_code=2, pytest_exit_code=2, evidence_exit_code=0,
            audit_exit_code=2, pressure_exit_code=0, sink_exit_code=0,
            watcher_exit_code=0, diagnostic_failed=False, group_after_wait_quiet=True,
            group_final_quiet=True, trap_changed_exit=False, closeout_complete=True)))
        self.write('diagnostic-closeout.tsv', 'sink\t12345\t1\t0\t0\n')
        for name in ('runner.log', 'pytest.log', 'failures.jsonl', 'coverage.json',
                     'failure-signatures.jsonl', 'sealed-self-removal-witness.json',
                     'model.pt', '.env'):
            self.write(name, PRIVATE)

    def git(self, source, *args):
        self.assertEqual(source, self.source)
        self.git_calls.append(args)
        if args == ('rev-parse', 'HEAD'):
            return COMMIT + '\n'
        self.assertEqual(args, ('ls-tree', '-rz', COMMIT, '--', 'backend'))
        return ('100644 blob ' + 'a' * 40 + '\t' + MODULE + '\0'
                '100644 blob ' + 'b' * 40 + '\tbackend/scripts/test_public.py\0'
                '120000 blob ' + 'c' * 40 + '\tbackend/tests/test_symlink.py\0')

    def project(self, output_name='backend-metadata.json', forbidden=(), expected_status=0):
        output = self.root / output_name
        original_open = os.open
        forbidden = {self.evidence / name for name in (
            'runner.log', 'pytest.log', 'failures.jsonl', 'coverage.json',
            'failure-signatures.jsonl', 'sealed-self-removal-witness.json', 'model.pt', '.env',
            *forbidden)}
        forbidden.add(self.root / 'private-payload')
        original_io_open = io.open

        def no_raw(path, *args, **kwargs):
            if not isinstance(path, int):
                self.assertNotIn(Path(path), forbidden, 'Forbidden evidence opened')
            return original_io_open(path, *args, **kwargs)

        def no_raw_fd(path, flags, *args, **kwargs):
            if not isinstance(path, int):
                self.assertNotIn(Path(path), forbidden, 'Forbidden evidence opened')
            return original_open(path, flags, *args, **kwargs)

        stream = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.reporter, 'git', side_effect=self.git))
            stack.enter_context(patch.object(self.reporter, 'PublicDefinitions',
                                              side_effect=AssertionError('No test resolver or imports')))
            stack.enter_context(patch.object(self.reporter, 'audit_evidence',
                                              side_effect=AssertionError('No execution coverage audit')))
            stack.enter_context(patch('io.open', side_effect=no_raw))
            stack.enter_context(patch('os.open', side_effect=no_raw_fd))
            stack.enter_context(patch('subprocess.Popen', side_effect=AssertionError('No child')))
            stack.enter_context(redirect_stdout(stream))
            stack.enter_context(redirect_stderr(stream))
            status = self.reporter.main(['collection-failure', str(self.evidence),
                                         str(self.source), str(output)])
        self.assertEqual(status, expected_status)
        self.assertEqual(stream.getvalue(), 'CI_BACKEND_METADATA_' +
                         ('FAILED' if expected_status else 'WRITTEN') + '\n')
        document = json.loads(output.read_text())
        self.assertNotIn(PRIVATE, json.dumps(document))
        self.assertFalse(document['rows_exported'])
        self.assertFalse(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])
        load('ci_backend_shards').bound_diagnostic_file(output)
        return document

    def test_failed_reference_without_coverage_exports_bounded_public_observations(self):
        self.ledger()
        (self.evidence / 'coverage.json').unlink()
        document = self.project()
        self.assertEqual(document['source_commit'], COMMIT)
        self.assertEqual(document['pytest_exit_code'], 2)
        self.assertEqual(document['runner_closeout']['runner']['work_exit_stage'], 'PYTEST')
        self.assertNotIn('12345', json.dumps(document))
        partial = document['partial_diagnostics']
        self.assertEqual(partial['status'], 'available')
        self.assertIs(partial['nonfinal'], True)
        value = partial['collection']
        self.assertEqual(value['discovered_count'], 2)
        self.assertEqual(value['collected_count'], 2)
        self.assertEqual(value['collection_error_count'], 7)
        self.assertEqual(value['exported_error_count'], 7)
        self.assertEqual(value['omitted_error_count'], 0)
        self.assertEqual(value['unresolved_module_count'], 4)
        self.assertEqual([row['public_module'] for row in value['errors']],
                         [MODULE, MODULE, 'backend/scripts/test_public.py', None, None, None, None])
        for row in value['errors']:
            self.assertEqual(set(row), {'public_module', 'category', 'exception', 'exception_status'})
            self.assertEqual(row['category'], 'collection_report_failed')
            self.assertIsNone(row['exception'])
            self.assertEqual(row['exception_status'], 'not_recorded')
        self.assertEqual(value['sessions'], [{'event': 'start'}, {'event': 'finish', 'exitstatus': 2}])
        self.assertEqual(document['metadata_error_codes'], [])
        self.write('pytest-exit-code.txt', '0\n')
        self.rows('session.jsonl', [{'event': 'start'}, {'event': 'finish', 'exitstatus': 0}])
        closeout = json.loads((self.evidence / 'runner-closeout.json').read_text())
        closeout.update(pytest_exit_code=0, work_exit_stage='AUDIT')
        self.write('runner-closeout.json', json.dumps(closeout))
        (self.root / 'control').mkdir()
        control = self.project('control/backend-metadata.json')
        self.assertEqual(control['pytest_exit_code'], 0)
        self.assertEqual(control['runner_closeout']['runner']['final_exit_code'], 2)
        self.ledger()
        self.rows('collection-errors.jsonl', [{'nodeid': '', 'message': PRIVATE},
                                               {'nodeid': 'tests', 'longrepr': PRIVATE}])
        (self.root / 'opaque').mkdir()
        opaque_document = self.project('opaque/backend-metadata.json')
        opaque = opaque_document['partial_diagnostics']['collection']
        self.assertEqual(opaque_document['runner_closeout']['runner']['pytest_exit_code'], 2)
        self.assertEqual(opaque_document['partial_diagnostics']['status'], 'available')
        self.assertEqual(opaque['collection_error_count'], 2)
        self.assertEqual(opaque['unresolved_module_count'], 2)
        self.assertTrue(all(row['public_module'] is None and row['exception'] is None
                            and row['exception_status'] == 'not_recorded' for row in opaque['errors']))
        self.ledger()
        (self.evidence / 'collection-errors.jsonl').unlink()
        (self.root / 'no-error-ledger').mkdir()
        absent = self.project('no-error-ledger/backend-metadata.json', expected_status=2)['partial_diagnostics']
        self.assertEqual(absent['status'], 'partial')
        self.assertEqual(absent['collection']['collected_count'], 2)
        for name in ('collection_error_count', 'omitted_error_count', 'unresolved_module_count'):
            self.assertIsNone(absent['collection'][name])
        self.ledger()
        self.rows('collection-errors.jsonl', [{'nodeid': 'tests/test_public.py'}] * 65)
        (self.root / 'bounded').mkdir()
        bounded = self.project('bounded/backend-metadata.json')['partial_diagnostics']['collection']
        self.assertEqual((bounded['collection_error_count'], bounded['exported_error_count'],
                          bounded['omitted_error_count']), (65, 64, 1))
        for name in ('collected.json', 'discovered.jsonl', 'collection-errors.jsonl', 'session.jsonl'):
            (self.evidence / name).unlink()
        (self.root / 'missing').mkdir()
        missing = self.project('missing/backend-metadata.json', expected_status=2)['partial_diagnostics']
        self.assertEqual(missing['status'], 'partial')
        self.assertIsNone(missing['collection']['collected_count'])
        self.assertIsNone(missing['collection']['collection_error_count'])
        self.ledger()
        self.write('runner-closeout.json', json.dumps({'private': PRIVATE}))
        (self.root / 'degraded').mkdir()
        degraded = self.project('degraded/backend-metadata.json', expected_status=2)
        self.assertEqual(degraded['runner_closeout']['status'], 'degraded')
        self.assertEqual(degraded['partial_diagnostics']['status'], 'partial')

    def test_invalid_inputs_fail_closed_before_payload_io_and_workflow_stays_failure_only(self):
        cases = [
            ('source-mismatch', 'source-head.txt', '2' * 40 + '\n', 'SOURCE_COMMIT_MISMATCH'),
            ('malformed', 'collection-errors.jsonl', '{' + PRIVATE + '\n', 'EVIDENCE_JSON_INVALID'),
            ('duplicate-key', 'collection-errors.jsonl', '{"nodeid":"tests/test_public.py","nodeid":"' + PRIVATE + '"}\n', 'EVIDENCE_JSON_INVALID'),
            ('node-type', 'collection-errors.jsonl', '{"nodeid":true}\n', 'EVIDENCE_TYPE_INVALID'),
            ('empty-discovery', 'discovered.jsonl', '{"nodeid":""}\n', 'EVIDENCE_TYPE_INVALID'),
            ('empty-collected', 'collected.json', '{"nodeids":[""]}', 'EVIDENCE_TYPE_INVALID'),
            ('row-overflow', 'collection-errors.jsonl', '{"nodeid":"tests/test_public.py"}\n' * 4097, 'EVIDENCE_TYPE_INVALID'),
            ('session-type', 'session.jsonl', '{"event":"finish","exitstatus":true}\n', 'SESSION_INVALID'),
            ('symlink', 'collection-errors.jsonl', None, 'EVIDENCE_NOT_REGULAR'),
            ('oversize', 'collection-errors.jsonl', None, 'EVIDENCE_TYPE_INVALID'),
        ]
        for index, (label, name, text, code) in enumerate(cases):
            with self.subTest(case=label):
                (self.evidence / name).unlink(missing_ok=True)
                self.ledger()
                forbidden = []
                if label == 'symlink':
                    target = self.root / 'private-payload'
                    target.write_text(PRIVATE)
                    (self.evidence / name).unlink()
                    (self.evidence / name).symlink_to(target)
                    forbidden = [name]
                elif label == 'oversize':
                    with (self.evidence / name).open('wb') as stream:
                        stream.truncate(1024 * 1024 + 1)
                    forbidden = [name]
                else:
                    self.write(name, text)
                if label == 'source-mismatch':
                    forbidden = ['collected.json', 'discovered.jsonl', 'collection-errors.jsonl',
                                 'session.jsonl', 'runner-closeout.json', 'diagnostic-closeout.tsv']
                destination = self.root / str(index)
                destination.mkdir()
                document = self.project(str(index) + '/backend-metadata.json', forbidden, expected_status=2)
                self.assertEqual(document['metadata_error_codes'], [code])
                self.assertEqual(document['partial_diagnostics']['status'], 'unavailable')
                if label != 'source-mismatch':
                    self.assertEqual(document['runner_closeout']['runner']['pytest_exit_code'], 2)
                (self.evidence / name).unlink()

        workflow = (SCRIPTS.parent / 'workflows/ci.yml').read_text()
        reference = workflow.split('  backend-reference:\n', 1)[1].split('  backend-workers:\n', 1)[0]
        self.assertIn('      - name: Generate failed reference metadata\n', reference)
        generation = reference.split('      - name: Generate failed reference metadata\n', 1)[1].split('      - name:', 1)[0]
        self.assertIn("always() && steps.execution.outcome == 'failure' && steps.execution.outputs.evidence != ''", generation)
        self.assertIn('collection-failure "$BACKEND_EVIDENCE" "$GITHUB_WORKSPACE"', generation)
        self.assertIn('120s python .github/scripts/ci_backend_metadata.py', generation)
        self.assertIn('> "$metadata/reporter.log" 2>&1', generation)
        self.assertIn('exit "$status"', generation)
        self.assertIn("always() && steps.execution.outcome == 'failure' && steps.reference_diagnostic_bound.outcome == 'success'", reference)
        self.assertIn('path: ${{ steps.reference_metadata.outputs.metadata_file }}', reference)
        self.assertIn('artifact_id: ${{ steps.upload.outputs.artifact-id }}', reference)
        self.assertIn('needs: backend-reference', workflow)
        self.assertNotIn('continue-on-error', reference)
        seal = reference.split('      - name: Export bounded collection-only plan\n', 1)[1].split('      - name:', 1)[0]
        self.assertNotIn('always()', seal)


if __name__ == '__main__':
    unittest.main()
