from __future__ import annotations

from scripts.anomaly_cluster_report import classify


def test_classify_detects_land_drop_miss() -> None:
    labels = classify(["Player A plays Island."])
    assert "land_miss" in labels


def test_classify_detects_multiword_land_drop_miss() -> None:
    labels = classify(["Player A plays Hallowed Fountain."])
    assert "land_miss" in labels


def test_classify_detects_ward_tax_and_invalid_targets() -> None:
    labels = classify(
        [
            "Invalid targets for Secure the Wastes: X value is required and must be non-negative.",
            "Ward tax paid.",
        ]
    )
    assert "cannot_pay" in labels or "invalid_targets" in labels
    assert "ward_tax" in labels


def test_classify_detects_main_phase_pass_loop_from_ai_traces() -> None:
    labels = classify(
        [
            'AI TRACE {"step":"Step.PRECOMBAT_MAIN","action":{"type":"pass_priority"}}',
            'AI TRACE {"step":"Step.PRECOMBAT_MAIN","action":{"type":"pass_priority"}}',
        ]
    )
    assert "main_phase_pass_loop" in labels
