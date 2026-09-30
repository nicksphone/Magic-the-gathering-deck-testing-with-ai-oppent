from unittest.mock import patch

import pytest

from game_state.state import MatchFactory
from rules_engine.engine import RulesEngine
from ai.agent import AIAgent
from scripts import profile_ai_match as profiler


def test_latency_percentiles_and_diagnostic_target_do_not_invent_empty_samples():
    assert profiler.latency_summary([], 1)["p95_seconds"] is None
    summary = profiler.latency_summary([{"seconds": x / 100} for x in range(1, 101)], .95)
    assert summary == {"decisions": 100, "target_seconds": .95, "over_target": 5,
                       "p50_seconds": .5, "p95_seconds": .95, "p99_seconds": .99, "max_seconds": 1}


@pytest.mark.parametrize("target", [0, -1, float("inf"), float("nan")])
def test_invalid_latency_targets_are_rejected(target):
    with pytest.raises(ValueError):
        profiler.latency_summary([], target)


def test_profiler_preserves_decision_and_restores_agent_without_hand_output(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=111)
    moves = RulesEngine().legal_moves(state, 1)
    original = AIAgent.choose_action
    expected = AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, 1)
    def game(*args, **kwargs):
        observed = AIAgent(difficulty="master", archetype="Control").choose_action(state, moves, 1)
        assert observed == expected
        return {"winner": 1, "timeout": False, "log": ["PRIVATE HAND"], "ticks": 1}
    monkeypatch.setattr(profiler, "run_game", game)
    with patch.object(profiler, "perf_counter", side_effect=[0, 2]):
        result = profiler.profile_game(deck, deck, 111, target_seconds=1)
    assert AIAgent.choose_action is original
    assert result["latency"]["over_target"] == 1
    assert result["game"]["winner"] == 1
    assert "log" not in result["game"]
    assert not {"hand", "card_name", "card_id"}.intersection(result["decisions"][0])
    def failure(*args, **kwargs):
        raise RuntimeError("interrupted")
    monkeypatch.setattr(profiler, "run_game", failure)
    with pytest.raises(RuntimeError):
        profiler.profile_game(deck, deck, 111)
    assert AIAgent.choose_action is original
