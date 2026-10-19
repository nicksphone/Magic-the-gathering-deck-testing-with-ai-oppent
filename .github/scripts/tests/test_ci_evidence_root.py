"""Original caller tests must not redirect their own pytest completeness writer."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
SOURCE = SCRIPTS.parents[1]


class EvidenceRootTests(unittest.TestCase):
    def test_real_original_callers_and_failure_keep_session_evidence_root(self):
        with tempfile.TemporaryDirectory(prefix='ci-root-public-') as directory:
            root = Path(directory)
            backend = root / 'backend'
            tests = backend / 'tests'
            tests.mkdir(parents=True)
            evidence = root / 'evidence'
            evidence.mkdir()
            for name in ('conftest.py', 'test_closed_http_runtime_callers.py',
                         'closed_http_runtime.py', 'test_private_choice_http_restart.py',
                         'test_library_choice_http_audit.py', 'test_land_consumer_variants_http.py',
                         'test_activated_handland_http_audit.py', 'test_optional_land_choice_http_stage.py'):
                shutil.copyfile(SOURCE / 'backend/tests' / name, tests / name)
            (tests / 'test_writer_failure.py').write_text(
                'import os\n'
                'def test_redirected_failure(monkeypatch, tmp_path):\n'
                '    monkeypatch.setenv("MTG_CI_EVIDENCE", str(tmp_path))\n'
                '    raise RuntimeError("synthetic public failure")\n')
            launcher = (
                'import sys\n'
                'def deny(event,args):\n'
                '    if event.startswith(("sqlite3.","socket.")):\n'
                '        raise RuntimeError("SQL_SOCKET_DENIED")\n'
                'sys.addaudithook(deny)\n'
                'sys.path[:0] = [sys.argv.pop(1), sys.argv.pop(1)]\n'
                'import pytest\n'
                'raise SystemExit(pytest.main(sys.argv[1:]))\n')
            environment = {'PATH': os.defpath, 'HOME': directory,
                'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                'MTG_CI_PROGRESS': '1', 'MTG_CI_EVIDENCE': str(evidence),
                'MTG_ISOLATED_TEST_ROOT': str(root), 'TMPDIR': directory}
            result = subprocess.run([sys.executable, '-I', '-B', '-c', launcher,
                str(SCRIPTS), str(backend), '-q', '-p', 'no:cacheprovider',
                '-p', 'ci_backend_evidence', str(tests / 'test_closed_http_runtime_callers.py'),
                str(tests / 'test_writer_failure.py')], cwd=backend, env=environment,
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            collected = json.loads((evidence / 'collected.json').read_text())['nodeids']
            self.assertEqual(len(collected), 3)
            phases = [json.loads(line) for line in (evidence / 'phases.jsonl').read_text().splitlines()]
            self.assertEqual(len(phases), 9, 'call phases followed a test environment override')
            self.assertEqual({row['nodeid'] for row in phases}, set(collected))
            for node in collected:
                self.assertEqual({row['phase'] for row in phases if row['nodeid'] == node},
                                 {'setup', 'call', 'teardown'})
            self.assertEqual(sum(row['outcome'] == 'failed' for row in phases), 1)
            signatures = [json.loads(line) for line in
                          (evidence / 'failure-signatures.jsonl').read_text().splitlines()]
            self.assertEqual(len(signatures), 1)
            self.assertEqual(signatures[0]['signature']['exception'], 'RuntimeError')
            self.assertEqual(len((evidence / 'started.jsonl').read_text().splitlines()), 3)
            session = [json.loads(line) for line in (evidence / 'session.jsonl').read_text().splitlines()]
            self.assertEqual(session[-1], {'event': 'finish', 'exitstatus': 1})


if __name__ == '__main__':
    unittest.main()
