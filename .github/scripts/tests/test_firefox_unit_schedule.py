"""Keep the existing Firefox protocol cohort and both bootstrap regressions."""
import json
from pathlib import Path
import shlex
import unittest


class FirefoxUnitScheduleTests(unittest.TestCase):
    def test_original_four_and_new_bootstrap_modules_run_once_in_the_normal_script(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / 'frontend/package.json').read_text())
        self.assertEqual(shlex.split(package['scripts']['test:unit:firefox']), [
            'node', '--test',
            'tests/firefox-driver-contract.test.mjs',
            'tests/firefox-transport.test.mjs',
            'tests/firefox-fetch-collector.test.mjs',
            'tests/firefox-runtime-observer.test.mjs',
            'tests/firefox-disabled-bootstrap.test.mjs',
            'tests/firefox-bootstrap-failure-cleanup.test.mjs',
            'tests/firefox-release-owned-launcher-contract.test.mjs',
            'tests/firefox-launcher-listener-readiness.test.mjs',
            'tests/release-owned/public-storage-owner-rename-budget.test.mjs',
            'tests/release-owned/owned-process-group-closure.test.mjs',
        ])


if __name__ == '__main__':
    unittest.main()
