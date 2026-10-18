"""PUBLIC slow pytest-startup control, before any pytest_configure hook."""
import os
import importlib.util
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import tempfile
import unittest

from test_backend_ci_tmp_retention import runner_command

SCRIPTS = Path(__file__).resolve().parents[1]


def producer_prefix():
    command = runner_command()
    return shlex.join(command[:command.index('python')]) + ' '


class EarlyStorageInterruptTests(unittest.TestCase):
    def test_native_producer_restores_int_without_changing_pytest_arguments(self):
        self.assertEqual(producer_prefix(), '/usr/bin/env --default-signal=INT ')
        script = shlex.join(runner_command())
        self.assertIn('python -m pytest -vv --tb=short -ra -p no:cacheprovider -p ci_backend_evidence -p ci_backend_snapshot_cleanup -o tmp_path_retention_policy=failed', script)

    def test_actual_slow_pytest_startup_is_interrupted_before_configure(self):
        with tempfile.TemporaryDirectory(prefix='ci-public-preconfigure-') as directory:
            root = Path(directory).resolve()
            evidence = root / 'evidence'; evidence.mkdir()
            spec = importlib.util.spec_from_file_location('public_pressure_control', SCRIPTS / 'ci_backend_storage.py')
            storage = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(storage)
            storage.prepare(evidence, reserve_bytes=4096)
            (root / 'conftest.py').write_text(
                'from pathlib import Path\nimport sys, time\n'
                'def deny(event, args):\n'
                "    if event.startswith(('sqlite3.', 'socket.')): raise RuntimeError('SQL_SOCKET_DENIED')\n"
                'sys.addaudithook(deny)\n'
                "Path('ready').write_text('PUBLIC startup before configure')\n"
                'time.sleep(30)\n'
                "def pytest_configure(config): Path('configured').write_text('unexpected')\n")
            (root / 'test_public.py').write_text('def test_not_reached(): assert True\n')
            # Bash's asynchronous child inherits ignored SIGINT without the
            # native env reset. Signal only the PID this same shell just spawned.
            launch = ("trap 'kill -TERM \"$pid\" 2>/dev/null; wait \"$pid\" 2>/dev/null' TERM\n"
                + producer_prefix() + '"$1" -I -B -m pytest -p no:cacheprovider >private.log 2>&1 &\n'
                'pid=$!\n'
                'for ((i=0;i<100;i++)); do [[ -f ready ]] && break; sleep .02; done\n'
                '[[ -f ready ]] || { kill -TERM "$pid"; wait "$pid"; exit 99; }\n'
                '"$1" -I -B -c \'import importlib.util,sys; from types import SimpleNamespace; '
                's=importlib.util.spec_from_file_location("public_watcher",sys.argv[1]); '
                'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                'm.STATVFS=lambda fd: SimpleNamespace(f_bavail=0,f_frsize=4096,f_favail=99999); '
                'raise SystemExit(m.watch(sys.argv[2],int(sys.argv[3])))\' "$2" "$PWD/evidence" "$pid"\n'
                'watch_status=$?\nwait "$pid"\n')
            env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
            for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'MTG_CI_STORAGE_GUARD'):
                env.pop(name, None)
            process = subprocess.Popen(['/bin/bash', '-c', launch, 'public-control', sys.executable,
                str(SCRIPTS / 'ci_backend_storage.py')],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True)
            timed_out = False
            try:
                try:
                    stdout, stderr = process.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.terminate()
                    stdout, stderr = process.communicate(timeout=3)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            self.assertFalse(timed_out, 'Pre-configure SIGINT was ignored; pytest remained live')
            self.assertEqual((stdout, stderr), ('', ''))
            self.assertIn(process.returncode, (2, 128 + signal.SIGINT))
            self.assertTrue((root / 'ready').exists())
            self.assertFalse((root / 'configured').exists())
            self.assertIn('KeyboardInterrupt', (root / 'private.log').read_text())
            import json
            self.assertEqual(json.loads((evidence / 'storage-status.json').read_text())['reason'], 'byte-pressure')
            self.assertFalse((evidence / storage.RESERVE_NAME).exists())


if __name__ == '__main__':
    unittest.main()
