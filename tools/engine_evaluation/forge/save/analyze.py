# SPDX-License-Identifier: GPL-3.0-or-later
# Original post-execution analysis; Card-Forge native sources are unchanged.
# Does not change or replace the strict comparator or its preserved red results.
import copy
import json
from pathlib import Path
import sys


def placement(facts):
    facts = copy.deepcopy(facts)
    for player in facts["players"]:
        # The initial observer mistakenly used Object.toString(), not mana data.
        del player["mana_pool"]
        for cards in player["zones"].values():
            for card in cards:
                del card["sick"]
    return facts


def analyze(root):
    results = []
    for seat in (0, 1):
        episode = json.loads((root / f"export-seat{seat}/EPISODE.private.json").read_text())
        assert episode["mana_paid_by_native_cost_engine"] is True
        assert episode["native_resolution_damage"] == 3
        for stage in ("pending", "settled"):
            before = json.loads((root / f"export-seat{seat}/{stage}/facts.private.json").read_text())
            after = json.loads((root / f"restore-seat{seat}-{stage}/facts.private.json").read_text())
            expected_life = [20, 20]
            if stage == "settled":
                expected_life[1 - seat] = 17
            life_equal = [p["life"] for p in before["players"]] == [p["life"] for p in after["players"]] == expected_life
            libraries_equal = all(a["zones"]["Library"] == b["zones"]["Library"]
                                  for a, b in zip(placement(before)["players"], placement(after)["players"]))
            flags = []
            for i, (a, b) in enumerate(zip(before["players"], after["players"])):
                for zone in a["zones"]:
                    for index, (x, y) in enumerate(zip(a["zones"][zone], b["zones"][zone])):
                        if x["name"] == y["name"] and x["sick"] != y["sick"]:
                            flags.append({"seat": i, "zone": zone, "index": index,
                                          "name": x["name"], "before": x["sick"], "after": y["sick"]})
            result = {"seat": seat, "stage": stage, "life_exact": life_equal,
                      "library_names_order_owner_tap_face_exact": libraries_equal,
                      "placement_and_stack_projection_exact": placement(before) == placement(after),
                      "physical_cards_before": [p["physical_cards"] for p in before["players"]],
                      "physical_cards_after": [p["physical_cards"] for p in after["players"]],
                      "pending_stack_before": before["stack_count"], "pending_stack_after": after["stack_count"],
                      "pending_stack_exact": before["pending_stack"] == after["pending_stack"],
                      "sickness_flag_changes": flags, "full_save_qualified": False,
                      "mana_contents_comparison": "UNMEASURED_OBJECT_TOSTRING_IS_NOT_MANA_CONTENTS"}
            assert life_equal and libraries_equal, "Positive life/library compatibility control failed"
            if stage == "settled":
                assert result["placement_and_stack_projection_exact"], "Settled placement control failed"
                assert result["physical_cards_after"] == [60, 60]
            results.append(result)
    return {"status": "COMPONENT_CONTROLS_COMPLETE_FULL_SAVE_NOT_QUALIFIED", "results": results,
            "raw_strict_results_preserved": True, "pending_requirement_not_relaxed": True,
            "sickness_differences_not_normalized_out_of_full_save_claim": True,
            "projection_is_only_life_card_placement_library_order_tap_owner_face_and_stack": True,
            "not_a_rng_pending_dialog_controller_or_bo3_resume_test": True}


if __name__ == "__main__":
    root = Path(sys.argv[1])
    result = analyze(root)
    (root / "ANALYSIS.private.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for row in result["results"]:
        print(json.dumps({k: v for k, v in row.items() if k != "sickness_flag_changes"}, sort_keys=True))
