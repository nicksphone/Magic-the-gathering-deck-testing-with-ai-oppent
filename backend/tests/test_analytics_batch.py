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
    assert [row["deck_a_on_play"] for row in out1["game_results"]] == [True, False]


def test_batch_exposes_first_divergence_report() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    calls: list[tuple[list[str], list[str]]] = []

    def compare(left_log: list[str], right_log: list[str]) -> dict:
        calls.append((left_log, right_log))
        return {"category": "mock", "index": 9}

    service.compare_replay_logs = compare  # type: ignore[method-assign]
    deck_a = [{"quantity": 60, "card_name": "Island"}]
    deck_b = [{"quantity": 60, "card_name": "Swamp"}]
    out = service.run_batch(deck_a, deck_b, matches=2, difficulty="master", max_ticks=1)
    assert calls
    assert out["first_divergence"] == {"category": "mock", "index": 9}


def test_batch_exposes_first_divergence_excerpt() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    excerpt = service._first_divergence_excerpt(
        ["Turn 1.", "Player A plays Island.", "Player A passes priority."],
        ["Turn 1.", "Player A plays Island.", "Player A casts Lightning Bolt."],
    )

    assert excerpt["index"] == 2
    assert excerpt["category"] == "pass_vs_action"
    assert excerpt["line_a"] == "Player A passes priority."
    assert excerpt["line_b"] == "Player A casts Lightning Bolt."


def test_batch_first_divergence_excerpt_includes_trace_context() -> None:
    repo = _DummyRepo()
    service = AnalyticsService(repo)  # type: ignore[arg-type]
    excerpt = service._first_divergence_excerpt(
        [
            'AI TRACE {"pid":1,"turn":4,"step":"precombat_main","hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"cast_spell","card_name":"Counterspell"}}'
        ],
        [
            'AI TRACE {"pid":1,"turn":4,"step":"precombat_main","hand":["Counterspell"],"opp_hand":["Threat"],"battlefield":[{"id":"c1","types":["Land"]}],"opp_battlefield":[{"id":"c2","types":["Creature"]}],"life":{"self":16,"opp":12},"legal_non_pass":true,"legal_has_land":false,"action":{"type":"pass_priority"}}'
        ],
    )

    assert excerpt["trace_context_a"]["hand_size"] == 1
    assert excerpt["trace_context_a"]["opp_hand_size"] == 1
    assert excerpt["trace_context_b"]["action_type"] == "pass_priority"
