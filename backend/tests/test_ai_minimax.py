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


def test_ranking_rollout_materializes_targeted_candidate(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=678)
    agent = AIAgent(difficulty="master", archetype="Midrange")

    def take_action(sim, _player_id, action):
        if action.get("targets") != {"target_player": 2}:
            raise ValueError("Target choice required")
        sim.players[2].life -= 5

    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent.engine, "legal_moves", lambda _sim, _pid: [])
    monkeypatch.setattr(agent, "_materialize_action", lambda _sim, move, _pid: {
        **move, "targets": {"target_player": 2},
    })
    monkeypatch.setattr(agent, "_approximate_resolution_for_creature_cast", lambda *_: None)
    monkeypatch.setattr(agent, "_approximate_resolution_for_ramp_spell", lambda *_: None)
    monkeypatch.setattr(agent, "_approximate_resolution_for_activated_action", lambda *_: None)
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life - sim.players[2].life))

    assert agent._simulate_delta(state, {"type": "cast_spell"}, 1) == 3.5


def test_ranking_rollout_materializes_targeted_opponent_reply(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=679)
    agent = AIAgent(difficulty="master", archetype="Midrange")

    def take_action(sim, _player_id, action):
        if action.get("targets") != {"target_player": 1}:
            raise ValueError("Target choice required")
        sim.players[1].life -= 5

    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent, "_materialize_action", lambda _sim, move, _pid: {
        **move, "targets": {"target_player": 1},
    })
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life - sim.players[2].life))

    assert agent._best_reply_delta(state, [{"type": "cast_spell"}], 1, 2) == 5.0


def test_strategic_beam_uses_ranked_reply_beyond_lexical_prefix(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=680)
    agent = AIAgent(difficulty="master", archetype="Midrange")
    replies = [
        {"type": "activate_ability", "ability_label": f"option {index}"}
        for index in range(6)
    ] + [{"type": "cast_spell", "branch": "punish"}]

    def take_action(sim, _player_id, action):
        if action.get("branch") == "root":
            sim.priority_player = 2
        elif action.get("branch") == "punish":
            sim.players[1].life -= 5

    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent.engine, "legal_moves", lambda _sim, _pid: replies)
    monkeypatch.setattr(agent, "_rank_moves", lambda _sim, moves, _pid, *, shallow=False: sorted(
        moves, key=lambda move: move.get("branch") == "punish", reverse=True,
    ))
    monkeypatch.setattr(agent, "_materialize_action", lambda _sim, move, _pid: move)
    monkeypatch.setattr(agent, "_strategic_features", lambda _sim, _pid: 0.0)
    monkeypatch.setattr(agent, "_stack_two_ply_value", lambda _sim, _pid: 0.0)
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life))

    assert agent._strategic_line_score(state, {"type": "pass_priority", "branch": "root"}, 1, depth=1) == 18.0


def test_ranking_reply_beam_uses_ranked_move_beyond_lexical_prefix(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=681)
    agent = AIAgent(difficulty="master", archetype="Midrange")
    replies = [
        {"type": "activate_ability", "ability_label": f"option {index}"}
        for index in range(8)
    ] + [{"type": "cast_spell", "branch": "punish"}]

    def take_action(sim, _player_id, action):
        if action.get("branch") == "punish":
            sim.players[1].life -= 5

    monkeypatch.setattr(agent.engine, "take_action", take_action)
    monkeypatch.setattr(agent, "_rank_moves", lambda _sim, moves, _pid, *, shallow=False: sorted(
        moves, key=lambda move: move.get("branch") == "punish", reverse=True,
    ))
    monkeypatch.setattr(agent, "_materialize_action", lambda _sim, move, _pid: move)
    monkeypatch.setattr("ai.agent.evaluate_board", lambda sim, _pid: float(sim.players[1].life))

    assert agent._best_reply_delta(state, replies, 1, 2) == 5.0


def test_shallow_reply_ranking_does_not_start_nested_rollout(monkeypatch):
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck, seed=682)
    agent = AIAgent(difficulty="master", archetype="Midrange")

    def fail_if_called(*_args):
        raise AssertionError("Shallow ranking must not start another rollout")

    monkeypatch.setattr(agent, "_simulate_delta", fail_if_called)

    assert agent._rank_moves(state, [{"type": "pass_priority"}], 1, shallow=True)
