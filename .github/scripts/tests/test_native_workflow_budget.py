"""The hosted job must outlive its unchanged native-service budget."""
from pathlib import Path
import re
import unittest


class NativeWorkflowBudgetTests(unittest.TestCase):
    def test_job_reserves_setup_and_cleanup_outside_the_native_service(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        launcher = (root / ".github/scripts/run-native-browser-ci.sh").read_text()
        jobs = re.findall(r"^    timeout-minutes: (\d+)$", workflow, re.MULTILINE)
        self.assertEqual(jobs, ["60"])
        self.assertIn("--property=RuntimeMaxSec=2700s", launcher)
        self.assertIn("--property=TimeoutStopSec=15s", launcher)
        self.assertEqual(int(jobs[0]) * 60 - 2700, 900)


if __name__ == "__main__":
    unittest.main()
