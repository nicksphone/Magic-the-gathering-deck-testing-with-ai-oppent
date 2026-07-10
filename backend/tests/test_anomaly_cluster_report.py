from __future__ import annotations

from scripts.anomaly_cluster_report import classify


def test_classify_detects_land_drop_miss() -> None:
    labels = classify(["Player A plays Island."])
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
