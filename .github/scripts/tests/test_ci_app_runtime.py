"""Installer protocol controls: Python/pip are mocked; no packages are installed."""
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / '.github/scripts/install-ci-app-runtime.sh'
FAKE_PYTHON = '''#!/usr/bin/bash
set -eu
printf '%s\\n' "$*" >> "$CALL_LOG"
step="$2"
if [[ "$step" == "$FAIL_STEP" ]]; then exit 23; fi
if [[ "$step" == venv ]]; then
  mkdir -p "$3/bin"
  cp "$0" "$3/bin/python"
  chmod 700 "$3/bin/python"
fi
'''


class AppRuntimeTests(unittest.TestCase):
    def test_all_python_fixture_jobs_use_the_existing_locked_closure(self):
        source = (ROOT / '.github/workflows/ci.yml').read_text()
        sections = [source.split('\n  frontend:\n', 1)[1].split('\n  browser:\n', 1)[0],
                    source.split('\n  browser:\n', 1)[1],
                    (ROOT / '.github/workflows/browser-recovery-localization.yml').read_text()]
        for section in sections:
            self.assertIn("python-version: '3.12.3'", section)
            self.assertIn('runs-on: ubuntu-24.04', section)
            self.assertIn('bash .github/scripts/install-ci-app-runtime.sh', section)
            self.assertNotIn('pip install -r backend/requirements.txt', section)

    def test_installer_orders_admission_and_exports_only_after_success(self):
        self.assertTrue(INSTALLER.is_file(), 'Shared locked-runtime installer is absent')
        for fail in ('', 'platform', 'venv', 'pip', 'runtime', 'existing', 'dangling'):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory(prefix='mtg-ci-runtime-control-') as temp:
                root = Path(temp)
                (root / 'bin').mkdir()
                fake = root / 'bin/python'
                fake.write_text(FAKE_PYTHON)
                fake.chmod(0o700)
                export = root / 'GITHUB_PATH'
                log = root / 'calls'
                runtime = root / 'runtime'
                runtime.mkdir()
                if fail == 'existing':
                    (runtime / 'ci-app-backend').mkdir()
                elif fail == 'dangling':
                    (runtime / 'ci-app-backend').symlink_to(root / 'missing')
                result = subprocess.run(['/usr/bin/bash', str(INSTALLER)], cwd=ROOT,
                    env={'PATH': str(root / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8',
                         'HOME': str(root), 'RUNNER_TEMP': str(runtime), 'GITHUB_PATH': str(export),
                         'CALL_LOG': str(log), 'FAIL_STEP': fail},
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2 if fail in ('existing', 'dangling') else 23 if fail else 0, result.stderr)
                if fail in ('existing', 'dangling'):
                    self.assertFalse(log.exists())
                    self.assertFalse(export.exists())
                    continue
                calls = log.read_text().splitlines()
                self.assertIn('ci_backend_shards.py platform', calls[0])
                if fail:
                    self.assertFalse(export.exists(), 'Failed setup must not publish an interpreter')
                    self.assertEqual(len(calls), ('platform', 'venv', 'pip', 'runtime').index(fail) + 1)
                else:
                    self.assertEqual(len(calls), 4)
                    self.assertIn('--require-hashes --only-binary=:all: --no-cache-dir', calls[2])
                    self.assertIn('backend/requirements-py312-linux.lock', calls[2])
                    self.assertIn('ci_backend_shards.py runtime', calls[3])
                    self.assertEqual(export.read_text(), str(runtime / 'ci-app-backend/bin') + '\n')


if __name__ == '__main__':
    unittest.main()
