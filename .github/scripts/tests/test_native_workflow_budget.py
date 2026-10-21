"""The hosted job must outlive its unchanged native-service budget."""
from pathlib import Path
import re
import unittest


class NativeWorkflowBudgetTests(unittest.TestCase):
    def test_browser_jobs_use_the_exact_qualified_python_release(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        self.assertEqual(
            re.findall(r"^          python-version: '([^']+)'$", workflow, re.MULTILINE),
            ["3.12.3"],
        )

    def test_browser_jobs_install_the_existing_hashed_application_closure(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/native-browser.yml").read_text()
        install = workflow.split("      - name: Install app dependencies\n", 1)[1].split("      - name:", 1)[0]
        self.assertIn("bash .github/scripts/install-ci-app-runtime.sh", install)
        self.assertIn("npm --prefix frontend ci", install)
        self.assertNotIn("pip install -r backend/requirements.txt", install)

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
