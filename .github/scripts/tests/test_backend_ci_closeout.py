"""Public, owned-process runner closeout controls; never run backend tests."""
import sys


def deny_external_io(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')
    if event == 'import' and args and args[0].split('.', 1)[0] == 'openai':
        raise RuntimeError('PROVIDER_DENIED')


sys.addaudithook(deny_external_io)

import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'closeout_public_donor', Path(__file__).with_name('test_backend_ci_privacy.py'))
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class DiagnosticCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.fixture = privacy.RunnerPrivacyTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        external = os.environ.get('MTG_CI_CLOSEOUT_TEST_EVIDENCE')
        self.ledger_root = Path(external) if external else self.fixture.root / 'closeout-evidence'
        if external:
            self.assertTrue(self.ledger_root.is_dir())
            self.assertEqual(self.ledger_root.resolve(), self.ledger_root)
            self.assertFalse(any(p.is_symlink() for p in (self.ledger_root, *self.ledger_root.parents)))

    def run_control(self, stalled=None, pytest_status=0, ignore_term=False,
                    active_delay=0, diagnostic_status=None, progress_status=None,
                    progress_bootstrap=False, progress_stop_fifo=False):
        fixture = self.fixture
        scripts = fixture.source / '.github/scripts'
        storage = scripts / 'ci_backend_storage.py'
        text = storage.read_text()
        injection = f'''
    import signal
    role = ('pressure' if sys.argv[1] == 'watch' else
            'sink' if sys.argv[1:] == ['stream', sys.argv[2], 'pytest.log'] else
            'logger' if sys.argv[1:] == ['stream', sys.argv[2], 'runner.log'] else None)
    if role:
        (Path(sys.argv[2]) / ('control-' + role + '.pid')).write_text(str(os.getpid()))
    if role is not None and role == {stalled!r}:
        if {ignore_term!r}:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if role != 'sink':
            time.sleep(60)
    if role == 'pressure' and {diagnostic_status!r} is not None:
        return {diagnostic_status!r}
'''
        text = text.replace('def main():\n', 'def main():\n' + injection)
        storage.write_text(text)
        boundary = privacy.PYTHON_BOUNDARY.lstrip().replace(
            '#!/usr/bin/python3 -I\n', '#!/usr/bin/python3 -IB\n')
        boundary = boundary.replace('import importlib.util, json, os',
                                    'import importlib.util, json, os, time')
        boundary = boundary.replace("raise SystemExit(exitcode)\n", f'''
Path(os.environ['MTG_CI_EVIDENCE'], 'control-pytest-ready').write_text('ready')
deadline = time.monotonic() + 15
while not Path(os.environ['MTG_CI_EVIDENCE'], 'control-release').exists():
    if time.monotonic() >= deadline:
        raise SystemExit(99)
    time.sleep(.01)
if {bool(active_delay)!r}:
    Path(os.environ['MTG_CI_EVIDENCE'], 'control-pytest-active').write_text('active')
    deadline = time.monotonic() + 5
    while not Path(os.environ['MTG_CI_EVIDENCE'], 'control-finish').exists():
        if time.monotonic() >= deadline:
            raise SystemExit(98)
        time.sleep(.01)
Path(os.environ['MTG_CI_EVIDENCE'], 'control-pytest-returning').write_text(str({pytest_status!r}))
raise SystemExit({pytest_status!r})
''')
        (fixture.bin / 'python').write_text(boundary)
        if stalled == 'progress' or progress_status is not None:
            (scripts / 'ci_backend_progress.py').write_text(
                'import os, signal, sys, time\nfrom pathlib import Path\n'
                "Path(sys.argv[1], 'control-progress.pid').write_text(str(os.getpid()))\n"
                + (f'raise SystemExit({progress_status!r})\n' if progress_status is not None else
                   'signal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)\n'))
        if progress_bootstrap:
            shutil.copyfile(SCRIPTS / 'ci_backend_metadata.py', scripts / 'ci_backend_metadata.py')
            progress = (SCRIPTS / 'ci_backend_progress.py').read_text()
            bootstrap = '''import os as _bootstrap_os
import sys as _bootstrap_sys
import time as _bootstrap_time
from pathlib import Path as _BootstrapPath
_bootstrap_evidence = _BootstrapPath(_bootstrap_sys.argv[1])
(_bootstrap_evidence / 'control-progress.pid').write_text(str(_bootstrap_os.getpid()))
(_bootstrap_evidence / 'control-progress-bootstrap').write_text('waiting\\n')
_bootstrap_deadline = _bootstrap_time.monotonic() + 5
while not (_bootstrap_evidence / 'progress-stop').exists():
    if _bootstrap_time.monotonic() >= _bootstrap_deadline:
        raise SystemExit('CONTROL_PROGRESS_BOOTSTRAP_TIMEOUT')
    _bootstrap_time.sleep(.01)
'''
            (scripts / 'ci_backend_progress.py').write_text(bootstrap + progress)
        self.commit_fixture()
        environment = {**fixture.environment,
                       'SYNTHETIC_RUN_MODE': 'fail' if pytest_status == 1 else 'pass'}
        if stalled == 'progress' or progress_status is not None or progress_bootstrap:
            environment['MTG_CI_PROGRESS'] = '1'
            # The donor Python CLI forwards the original isolated progress calls.
            python = fixture.bin / 'python'
            body = python.read_text().replace("mode = os.environ['SYNTHETIC_RUN_MODE']",
                "if len(sys.argv) > 1 and sys.argv[1] == '-I':\n"
                "    os.execv('/usr/bin/python3', ['/usr/bin/python3', *sys.argv[1:]])\n"
                "mode = os.environ['SYNTHETIC_RUN_MODE']")
            python.write_text(body)
        started = time.monotonic()
        child = subprocess.Popen(
            ['/bin/bash', '-c', 'exec 5>/dev/null; exec /bin/bash .github/scripts/run-backend-ci.sh'],
            cwd=fixture.source, env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True)
        evidence = None
        held_writer = None
        timed_out = False
        owned = {}
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                output = Path(environment['GITHUB_OUTPUT'])
                if output.exists() and output.read_text().startswith('evidence='):
                    evidence = Path(output.read_text().strip().split('=', 1)[1])
                    if (evidence / 'control-pytest-ready').exists() and (
                            not progress_bootstrap or (evidence / 'control-progress-bootstrap').exists()):
                        break
                if child.poll() is not None:
                    self.fail('Control runner ended before synthetic pytest readiness')
                time.sleep(.01)
            self.assertIsNotNone(evidence)
            self.assertTrue((evidence / 'control-pytest-ready').exists())
            if progress_bootstrap:
                self.assertTrue((evidence / 'control-progress-bootstrap').exists())
            if stalled == 'sink':
                paths = dict(line.split('=', 1) for line in
                             (evidence / 'owned-paths.txt').read_text().splitlines())
                held_writer = os.open(Path(paths['work']) / 'pytest-output',
                                      os.O_WRONLY | os.O_NONBLOCK)
            if progress_stop_fifo:
                os.mkfifo(evidence / 'progress-stop', 0o600)
            (evidence / 'control-release').write_text('release')
            if active_delay:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not (
                        evidence / 'control-pytest-active').exists():
                    time.sleep(.01)
                self.assertTrue((evidence / 'control-pytest-active').exists())
                self.assertIsNone(child.poll(), 'Diagnostic closeout interrupted active pytest')
                self.assertEqual((evidence / 'pytest-exit-code.txt').read_text(), '')
                (evidence / 'control-finish').write_text('finish')
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not (
                    evidence / 'control-pytest-returning').exists():
                time.sleep(.01)
            self.assertTrue((evidence / 'control-pytest-returning').exists())
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline and (
                    evidence / 'pytest-exit-code.txt').read_text().strip() != str(pytest_status):
                time.sleep(.01)
            promptly_saved = (evidence / 'pytest-exit-code.txt').read_text().strip() == str(pytest_status)
            try:
                stdout, stderr = child.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                timed_out = True
                stdout, stderr = '', ''
        finally:
            if held_writer is not None:
                os.close(held_writer)
            if evidence is not None:
                owned = {p.stem: int(p.read_text()) for p in evidence.glob('control-*.pid')}
            if child.poll() is None:
                for pid in owned.values():
                    path = Path('/proc', str(pid), 'stat')
                    try:
                        fields = path.read_text().rsplit(')', 1)[1].split()
                        self.assertEqual(int(fields[1]), child.pid,
                                         'Only direct control children may be stopped')
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except FileNotFoundError:
                        pass
                try:
                    child.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    pass
            # This new session contains only this control's stub runner/children.
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=3)
            child.communicate(timeout=3)
            ledger = self.ledger_root / (
                self._testMethodName + '-' + str(time.time_ns()))
            ledger.mkdir(parents=True)
            remaining = [pid for pid in owned.values() if Path('/proc', str(pid)).exists()]
            (ledger / 'closure.json').write_text(json.dumps({
                'runner_pid': child.pid, 'runner_wait': child.returncode,
                'known_diagnostics': owned, 'remaining': remaining,
                'timed_out_before_test_cleanup': timed_out}))
            if evidence is not None:
                for name in ('pytest-exit-code.txt', 'tee-exit-code.txt',
                             'diagnostic-closeout.tsv', 'coverage.json',
                             'pytest.log.stream.json', 'runner.log.stream.json'):
                    path = evidence / name
                    if path.is_file():
                        shutil.copyfile(path, ledger / name)
            self.assertFalse(remaining, 'Control cleanup left a diagnostic process')
        self.assertFalse(timed_out, 'Runner remained blocked after synthetic pytest returned')
        self.assertTrue(promptly_saved, 'Actual pytest exit was delayed behind diagnostic closeout')
        self.assertEqual((stdout, stderr), ('', ''))
        self.assertEqual((evidence / 'pytest-exit-code.txt').read_text().strip(),
                         str(pytest_status))
        self.assertNotIn(privacy.SENTINEL, stdout + stderr)
        pids = {p.stem: int(p.read_text()) for p in evidence.glob('control-*.pid')}
        for role, pid in pids.items():
            self.assertFalse(Path('/proc', str(pid)).exists(), role + ' was not reaped')
        return child.returncode, evidence

    def commit_fixture(self):
        for args in (('add', '.'), ('-c', 'commit.gpgsign=false', 'commit', '-qm',
                                  'public closeout control')):
            subprocess.run(['git', '-C', str(self.fixture.source), *args],
                           env=self.fixture.environment, check=True, capture_output=True)

    def test_pressure_stall_is_bounded_reaped_and_recorded_after_true_pytest_zero(self):
        code, evidence = self.run_control('pressure', ignore_term=True)
        self.assertEqual(code, 2)
        self.assertIn('pressure', (evidence / 'diagnostic-closeout.tsv').read_text())

    def test_leaked_fifo_writer_cannot_block_sink_and_ignored_term_is_escalated(self):
        code, evidence = self.run_control('sink', ignore_term=True)
        self.assertEqual(code, 2)
        self.assertNotEqual((evidence / 'tee-exit-code.txt').read_text().strip(), '0')
        self.assertFalse((evidence / 'pytest.log.stream.json').exists())

    def test_pressure_cleanup_cannot_replace_pytest_failure(self):
        code, evidence = self.run_control('pressure', pytest_status=1, ignore_term=True)
        self.assertEqual(code, 1)

    def test_sink_cleanup_cannot_replace_pytest_timeout_status(self):
        code, evidence = self.run_control('sink', pytest_status=124, ignore_term=True)
        self.assertEqual(code, 124)

    def test_logger_ignoring_term_is_bounded_reaped_and_not_success(self):
        code, evidence = self.run_control('logger', ignore_term=True)
        self.assertEqual(code, 2)
        self.assertFalse((evidence / 'runner.log.stream.json').exists())

    def test_progress_ignoring_shutdown_is_reaped_and_cannot_be_green(self):
        code, evidence = self.run_control('progress')
        self.assertEqual(code, 2)

    def test_natural_diagnostic_failure_preserves_actual_pytest_exit(self):
        code, evidence = self.run_control(diagnostic_status=23)
        self.assertEqual(code, 2)

    def test_natural_progress_exit_cannot_be_masked_by_successful_logger(self):
        code, evidence = self.run_control(progress_status=23)
        self.assertEqual(code, 2)

    def test_existing_progress_stop_fifo_rejects_without_blocking_closeout(self):
        code, evidence = self.run_control(progress_status=0, progress_stop_fifo=True)
        self.assertEqual(code, 2)
        self.assertTrue((evidence / 'progress-stop').is_fifo())
        progress_rows = [row.split('\t') for row in
                         (evidence / 'diagnostic-closeout.tsv').read_text().splitlines()
                         if row.startswith('progress\t')]
        self.assertEqual(len(progress_rows), 1)
        self.assertEqual(progress_rows[0][2:], ['1', '0', '0'])

    def test_progress_bootstrap_stop_reaches_real_main_and_normal_closeout(self):
        code, evidence = self.run_control(progress_bootstrap=True)
        self.assertEqual(code, 0)
        self.assertEqual((evidence / 'control-progress-bootstrap').read_bytes(), b'waiting\n')
        self.assertEqual((evidence / 'progress-stop').read_bytes(), b'stop\n')
        pid = int((evidence / 'control-progress.pid').read_text())
        progress_rows = [row.split('\t') for row in
                         (evidence / 'diagnostic-closeout.tsv').read_text().splitlines()
                         if row.startswith('progress\t')]
        self.assertEqual(progress_rows, [['progress', str(pid), '1', '0', '0']])
        self.assertFalse(Path('/proc', str(pid)).exists(), 'Actual progress PID was not reaped')

    def test_natural_closeout_preserves_complete_private_stream_and_success(self):
        code, evidence = self.run_control()
        self.assertEqual(code, 0)
        self.assertIn(privacy.SENTINEL, (evidence / 'pytest.log').read_text())
        receipt = json.loads((evidence / 'pytest.log.stream.json').read_text())
        self.assertTrue(receipt['full_raw_retained'])
        self.assertFalse(receipt['truncated'])

    def test_closeout_does_not_run_while_pytest_is_active(self):
        code, evidence = self.run_control(active_delay=1)
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
