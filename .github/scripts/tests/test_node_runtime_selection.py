"""Pin hosted browser/frontend runtimes without changing their test scopes."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]


class NodeRuntimeSelectionTests(unittest.TestCase):
    def test_hosted_workflows_pin_the_exact_node_release(self):
        selectors = {
            "ci.yml": 2,
            "native-browser.yml": 1,
            "browser-recovery-localization.yml": 1,
            "browser-owned-closeout-localization.yml": 1,
            "native-runtime-portability-localization.yml": 1,
        }
        for name, count in selectors.items():
            with self.subTest(workflow=name):
                workflow = (ROOT / ".github/workflows" / name).read_text()
                self.assertEqual(
                    re.findall(r"^          node-version: '([^']+)'$", workflow, re.MULTILINE),
                    ["24.22.0"] * count,
                )

    def test_current_setup_requirements_match_the_pinned_release(self):
        self.assertIn(
            "Use Python 3.12 and Node 24.22.0; hosted workflows pin this exact Node release.",
            (ROOT / "README.md").read_text(),
        )
        self.assertIn(
            "Node 24.22.0 with built-in WebSocket",
            (ROOT / "docs/testing/human-actions-browser.md").read_text(),
        )


if __name__ == "__main__":
    unittest.main()
