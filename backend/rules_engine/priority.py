from __future__ import annotations

from game_state.state import MatchState


def pass_priority(state: MatchState, player_id: int) -> bool:
    if state.priority_player != player_id:
        return False
    state.passed_priority.add(player_id)
    opponent = 1 if player_id == 2 else 2
    if opponent in state.passed_priority:
        state.passed_priority = set()
        return True
    state.priority_player = opponent
    return False
