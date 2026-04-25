from __future__ import annotations

from analytics.service import AnalyticsService


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[tuple[str, dict]] = []

    def save_snapshot(self, label: str, stats: dict) -> None:
        self.saved.append((label, stats))


def test_ai_diagnostics_reports_matchup_metrics() -> None:
    repo = FakeRepo()
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    result = AnalyticsService(repo).run_ai_diagnostics(
        deck_pool=[
            {"name": "Diag A", "mainboard": deck_a},
            {"name": "Diag B", "mainboard": deck_b},
        ],
        matches_per_pair=1,
        difficulty="strong",
        max_ticks=400,
    )

    assert result["deck_count"] == 2
    assert result["pairs_tested"] == 1
    assert result["games"] == 1
    assert "global_anomalies" in result
    assert "suspicious_matchups" in result
    assert len(result["suspicious_matchups"]) == 1
    assert repo.saved and repo.saved[0][0] == "ai_diagnostics"
