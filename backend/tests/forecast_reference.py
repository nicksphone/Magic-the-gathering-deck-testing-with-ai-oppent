"""Frozen eager two-ply algorithm, retained for scalar/result parity."""
from __future__ import annotations
from ai.pending_effects import planning_copy

def eager_reference(self, state: MatchState, player_id: int, baseline_score: float | None = None) -> float:
    """Depth-limited stack planner for counter wars; only runs while stack is active."""
    stack_items = list(getattr(state, "stack", []) or [])
    if not stack_items or getattr(state, "winner", None) is not None:
        return 0.0
    pid = getattr(state, "priority_player", player_id)
    legal = self.engine.legal_moves(state, pid)
    if not legal:
        return 0.0
    top_actions = self._strategic_top_actions(state, legal, pid, limit=3)
    if not top_actions:
        return 0.0
    maximizing = pid == player_id
    best = -9999.0 if maximizing else 9999.0
    for act in top_actions:
        try:
            sim = planning_copy(state)
            self.engine.take_action(sim, pid, act, reject_invalid=True)
        except Exception:
            continue
        immediate = self._strategic_position_score(sim, player_id)
        if getattr(sim, "winner", None) is not None or not (getattr(sim, "stack", []) or []):
            val = immediate
        else:
            reply_pid = getattr(sim, "priority_player", pid)
            reply_legal = self.engine.legal_moves(sim, reply_pid)
            replies = self._strategic_top_actions(sim, reply_legal, reply_pid, limit=2)
            if not replies:
                val = immediate
            else:
                reply_vals: list[float] = []
                for rep in replies:
                    try:
                        nxt = planning_copy(sim)
                        self.engine.take_action(nxt, reply_pid, rep, reject_invalid=True)
                        reply_vals.append(self._strategic_position_score(nxt, player_id))
                    except Exception:
                        continue
                if not reply_vals:
                    val = immediate
                elif reply_pid == player_id:
                    val = max(reply_vals)
                else:
                    val = min(reply_vals)
        best = max(best, val) if maximizing else min(best, val)
    if best in {-9999.0, 9999.0}:
        return 0.0
    # The caller already scores this position. Add response improvement only,
    # not a second absolute score that rewards stacks while ahead and punishes
    # them while behind.
    baseline = self._strategic_position_score(state, player_id) if baseline_score is None else baseline_score
    return 0.2 * (best - baseline)

