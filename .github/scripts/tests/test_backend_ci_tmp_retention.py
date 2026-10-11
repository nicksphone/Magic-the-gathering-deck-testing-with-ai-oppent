"""Real pytest scratch-retention checks with generated public data only."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]


def runner_options():
    script = (SCRIPTS / 'run-backend-ci.sh').read_text()
    command = re.search(r'^python -m pytest (.*?)\\\n  3>&-', script, re.M | re.S)
    if command is None:
        raise AssertionError('Backend pytest command not found')
    return shlex.split(command.group(1).replace('\\\n', ' '))


class ScratchRetentionTests(unittest.TestCase):
    def test_runner_uses_builtin_failed_retention_without_filtering_tests(self):
        options = runner_options()
        self.assertIn('tmp_path_retention_policy=failed', options)
        self.assertEqual(options, ['-vv', '--tb=short', '-ra', '-p',
            'no:cacheprovider', '-p', 'ci_backend_evidence', '-o',
            'tmp_path_retention_policy=failed'])

    def test_real_pytest_reclaims_passed_scratch_but_retains_failed_call_and_ledger(self):
        with tempfile.TemporaryDirectory(prefix='ci-retention-public-') as directory:
            root = Path(directory)
            evidence = root / 'evidence'
            evidence.mkdir()
            scenario = root / 'scenario'
            scenario.mkdir()
            (scenario / 'test_scratch.py').write_text(textwrap.dedent('''\
                import json
                import os
                from pathlib import Path
                import pytest

                METRICS = Path(os.environ['PUBLIC_RETENTION_METRICS'])

                def record(path):
                    sizes = [p.stat().st_size for p in path.parent.rglob('payload.bin')]
                    with METRICS.open('a') as stream:
                        stream.write(json.dumps({'retained_bytes': sum(sizes)}) + '\\n')

                @pytest.mark.parametrize('case', range(20))
                def test_passed_scratch(tmp_path, case):
                    (tmp_path / 'payload.bin').write_bytes(b'p' * 262144)
                    record(tmp_path)

                def test_failed_scratch(tmp_path):
                    (tmp_path / 'payload.bin').write_bytes(b'f' * 262144)
                    record(tmp_path)
                    assert False, 'generated public failure'

                def test_final_fixture_state(tmp_path_factory):
                    base = tmp_path_factory.getbasetemp()
                    paths = list(base.rglob('payload.bin'))
                    Path(os.environ['PUBLIC_RETENTION_FINAL']).write_text(json.dumps([
                        {'directory': p.parent.name, 'size': p.stat().st_size}
                        for p in paths]))
            '''))
            launcher = textwrap.dedent('''\
                import sys
                def deny(event, args):
                    if event.startswith(('sqlite3.', 'socket.')):
                        raise RuntimeError('SQL_SOCKET_DENIED')
                sys.addaudithook(deny)
                import runpy
                sys.path.insert(0, sys.argv.pop(1))
                sys.argv[0] = 'pytest'
                runpy.run_module('pytest', run_name='__main__')
            ''')
            environment = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                'MTG_CI_PROGRESS': '0', 'MTG_CI_EVIDENCE': str(evidence),
                'PYTEST_DEBUG_TEMPROOT': str(root),
                'PUBLIC_RETENTION_METRICS': str(root / 'metrics.jsonl'),
                'PUBLIC_RETENTION_FINAL': str(root / 'final.json')}
            environment.pop('PYTEST_ADDOPTS', None)
            result = subprocess.run([sys.executable, '-I', '-B', '-c', launcher,
                str(SCRIPTS), *runner_options()], cwd=scenario, env=environment,
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            collected = json.loads((evidence / 'collected.json').read_text())['nodeids']
            phases = [json.loads(line) for line in (evidence / 'phases.jsonl').read_text().splitlines()]
            self.assertEqual(len(collected), 22)
            self.assertEqual(len(phases), 66)
            self.assertEqual(sum(row['outcome'] == 'failed' for row in phases), 1)
            final = json.loads((root / 'final.json').read_text())
            self.assertEqual(len(final), 1)
            self.assertTrue(final[0]['directory'].startswith('test_failed_scratch'))
            self.assertEqual(final[0]['size'], 262144)
            samples = [json.loads(line) for line in (root / 'metrics.jsonl').read_text().splitlines()]
            self.assertEqual(len(samples), 21)
            self.assertEqual(max(row['retained_bytes'] for row in samples), 262144)


if __name__ == '__main__':
    unittest.main()
