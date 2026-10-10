"""Public synthetic controls; no backend imports, SQL, services or private inputs."""
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
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_backend_ci_privacy as privacy

PYTHON_BOUNDARY = privacy.PYTHON_BOUNDARY
SCRIPTS = privacy.SCRIPTS
SENTINEL = privacy.SENTINEL


def load(name):
    path = SCRIPTS / (name + '.py')
    if not path.is_file():
        raise AssertionError('Approved progress implementation is absent')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProgressProjectionTests(unittest.TestCase):
    def setUp(self):
        self.progress = load('ci_backend_progress')
        self.workspace = tempfile.TemporaryDirectory(prefix='ci-progress-public-')
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source = self.root / 'source'
        tests = self.source / 'backend/tests'
        tests.mkdir(parents=True)
        (tests / 'test_public.py').write_text(
            'def test_known():\n    pass\nclass TestKnown:\n    def test_method(self):\n        pass\n')
        env = {'PATH': os.defpath, 'HOME': str(self.root), 'GIT_CONFIG_NOSYSTEM': '1',
               'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_AUTHOR_NAME': 'Synthetic',
               'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid', 'GIT_COMMITTER_NAME': 'Synthetic',
               'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid'}
        for args in (('init', '-q'), ('add', '.'),
                     ('-c', 'commit.gpgsign=false', 'commit', '-qm', 'public fixture')):
            subprocess.run(['git', '-C', str(self.source), *args], env=env,
                           check=True, capture_output=True)
        self.commit = subprocess.check_output(['git', '-C', str(self.source), 'rev-parse', 'HEAD'],
                                              env=env, text=True).strip()
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        (self.evidence / 'source-head.txt').write_text(self.commit + '\n')
        self.node = 'tests/test_public.py::test_known[' + SENTINEL + ']'
        self.reader = self.progress.Progress(self.evidence, self.source)

    def append(self, name, row):
        with (self.evidence / name).open('a') as stream:
            stream.write(json.dumps(row) + '\n')

    def session(self):
        self.append('session.jsonl', {'event': 'start'})
        self.append('discovered.jsonl', {'nodeid': self.node})
        self.append('collected.json', {'nodeids': [self.node]})
        self.append('started.jsonl', {'nodeid': self.node})

    def phase(self, phase, outcome='passed', **extra):
        self.append('phases.jsonl', {'nodeid': self.node, 'phase': phase, 'outcome': outcome,
                                    'duration_seconds': 0.1, **extra})

    def test_initial_observation_is_nonfinal_without_coverage_or_success(self):
        row = self.reader.observe()
        self.assertIn('source_commit', row)
        self.assertEqual(row['source_commit'], self.commit)
        self.assertTrue(row['nonfinal'])
        self.assertEqual(row['session_state'], 'before_session')
        self.assertEqual(row['counts']['completed'], 0)
        self.assertIsNone(row['last_started'])
        self.assertFalse({'success', 'total', 'coverage', 'cause', 'pytest_exit_code'} & row.keys())

    def test_full_original_identity_hash_and_only_public_ast_name(self):
        self.session()
        row = self.reader.observe()
        self.assertEqual(row['last_started'], {
            'node_sha256': hashlib.sha256(self.node.encode()).hexdigest(),
            'public_test': 'test_public.test_known'})
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_unknown_definition_stays_null_not_echoed(self):
        self.append('started.jsonl', {'nodeid': 'tests/' + SENTINEL + '.py::test_unknown'})
        row = self.reader.observe()
        self.assertIsNone(row['last_started']['public_test'])
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_real_start_precedes_setup_report_and_completed_node(self):
        self.session()
        row = self.reader.observe()
        self.assertEqual(row['counts']['started'], 1)
        self.assertEqual(row['counts']['completed'], 0)
        self.assertIsNone(row['last_reported'])
        self.phase('setup')
        row = self.reader.observe()
        self.assertEqual(row['last_reported']['phase'], 'setup')
        self.assertEqual(row['counts']['completed'], 0)
        self.phase('call')
        self.phase('teardown')
        self.assertEqual(self.reader.observe()['counts']['completed'], 1)

    def test_failure_is_observed_before_teardown_without_success_claim(self):
        self.session()
        self.phase('setup')
        self.phase('call', 'failed', longrepr=SENTINEL)
        row = self.reader.observe()
        self.assertEqual(row['counts']['failed_phases'], 1)
        self.assertEqual(row['counts']['completed'], 0)
        self.assertEqual(row['last_reported']['outcome'], 'failed')
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_setup_skip_completes_without_inventing_call_or_pass(self):
        self.session()
        self.phase('setup', 'skipped')
        self.phase('teardown')
        row = self.reader.observe()
        self.assertEqual(row['counts']['completed'], 1)
        self.assertEqual(row['counts']['skipped_phases'], 1)
        self.assertNotIn('call/passed', row['phase_counts'])

    def test_xfail_reason_is_boolean_count_only(self):
        self.session()
        self.phase('setup')
        self.phase('call', 'skipped', wasxfail=SENTINEL)
        self.phase('teardown')
        row = self.reader.observe()
        self.assertEqual(row['counts']['xfail_phases'], 1)
        self.assertEqual(row['counts']['skipped_phases'], 1)
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_finish_is_observed_but_never_certifies_coverage(self):
        self.session()
        self.append('session.jsonl', {'event': 'finish', 'exitstatus': 1, 'error': SENTINEL})
        row = self.reader.observe()
        self.assertEqual(row['session_state'], 'finished')
        self.assertTrue(row['nonfinal'])
        self.assertEqual(row['counts']['completed'], 0)
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_partial_line_is_held_then_consumed_exactly_once(self):
        path = self.evidence / 'started.jsonl'
        line = json.dumps({'nodeid': self.node}) + '\n'
        path.write_text(line[:15])
        row = self.reader.observe()
        self.assertEqual(row['counts']['started'], 0)
        self.assertIn('PARTIAL_RECORD', row['degraded_codes'])
        with path.open('a') as stream:
            stream.write(line[15:])
        self.assertEqual(self.reader.observe()['counts']['started'], 1)
        self.assertEqual(self.reader.observe()['counts']['started'], 1)

    def test_malformed_complete_line_degrades_without_raw_error(self):
        (self.evidence / 'started.jsonl').write_text(SENTINEL + '\n')
        row = self.reader.observe()
        self.assertIn('LEDGER_INVALID', row['degraded_codes'])
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_truncation_is_degraded_and_never_double_counted(self):
        self.session()
        self.reader.observe()
        (self.evidence / 'started.jsonl').write_text('')
        row = self.reader.observe()
        self.assertIn('LEDGER_REPLACED', row['degraded_codes'])
        self.assertEqual(row['counts']['started'], 1)

    def test_replacement_with_same_size_and_new_inode_is_degraded(self):
        self.session()
        self.reader.observe()
        path = self.evidence / 'started.jsonl'
        replacement = self.evidence / 'replacement'
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
        self.assertIn('LEDGER_REPLACED', self.reader.observe()['degraded_codes'])

    def test_duplicate_phase_is_degraded_not_additional_completion(self):
        self.session()
        self.phase('setup')
        self.phase('call')
        self.phase('teardown')
        self.phase('teardown')
        row = self.reader.observe()
        self.assertIn('LEDGER_INVALID', row['degraded_codes'])
        self.assertEqual(row['counts']['completed'], 1)

    def test_invalid_phase_outcome_types_do_not_cross_public_boundary(self):
        for phase, outcome in ((SENTINEL, 'passed'), ('setup', SENTINEL), ('setup', True)):
            self.append('phases.jsonl', {'nodeid': self.node, 'phase': phase, 'outcome': outcome})
        row = self.reader.observe()
        self.assertIn('LEDGER_INVALID', row['degraded_codes'])
        self.assertEqual(row['phase_counts'], {})
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_disk_observation_is_actual_numeric_statvfs_only(self):
        observed = os.statvfs(self.evidence)
        with patch.object(self.progress.os, 'statvfs', return_value=observed) as stat:
            row = self.reader.observe()
        stat.assert_called_once_with(self.evidence)
        self.assertEqual(row['disk_free_bytes'], observed.f_bfree * observed.f_frsize)
        self.assertEqual(row['disk_available_bytes'], observed.f_bavail * observed.f_frsize)
        self.assertNotIn(str(self.root), json.dumps(row))

    def test_read_failure_and_stat_failure_use_fixed_codes(self):
        with patch.object(self.progress.os, 'statvfs', side_effect=OSError(SENTINEL)):
            row = self.reader.observe()
        self.assertIn('DISK_UNAVAILABLE', row['degraded_codes'])
        self.assertIsNone(row['disk_free_bytes'])
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_leaf_symlink_is_rejected_before_read(self):
        secret = self.root / 'synthetic-secret'
        secret.write_text(SENTINEL)
        (self.evidence / 'started.jsonl').symlink_to(secret)
        row = self.reader.observe()
        self.assertIn('PATH_REJECTED', row['degraded_codes'])
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_absolute_relative_dangling_dotdot_and_nested_ancestor_rejection(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        dangling = self.root / 'dangling'
        dangling.symlink_to(self.root / 'missing', target_is_directory=True)
        candidates = (alias / 'evidence', Path(os.path.relpath(alias / 'evidence')),
                      dangling / 'evidence', alias / '..' / self.root.name / 'evidence',
                      alias / 'source/backend/tests')
        for candidate in candidates:
            with self.subTest(candidate=str(candidate)), patch.object(
                    self.progress, 'git', side_effect=AssertionError('No Git I/O before check')):
                row = self.progress.Progress(candidate, self.source).observe()
                self.assertEqual(row['degraded_codes'], ['PATH_REJECTED'])

    def test_source_ancestor_symlink_rejected_before_git_or_structured_read(self):
        alias = self.root / 'source-alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with patch.object(self.progress, 'git', side_effect=AssertionError('No Git I/O before check')):
            row = self.progress.Progress(self.evidence, alias).observe()
        self.assertEqual(row['degraded_codes'], ['PATH_REJECTED'])

    def test_commit_mismatch_does_not_resolve_public_names(self):
        (self.evidence / 'source-head.txt').write_text('a' * 40)
        self.session()
        row = self.reader.observe()
        self.assertIn('SOURCE_UNAVAILABLE', row['degraded_codes'])
        self.assertIsNone(row['source_commit'])
        self.assertIsNone(row['last_started'])

    def test_export_never_opens_raw_logs_failures_or_protected_payload(self):
        self.session()
        for name in ('pytest.log', 'runner.log', 'failures.jsonl', 'protected-input.json'):
            (self.evidence / name).write_text(SENTINEL)
        opened = []
        original = Path.open
        def record(path, *args, **kwargs):
            opened.append(path.name)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', record):
            row = self.reader.observe()
        self.assertFalse({'pytest.log', 'runner.log', 'failures.jsonl', 'protected-input.json'} & set(opened))
        self.assertNotIn(SENTINEL, json.dumps(row))

    def test_initial_and_sixty_second_schedule_and_collection_finish_checkpoints(self):
        self.assertEqual(self.progress.INTERVAL_SECONDS, 60)
        self.assertTrue(self.progress.due(0, None, None, 'before_session'))
        self.assertFalse(self.progress.due(59, 0, 'running', 'running'))
        self.assertTrue(self.progress.due(60, 0, 'running', 'running'))
        self.assertTrue(self.progress.due(1, 0, 'collecting', 'running'))
        self.assertTrue(self.progress.due(2, 1, 'running', 'finished'))


class StartIsolationTests(unittest.TestCase):
    def test_start_hook_failure_does_not_disable_original_accounting(self):
        observer = load('ci_backend_evidence')
        self.assertTrue(hasattr(observer, 'pytest_runtest_logstart'), 'Real start hook is absent')
        with tempfile.TemporaryDirectory(prefix='ci-progress-start-') as temporary:
            root = Path(temporary)
            (root / 'started.jsonl').mkdir()
            with patch.dict(os.environ, {'MTG_CI_EVIDENCE': temporary, 'MTG_CI_PROGRESS': '1'}):
                stream = io.StringIO()
                with contextlib.redirect_stderr(stream):
                    observer.pytest_runtest_logstart('tests/test_public.py::test_known', (SENTINEL, 0, SENTINEL))
                self.assertFalse(observer._degraded)
                observer.pytest_sessionstart(None)
                observer.pytest_itemcollected(SimpleNamespace(nodeid='n'))
                observer.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid='n')]))
                for phase in ('setup', 'call', 'teardown'):
                    observer.pytest_runtest_logreport(SimpleNamespace(nodeid='n', when=phase,
                        outcome='failed' if phase == 'call' else 'passed', duration=0.1,
                        failed=phase == 'call', longrepr=SENTINEL))
                observer.pytest_sessionfinish(None, 1)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(observer.audit(root, 1), 0)
                self.assertIn(SENTINEL, (root / 'failures.jsonl').read_text())
                self.assertEqual(stream.getvalue(), 'CI_PROGRESS_START_DEGRADED\n')

    def test_default_off_does_not_write_new_ledger(self):
        observer = load('ci_backend_evidence')
        self.assertTrue(hasattr(observer, 'pytest_runtest_logstart'), 'Real start hook is absent')
        with tempfile.TemporaryDirectory(prefix='ci-progress-off-') as temporary:
            with patch.dict(os.environ, {'MTG_CI_EVIDENCE': temporary, 'MTG_CI_PROGRESS': '0'}):
                observer.pytest_runtest_logstart('n', (SENTINEL, 0, SENTINEL))
            self.assertFalse((Path(temporary) / 'started.jsonl').exists())


class PublisherBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((SCRIPTS / 'ci_backend_progress.py').is_file(), 'Publisher is absent')
        self.fixture = privacy.RunnerPrivacyTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        scripts = self.fixture.source / '.github/scripts'
        for name in ('ci_backend_progress.py', 'ci_backend_metadata.py'):
            shutil.copyfile(SCRIPTS / name, scripts / name)
        boundary = PYTHON_BOUNDARY.lstrip().replace(
            'import importlib.util, json, os', 'import importlib.util, json, os, time')
        boundary = boundary.replace("mode = os.environ['SYNTHETIC_RUN_MODE']",
            "if len(sys.argv) > 1 and sys.argv[1] == '-I':\n"
            f"    os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n"
            "mode = os.environ['SYNTHETIC_RUN_MODE']")
        boundary = boundary.replace("if args[0].endswith('prepare-backend-private-inputs.py'):",
            "if args[0].endswith('prepare-backend-private-inputs.py'):\n"
            "    assert not Path('/proc/self/fd/5').exists()\n")
        boundary = boundary.replace("assert args[:2] == ['-m', 'pytest']",
            "assert not Path('/proc/self/fd/5').exists()\n"
            "assert args[:2] == ['-m', 'pytest']")
        boundary = boundary.replace("for node in nodes:\n    for phase",
            "for node in nodes:\n    observer.pytest_runtest_logstart(node, ('synthetic', 0, 'synthetic'))\n    for phase")
        (self.fixture.bin / 'python').write_text(boundary)
        # Publisher gets the genuine interpreter despite the synthetic pytest CLI.
        subprocess.run(['git', '-C', str(self.fixture.source), 'add', '.'],
                       env=self.fixture.environment, check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.fixture.source), '-c', 'commit.gpgsign=false',
                        'commit', '-qm', 'public progress fixture'], env=self.fixture.environment,
                       check=True, capture_output=True)

    def run_progress(self, mode, sink=None):
        sink = self.fixture.root / 'public.jsonl' if sink is None else sink
        env = {**self.fixture.environment, 'SYNTHETIC_RUN_MODE': mode, 'MTG_CI_PROGRESS': '1',
               'PYTHONPATH': '/nonexistent/' + SENTINEL, 'MTG_HEAT_WITNESS_01': SENTINEL}
        before = time.monotonic()
        result = subprocess.run(['bash', '-c', 'exec 5>"$1"; bash .github/scripts/run-backend-ci.sh',
                                 'synthetic', str(sink)], cwd=self.fixture.source, env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertNotIn(SENTINEL, sink.read_text(), 'A private child reached the public FD')
        evidence = Path(Path(env['GITHUB_OUTPUT']).read_text().splitlines()[-1].split('=', 1)[1])
        return result, evidence, time.monotonic() - before

    def test_real_public_fd_contains_only_projected_json_and_is_not_in_private_children(self):
        result, evidence, elapsed = self.run_progress('pass')
        self.assertEqual(result.returncode, 0)
        self.fixture.assert_local_only(result, evidence)
        text = (self.fixture.root / 'public.jsonl').read_text()
        self.assertNotIn(SENTINEL, text)
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertTrue(rows)
        self.assertTrue(all(row['nonfinal'] for row in rows))
        for row in rows:
            self.assertTrue({'source_commit', 'observation_sequence', 'elapsed_seconds'} <= row.keys())
            self.assertRegex(row['source_commit'], r'^(?:[0-9a-f]{40}|[0-9a-f]{64})$')
            self.assertIs(type(row['observation_sequence']), int)
            self.assertGreaterEqual(row['observation_sequence'], 0)
            self.assertTrue(math.isfinite(row['elapsed_seconds']))
            self.assertGreaterEqual(row['elapsed_seconds'], 0)
        self.assertEqual([r['observation_sequence'] for r in rows], list(range(len(rows))))
        self.assertEqual([r['elapsed_seconds'] for r in rows], sorted(r['elapsed_seconds'] for r in rows))
        self.assertTrue((evidence / 'started.jsonl').is_file())
        self.assertEqual(json.loads((evidence / 'synthetic-invocation.json').read_text()),
            ['-m', 'pytest', '-vv', '--tb=short', '-ra', '-p', 'no:cacheprovider', '-p', 'ci_backend_evidence'])

    def test_clean_environment_has_no_private_inputs_or_backend_pythonpath(self):
        self.fixture.environment['BASH_FUNC_mktemp%%'] = (
            '() { if [[ -e /proc/self/fd/5 ]]; then printf "%s" '
            + SENTINEL + ' >&5; return 25; fi; /usr/bin/mktemp "$@"; }')
        self.fixture.environment['BASH_FUNC_command%%'] = (
            '() { if [[ -e /proc/self/fd/5 ]]; then printf "%s" '
            + SENTINEL + ' >&5; return 24; fi; builtin command "$@"; }')
        script = self.fixture.source / '.github/scripts/ci_backend_progress.py'
        script.write_text('import json, os, sys\n'
            "assert set(os.environ) <= {'PATH', 'LANG', 'LC_CTYPE'}\n"
            "assert not any('backend' in p or 'scripts' in p for p in sys.path)\n"
            "print(json.dumps({'nonfinal': True, 'environment_clean': 1}), flush=True)\n")
        result, evidence, elapsed = self.run_progress('pass')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads((self.fixture.root / 'public.jsonl').read_text()),
                         {'nonfinal': True, 'environment_clean': 1})

    def test_early_preparation_failure_stops_and_reaps_publisher(self):
        result, evidence, elapsed = self.run_progress('shell')
        self.assertEqual(result.returncode, 17)
        self.fixture.assert_local_only(result, evidence)
        self.assertLess(elapsed, 8)
        self.assert_reaped(evidence)

    def assert_reaped(self, evidence):
        pid = int((evidence / 'progress-owner.pid').read_text())
        self.assertFalse(Path('/proc', str(pid)).exists(), 'Owned publisher remains live or zombie')

    def test_blocked_sink_cannot_backpressure_pytest_or_prevent_deadline_reap(self):
        script = self.fixture.source / '.github/scripts/ci_backend_progress.py'
        script.write_text('import os, signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                          "while True: os.write(1, b'x' * 65536)\n")
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        self.addCleanup(os.close, write_fd)
        env = {**self.fixture.environment, 'SYNTHETIC_RUN_MODE': 'fail_tee', 'MTG_CI_PROGRESS': '1'}
        before = time.monotonic()
        result = subprocess.run(['bash', '-c', 'exec 5>&"$1"; if [[ "$1" != 5 ]]; then eval "exec $1>&-"; fi; exec "$2" .github/scripts/run-backend-ci.sh',
                                 'synthetic', str(write_fd), '/bin/bash'],
                                cwd=self.fixture.source, env=env, pass_fds=(write_fd,),
                                capture_output=True, text=True, timeout=12)
        evidence = Path(Path(env['GITHUB_OUTPUT']).read_text().strip().split('=', 1)[1])
        self.assertEqual(result.returncode, 1)
        self.assertLess(time.monotonic() - before, 8)
        self.assertEqual((evidence / 'pytest-exit-code.txt').read_text().strip(), '1')
        self.assertEqual((evidence / 'tee-exit-code.txt').read_text().strip(), '23')
        self.assert_reaped(evidence)

    def test_progress_never_masks_tee_audit_or_observer_failure(self):
        for mode, expected in (('pass_tee', 23), ('audit', 19), ('observer', 2)):
            with self.subTest(mode=mode):
                result, evidence, elapsed = self.run_progress(mode)
                self.assertEqual(result.returncode, expected)
                self.fixture.assert_local_only(result, evidence)
                self.assert_reaped(evidence)

    def test_workflow_optin_does_not_add_upload_or_permissions(self):
        workflow = (SCRIPTS.parent / 'workflows/ci.yml').read_text()
        self.assertEqual(workflow.count("MTG_CI_PROGRESS: '1'"), 1)
        self.assertIn('bash .github/scripts/run-backend-ci.sh 5>&1', workflow)
        self.assertEqual(workflow.count('uses: actions/upload-artifact@'), 1)
        self.assertIn('permissions:\n  contents: read\n', workflow)


if __name__ == '__main__':
    unittest.main()
