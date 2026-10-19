"""Run the new bounded diagnostic regressions in the unchanged npm pipeline."""
import json
from pathlib import Path
import shlex
import unittest


class DropDiagnosticScheduleTests(unittest.TestCase):
    def test_original_native_modules_then_new_projection_run_once(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / 'frontend/package.json').read_text())
        self.assertEqual(shlex.split(package['scripts']['test:unit:native-browser']), [
            'node', '--test',
            'tests/browser-selection.test.mjs',
            'tests/browser-sandbox-flags.test.mjs',
            'tests/browser-vendor-preflight.test.mjs',
            'tests/native-browser-service.test.mjs',
            'tests/browser-driver-passive-cdp.mjs',
            'tests/browser-response-metadata.test.mjs',
            'tests/browser-start-recovery-diagnostics.test.mjs',
            'tests/browser-preflight-lifecycle-metadata.test.mjs',
            'tests/browser-start-recovery-post-response-contract.test.mjs',
            'tests/browser-v2-held-response-contract.test.mjs',
            'tests/browser-navigation-metadata.test.mjs',
            'tests/browser-cors-transport-diagnostic.test.mjs',
            'tests/browser-request-signal-diagnostics.test.mjs',
            'tests/entry-copy-controls.test.mjs',
            'tests/browser-start-signal-enrollment.test.mjs',
            'tests/browser-post-response-lifecycle.test.mjs',
            'tests/browser-fetch-causal-order.test.mjs',
            'tests/browser-response-drop-diagnostic.test.mjs',
        ])


if __name__ == '__main__':
    unittest.main()
