"""Stdlib runner boundary controls using public, generated sentinel inputs only."""
import sys


def deny_external_io(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')


sys.addaudithook(deny_external_io)

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
SENTINEL = 'SYNTHETIC_RUNNER_PRIVATE_PAYLOAD_c9341'
PYTHON_BOUNDARY = r'''
#!/usr/bin/python3 -I
import sys
def deny(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')
sys.addaudithook(deny)
import importlib.util, json, os
from pathlib import Path
from types import SimpleNamespace
marker = 'SYNTHETIC_RUNNER_PRIVATE_PAYLOAD_c9341'
mode = os.environ['SYNTHETIC_RUN_MODE']
args = sys.argv[1:]
if args == ['--version']:
    print('Python synthetic CLI boundary')
    raise SystemExit(0)
if args == ['-']:
    print('[]')
    raise SystemExit(0)
if args[0].endswith('prepare-backend-private-inputs.py'):
    print('synthetic source echo: assert ' + repr(marker))
    print('synthetic provision stderr: ' + marker, file=sys.stderr)
    if mode == 'shell':
        print('RuntimeError: ' + marker, file=sys.stderr)
        raise SystemExit(17)
    destination = Path(args[1])
    destination.mkdir()
    (destination / 'sealed-self-removal-witness.json').write_text(json.dumps({'synthetic': marker}))
    raise SystemExit(0)
root = Path(os.environ['MTG_ISOLATED_TEST_ROOT'])
spec = importlib.util.spec_from_file_location('actual_observer', root / '.github/scripts/ci_backend_evidence.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)
if args[0].endswith('ci_backend_evidence.py'):
    if mode == 'audit':
        print(marker)
        print('synthetic audit exception: ' + marker, file=sys.stderr)
        raise SystemExit(19)
    raise SystemExit(observer.audit(Path(args[1]), int(args[2])))
assert args[:2] == ['-m', 'pytest']
Path(os.environ['MTG_CI_EVIDENCE'], 'synthetic-invocation.json').write_text(json.dumps(args))
nodes = ['tests/test_public.py::test_failure[' + marker + ']',
         'tests/test_public.py::test_success', 'tests/test_public.py::test_xfail']
exitcode = 1 if mode in ('fail', 'fail_tee') else 0
observer.pytest_sessionstart(None)
for node in nodes:
    observer.pytest_itemcollected(SimpleNamespace(nodeid=node))
observer.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid=n) for n in nodes]))
if mode == 'observer':
    Path(os.environ['MTG_CI_EVIDENCE'], 'phases.jsonl').mkdir()
for node in nodes:
    for phase in ('setup', 'call', 'teardown'):
        outcome = 'passed'
        if phase == 'call' and node == nodes[0] and exitcode:
            outcome = 'failed'
        if phase == 'call' and node == nodes[2]:
            outcome = 'skipped'
        report = SimpleNamespace(nodeid=node, when=phase, outcome=outcome, duration=0.125,
                                 failed=outcome == 'failed', longrepr='AssertionError: ' + marker)
        if node == nodes[2] and phase == 'call':
            report.wasxfail = marker
        observer.pytest_runtest_logreport(report)
observer.pytest_sessionfinish(None, exitcode)
print('synthetic captured pytest stdout: ' + marker)
print('synthetic captured pytest stderr: ' + marker, file=sys.stderr)
print('synthetic assertion repr: ' + repr({'private': marker}))
raise SystemExit(exitcode)
'''


class RunnerPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix='ci-public-runner-')
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source = self.root / 'source'
        scripts = self.source / '.github/scripts'
        scripts.mkdir(parents=True)
        for name in ('run-backend-ci.sh', 'ci_backend_evidence.py'):
            shutil.copyfile(SCRIPTS / name, scripts / name)
        # This stand-in never reads env secrets or the real preparation implementation.
        (scripts / 'prepare-backend-private-inputs.py').write_text('# generated public stand-in\n')
        tests = self.source / 'backend/tests'
        tests.mkdir(parents=True)
        (tests / 'test_public.py').write_text(
            f'def test_failure():\n    assert False, {SENTINEL!r}\n'
            f'def test_success():\n    print({SENTINEL!r})\n'
            'def test_xfail():\n    pass\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'python').write_text(textwrap.dedent(PYTHON_BOUNDARY).lstrip())
        (self.bin / 'python').chmod(0o700)
        (self.bin / 'tee').write_text(
            '#!/bin/bash\n/usr/bin/tee "$@"\nstatus=$?\n'
            'if [[ "$SYNTHETIC_RUN_MODE" == *tee ]]; then\n'
            f'  printf "%s\\n" "{SENTINEL}" >&2\n  exit 23\nfi\nexit "$status"\n')
        (self.bin / 'tee').chmod(0o700)
        self.environment = {'PATH': str(self.bin) + ':' + os.defpath,
                            'HOME': str(self.root), 'GIT_CONFIG_NOSYSTEM': '1',
                            'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_AUTHOR_NAME': 'Synthetic',
                            'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
                            'GIT_COMMITTER_NAME': 'Synthetic',
                            'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid',
                            'RUNNER_TEMP': str(self.root),
                            'GITHUB_OUTPUT': str(self.root / 'step-output.txt')}
        for args in (('init', '-q'), ('add', '.'),
                     ('-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic runner source')):
            subprocess.run(['git', '-C', str(self.source), *args], env=self.environment,
                           check=True, capture_output=True)

    def run_backend(self, mode):
        environment = {**self.environment, 'SYNTHETIC_RUN_MODE': mode}
        result = subprocess.run(['bash', '.github/scripts/run-backend-ci.sh'],
                                cwd=self.source, env=environment, timeout=20,
                                capture_output=True, text=True)
        output = Path(environment['GITHUB_OUTPUT']).read_text().strip()
        self.assertTrue(output.startswith('evidence='))
        evidence = Path(output.split('=', 1)[1])
        return result, evidence

    def metadata(self, evidence):
        spec = importlib.util.spec_from_file_location('privacy_reporter', SCRIPTS / 'ci_backend_metadata.py')
        reporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reporter)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            document, status = reporter.build_metadata(evidence, self.source)
        self.assertNotIn(SENTINEL, stream.getvalue() + json.dumps(document))
        return document, status

    def assert_local_only(self, result, evidence):
        self.assertEqual(result.stdout, '')
        self.assertEqual(result.stderr, '')
        self.assertTrue((evidence / 'runner.log').is_file())
        self.assertIn(SENTINEL, (evidence / 'runner.log').read_text())

    def test_failing_pytest_boundary_retains_all_rows_and_true_exit_locally(self):
        result, evidence = self.run_backend('fail')
        self.assertEqual(result.returncode, 1)
        self.assert_local_only(result, evidence)
        self.assertIn(SENTINEL, (evidence / 'pytest.log').read_text())
        self.assertIn(SENTINEL, (evidence / 'failures.jsonl').read_text())
        self.assertEqual(json.loads((evidence / 'synthetic-invocation.json').read_text()),
                         ['-m', 'pytest', '-vv', '--tb=short', '-ra', '-p',
                          'no:cacheprovider', '-p', 'ci_backend_evidence'])
        document, status = self.metadata(evidence)
        self.assertEqual(status, 0)
        self.assertEqual(document['pytest_exit_code'], 1)
        self.assertEqual(document['coverage']['collected_count'], 3)
        self.assertEqual(document['coverage']['phase_counts'],
                         {'setup/passed': 3, 'teardown/passed': 3,
                          'call/failed': 1, 'call/passed': 1, 'call/skipped': 1})
        nodes = json.loads((evidence / 'collected.json').read_text())['nodeids']
        self.assertEqual(document['collected_node_sha256'],
                         [hashlib.sha256(n.encode()).hexdigest() for n in nodes])
        self.assertEqual(len(document['phases']), 9)
        self.assertEqual(document['failures'][0]['public_test'], 'test_public.test_failure')
        self.assertTrue(document['coverage']['all_collected_completed'])
        self.assertFalse(document['coverage']['ci_success_consistent'])

    def test_passing_pytest_boundary_preserves_skipped_phase_without_inventing_pass(self):
        result, evidence = self.run_backend('pass')
        self.assertEqual(result.returncode, 0)
        self.assert_local_only(result, evidence)
        document, status = self.metadata(evidence)
        self.assertEqual(status, 0)
        self.assertEqual(document['coverage']['phase_counts']['call/skipped'], 1)
        self.assertTrue(document['phases'][7]['xfail_marker'])

    def test_private_preparation_shell_failure_is_local_and_not_success(self):
        result, evidence = self.run_backend('shell')
        self.assertEqual(result.returncode, 17)
        self.assert_local_only(result, evidence)
        document, status = self.metadata(evidence)
        self.assertEqual(status, 2)
        self.assertFalse(document['coverage']['all_collected_completed'])

    def test_real_observer_write_failure_is_local_and_audit_still_fails(self):
        result, evidence = self.run_backend('observer')
        self.assertEqual(result.returncode, 2)
        self.assert_local_only(result, evidence)
        self.assertIn('CI_EVIDENCE_WRITE_ERROR', (evidence / 'runner.log').read_text())
        self.assertIn('CI_EVIDENCE_DEGRADED=1', (evidence / 'runner.log').read_text())
        document, status = self.metadata(evidence)
        self.assertEqual(status, 2)
        self.assertFalse(document['rows_exported'])

    def test_audit_exception_and_stdout_are_local_and_exit_is_retained(self):
        result, evidence = self.run_backend('audit')
        self.assertEqual(result.returncode, 19)
        self.assert_local_only(result, evidence)
        self.assertIn(SENTINEL, (evidence / 'coverage.json').read_text())
        document, status = self.metadata(evidence)
        self.assertEqual(status, 2)
        self.assertFalse(document['coverage']['ci_success_consistent'])

    def test_tee_failure_cannot_become_backend_success(self):
        result, evidence = self.run_backend('pass_tee')
        self.assertEqual(result.returncode, 23)
        self.assert_local_only(result, evidence)
        self.assertEqual((evidence / 'pytest-exit-code.txt').read_text().strip(), '0')
        self.assertEqual((evidence / 'tee-exit-code.txt').read_text().strip(), '23')

    def test_pytest_failure_keeps_precedence_over_tee_failure(self):
        result, evidence = self.run_backend('fail_tee')
        self.assertEqual(result.returncode, 1)
        self.assert_local_only(result, evidence)
        self.assertEqual((evidence / 'tee-exit-code.txt').read_text().strip(), '23')

    def test_bootstrap_failure_prints_only_fixed_code(self):
        environment = {**self.environment, 'RUNNER_TEMP': str(self.root / SENTINEL)}
        result = subprocess.run(['bash', '.github/scripts/run-backend-ci.sh'],
                                cwd=self.source, env=environment,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        self.assertEqual(result.stderr, 'CI_BACKEND_EVIDENCE_SETUP_ERROR\n')


class WorkflowPublicationTests(unittest.TestCase):
    def test_upload_consumer_can_only_select_the_exact_metadata_json(self):
        workflow = (SCRIPTS.parent / 'workflows/ci.yml').read_text()
        steps = workflow.split('      - ')
        uploads = [step for step in steps if 'uses: actions/upload-artifact@' in step]
        self.assertEqual(len(uploads), 1, 'A broad raw diagnostic upload still exists')
        upload = uploads[0]
        self.assertIn('name: Upload backend metadata\n', upload)
        self.assertIn('path: ${{ steps.backend_metadata.outputs.metadata_file }}\n', upload)
        self.assertNotIn('steps.backend_tests.outputs.evidence', upload)
        self.assertNotIn('continue-on-error:', workflow)
        self.assertIn('if-no-files-found: error\n', upload)

    def test_reporter_tests_precede_the_only_secret_bearing_step(self):
        workflow = (SCRIPTS.parent / 'workflows/ci.yml').read_text()
        self.assertIn('      - name: Backend metadata reporter tests\n', workflow)
        self.assertLess(workflow.index('name: Backend metadata reporter tests'),
                        workflow.index('name: Backend tests'))
        secret_steps = [step for step in workflow.split('      - ') if '${{ secrets.' in step]
        self.assertEqual(len(secret_steps), 1)
        self.assertTrue(secret_steps[0].startswith('name: Backend tests\n'))


if __name__ == '__main__':
    unittest.main()
