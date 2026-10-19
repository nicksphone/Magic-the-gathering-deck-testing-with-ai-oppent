"""Actual pytest observer controls using generated, nonprivate sentinel data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
SENTINEL = 'SYNTHETIC_SIGNATURE_MESSAGE_NOT_PUBLIC_247a'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ObserverSignatureTests(unittest.TestCase):
    def test_actual_setup_call_and_custom_exception_keep_messages_private(self):
        with tempfile.TemporaryDirectory(prefix='ci-signatures-public-') as directory:
            root = Path(directory)
            source, evidence = root / 'source', root / 'evidence'
            tests = source / 'backend/tests'
            tests.mkdir(parents=True)
            evidence.mkdir()
            path = tests / 'test_diagnostic.py'
            path.write_text(
                'import pytest\n'
                '@pytest.fixture\n'
                'def rejected():\n'
                f'    raise PermissionError({SENTINEL!r})\n'
                'def test_setup(rejected):\n'
                '    pass\n'
                'def test_call():\n'
                f'    raise ValueError({SENTINEL!r})\n'
                f'{SENTINEL} = type({SENTINEL!r}, (Exception,), {{}})\n'
                'def test_custom():\n'
                f'    raise {SENTINEL}({SENTINEL!r})\n')
            environment = {
                'PATH': os.defpath, 'HOME': directory, 'LANG': 'C.UTF-8',
                'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
                'PYTHONPATH': str(SCRIPTS), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                'PYTHONDONTWRITEBYTECODE': '1', 'MTG_CI_EVIDENCE': str(evidence),
                'MTG_ISOLATED_TEST_ROOT': str(source),
            }
            for args in (('init', '-q'), ('add', '.'),
                         ('-c', 'commit.gpgsign=false', 'commit', '-qm', 'public diagnostic fixture')):
                subprocess.run(['git', '-C', str(source), *args], env=environment,
                               check=True, capture_output=True)
            commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                             env=environment, text=True).strip()
            result = subprocess.run(
                [sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                 '-p', 'ci_backend_evidence', str(tests)], cwd=source, env=environment,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertIn(SENTINEL, result.stdout)
            signature_text = (evidence / 'failure-signatures.jsonl').read_text()
            self.assertNotIn(SENTINEL, signature_text)
            signatures = [json.loads(line) for line in signature_text.splitlines()]
            self.assertEqual(len(signatures), 3)
            self.assertEqual({row['signature']['exception'] for row in signatures},
                             {'PermissionError', 'ValueError', 'Other'})
            self.assertEqual({row['phase'] for row in signatures}, {'setup', 'call'})
            for row in signatures:
                self.assertTrue(row['signature']['frames'])
                for frame in row['signature']['frames']:
                    self.assertEqual(frame['path'], 'backend/tests/test_diagnostic.py')
                    self.assertEqual(frame['source_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            (evidence / 'source-head.txt').write_text(commit + '\n')
            (evidence / 'pytest-exit-code.txt').write_text('1\n')
            auditor = load('ci_backend_evidence')
            import contextlib
            import io
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(auditor.audit(evidence, 1), 0)
            (evidence / 'coverage.json').write_text(output.getvalue())
            metadata = load('ci_backend_metadata')
            self.assertEqual(metadata.EXCEPTION_CATEGORIES, auditor.EXCEPTION_CATEGORIES)
            document, status = metadata.build_metadata(evidence, source)
            self.assertEqual(status, 0)
            self.assertTrue(document['coverage']['all_collected_completed'])
            self.assertEqual(len(document['failures']), 3)
            self.assertNotIn(SENTINEL, json.dumps(document))
            self.assertTrue(all(row['diagnostic']['frames'] for row in document['failures']))


if __name__ == '__main__':
    unittest.main()
