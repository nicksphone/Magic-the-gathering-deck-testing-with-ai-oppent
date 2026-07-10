from __future__ import annotations

from analytics.service import AnalyticsService
from analytics.replay_tools import classify_first_divergence
from collections import Counter


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


def test_scan_log_tracks_stall_and_land_window_anomalies() -> None:
    repo = FakeRepo()
    svc = AnalyticsService(repo)
    out = Counter()
    top = Counter()
    svc._scan_log_for_anomalies(
        [
            "Player A passes priority.",
            "Player B passes priority.",
            "Player A passes priority.",
            "Player B passes priority.",
            "Missed land-play window for Player A.",
        ],
        out,
        top,
    )
    assert out["stall_pass_streaks"] == 1
    assert out["missed_land_windows"] == 1


def test_compare_replay_logs_reports_first_divergence() -> None:
    repo = FakeRepo()
    svc = AnalyticsService(repo)
    report = svc.compare_replay_logs(
        [
            "Turn 1.",
            "Player A plays Island.",
            'AI TRACE {"action":{"type":"cast_spell","card_name":"Lightning Bolt"}}',
        ],
        [
            "Turn 1.",
            "Player A plays Island.",
            'AI TRACE {"action":{"type":"pass_priority"}}',
        ],
    )

    assert report["category"] == "pass_vs_action"
    assert report["action_a"] == "cast_spell"
    assert report["action_b"] == "pass_priority"
    assert report["index"] == 2


def test_compare_replay_logs_labels_pass_vs_action_root_cause() -> None:
    repo = FakeRepo()
    svc = AnalyticsService(repo)
    report = svc.compare_replay_logs(
        [
            "Player A passes priority.",
            "Player A passes priority.",
        ],
        [
            "Player A passes priority.",
            "Player A casts/activates Memory Deluge.",
        ],
    )

    assert report["category"] == "pass_vs_action"
    assert report["action_a"] == "pass_priority"
    assert report["action_b"] == "cast_spell"


def test_compare_replay_logs_labels_cast_resolution_error() -> None:
    repo = FakeRepo()
    svc = AnalyticsService(repo)
    report = classify_first_divergence(
        {
            "index": 3,
            "a": "Invalid targets for Secure the Wastes: X value is required and must be non-negative.",
            "b": "Invalid targets for Secure the Wastes: X value is required and must be non-negative.",
            "context_before": [],
            "context_after_a": [],
            "context_after_b": [],
        }
    )

    assert report["category"] == "cast_resolution_error"
    assert report["action_a"] == "unknown"
    assert report["action_b"] == "unknown"


def test_extract_turn_summaries_reads_ai_trace_snapshots() -> None:
    summaries = AnalyticsService._extract_turn_summaries(
        [
            'AI TRACE {"turn":2,"pid":1,"step":"precombat_main","hand":["Island"],"battlefield":[{"id":"c1"}],"opp_battlefield":[{"id":"c2"}],"life":{"self":18,"opp":16},"mana_pool":{"U":1},"action":{"type":"cast_spell","card_name":"Counterspell"},"reasoning":"Hold up interaction"}',
            'AI TRACE {"turn":2,"pid":1,"step":"precombat_main","hand":["Island"],"battlefield":[{"id":"c1"}],"opp_battlefield":[{"id":"c2"}],"life":{"self":18,"opp":16},"mana_pool":{"U":1},"action":{"type":"pass_priority"},"reasoning":"same turn duplicate"}',
            'AI TRACE {"turn":3,"pid":2,"step":"declare_attackers","hand":[],"battlefield":[{"id":"c3"},{"id":"c4"}],"opp_battlefield":[{"id":"c1"}],"life":{"self":14,"opp":12},"mana_pool":{},"action":{"type":"attack","card_name":"Goblin Guide"},"reasoning":"Push damage"}',
        ]
    )

    assert len(summaries) == 2
    assert summaries[0]["turn"] == 2
    assert summaries[0]["action_type"] == "cast_spell"
    assert summaries[0]["battlefield_size"] == 1
    assert summaries[1]["turn"] == 3
    assert summaries[1]["opp_battlefield_size"] == 1
