from __future__ import annotations

from analytics.service import AnalyticsService


class _DummyRepo:
    def save_snapshot(self, label: str, stats: dict) -> None:
        self.last = (label, stats)


def test_batch_does_not_auto_award_unresolved_games_to_deck_a() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    out = service.run_batch(deck_a, deck_b, matches=5, difficulty="master", max_ticks=1)
    assert out["win_rate_deck_a"] == 0
    assert out["win_rate_deck_b"] == 0
    assert out["timeouts"] == 5
    assert isinstance(out["sample_turn_summaries"], list)
    assert isinstance(out["sample_log_excerpt"], list)
    assert isinstance(out["game_results"], list)


def test_batch_is_deterministic_for_same_inputs() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    out1 = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    out2 = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    assert out1["deterministic_replay_fingerprint"] == out2["deterministic_replay_fingerprint"]
    assert out1["game_results"] == out2["game_results"]
