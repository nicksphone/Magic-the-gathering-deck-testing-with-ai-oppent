# SPDX-License-Identifier: GPL-3.0-or-later
# Original compatibility checks for Card-Forge, pinned by NativeSaveAudit.java.
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare


class PositionComparisonTest(unittest.TestCase):
    def setUp(self):
        self.facts = {"players": [{"life": 20, "zones": {
            "Library": ["Mountain", "Lightning Bolt"], "Hand": []}}],
            "pending_stack": [], "turn": 2, "phase": "MAIN1"}

    def test_exact_settled_position_passes(self):
        self.assertTrue(compare(self.facts, copy.deepcopy(self.facts))["strict_full_position_equal"])

    def test_pending_stack_loss_is_not_a_success(self):
        before = copy.deepcopy(self.facts)
        before["pending_stack"] = [{"spell": "Lightning Bolt", "target_seat": 1}]
        result = compare(before, self.facts)
        self.assertFalse(result["strict_full_position_equal"])
        self.assertFalse(result["pending_stack_equal"])
        self.assertEqual(result["different_fields"], ["pending_stack"])

    def test_library_order_is_not_normalized_away(self):
        after = copy.deepcopy(self.facts)
        after["players"][0]["zones"]["Library"].reverse()
        self.assertFalse(compare(self.facts, after)["strict_full_position_equal"])


if __name__ == "__main__":
    unittest.main()
