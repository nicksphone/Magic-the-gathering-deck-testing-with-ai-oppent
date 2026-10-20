"""Require the reviewed browser regressions in the real npm test scripts."""
import json
from pathlib import Path
import shlex
import unittest


class BrowserRequestStateScheduleTests(unittest.TestCase):
    def test_native_browser_runs_request_state_module_exactly_once(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))
        argv = shlex.split(package['scripts']['test:unit:native-browser'])
        self.assertEqual(argv[:2], ['node', '--test'])
        self.assertEqual(argv[2:].count(
            'tests/browser-response-drop-request-state.test.mjs'), 1)

    def test_firefox_runs_owned_process_group_closure_module_exactly_once(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))
        argv = shlex.split(package['scripts']['test:unit:firefox'])
        self.assertEqual(argv[:2], ['node', '--test'])
        self.assertEqual(argv[2:].count(
            'tests/release-owned/owned-process-group-closure.test.mjs'), 1)


if __name__ == '__main__':
    unittest.main()
