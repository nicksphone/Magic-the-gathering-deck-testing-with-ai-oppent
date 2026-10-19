"""The finite CI admission stanza preserves full merge/main/tag gates."""
from pathlib import Path
import unittest


class TriggerPolicyTests(unittest.TestCase):
    def test_full_ci_runs_once_for_pr_updates_and_still_runs_for_main_and_tags(self):
        workflow = (Path(__file__).resolve().parents[2] / "workflows/ci.yml").read_text()
        sections = workflow.split("\non:\n")
        self.assertEqual(len(sections), 2)
        events = sections[1].split("\npermissions:\n", 1)[0]
        self.assertEqual(events, (
            "  push:\n"
            "    branches: [main]\n"
            "    tags: ['**']\n"
            "  pull_request:\n"
        ))
