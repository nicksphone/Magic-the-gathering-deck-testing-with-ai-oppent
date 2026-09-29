"""Tactical search must account for an opponent's best reply."""

import pytest

from ai.agent import AIAgent
from game_state.state import MatchFactory


@pytest.mark.parametrize("next_actor,expected", [(1, 20.0), (2, 18.0)])
def test_strategic_search_selects_best_own_or_worst_opponent_reply(monkeypatch, next_actor, expected):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=676)
    agent = AIAgent(difficulty="master", archetype="Midrange")

    def take_action(sim, _player_id, action):
        if action.get("branch") == "root":
            sim.priority_player = next_actor
        elif action.get("branch") == "punish":
            sim.players[1].life -= 5

    replies = [
        {"type": "pass_priority", "branch": "safe"},
        {"type": "pass_priority", "branch": "punish"},
    ]
    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent.engine, "legal_moves", lambda _sim, _pid: replies)
    monkeypatch.setattr(agent, "_strategic_features", lambda _sim, _pid: 0.0)
    monkeypatch.setattr(agent, "_stack_two_ply_value", lambda _sim, _pid: 0.0)
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life))

    result = agent._strategic_line_score(state, {"type": "pass_priority", "branch": "root"}, 1, depth=1)

    assert result == expected


def test_strategic_search_materializes_targeted_opponent_reply(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=677)
    agent = AIAgent(difficulty="master", archetype="Midrange")

    def take_action(sim, _player_id, action):
        if action.get("branch") == "root":
            sim.priority_player = 2
        elif action.get("branch") == "punish":
            if action.get("targets") != {"target_player": 1}:
                raise ValueError("Target choice required")
            sim.players[1].life -= 5

    replies = [
        {"type": "pass_priority", "branch": "safe"},
        {"type": "cast_spell", "branch": "punish"},
    ]
    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent.engine, "legal_moves", lambda _sim, _pid: replies)
    monkeypatch.setattr(agent, "_materialize_action", lambda _sim, move, _pid: (
        {**move, "targets": {"target_player": 1}} if move.get("branch") == "punish" else move
    ))
    monkeypatch.setattr(agent, "_strategic_features", lambda _sim, _pid: 0.0)
    monkeypatch.setattr(agent, "_stack_two_ply_value", lambda _sim, _pid: 0.0)
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life))

    result = agent._strategic_line_score(state, {"type": "pass_priority", "branch": "root"}, 1, depth=1)

    assert result == 18.0
