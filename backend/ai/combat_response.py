"""Bounded response comparisons from declared combat and publicly announced effects."""
from rules_engine.type_effects import effective_types
from ai.heuristics import evaluate_board
from ai.pending_effects import _projection_copy, _settle_announced_stack, planning_copy
from game_state.state import MatchState, Step


def response_outcome(agent, state, player_id, action):
    projected = _projection_copy(state)
    projected.replacement_choice_required = True
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    public = {cid for player in state.players.values()
              for cid in player.battlefield + player.graveyard + player.exile}
    try:
        agent.engine.take_action(projected, player_id, action, reject_invalid=True)
        hands = {pid: tuple(player.hand) for pid, player in projected.players.items()}
        public.update(item.source_card_id for item in projected.stack)
        if not _settle_announced_stack(projected):
            return None
        if any(tuple(player.library) != libraries[pid]
               or tuple(player.hand[:len(hands[pid])]) != hands[pid]
               or any(cid not in public for cid in player.hand[len(hands[pid]):])
               for pid, player in projected.players.items()):
            return None
        after_effects = planning_copy(projected)
        if not agent._finish_combat_projection(projected, after_effects):
            return None
        if any(line.startswith('Oracle effect not inferred') for line in projected.log):
            return None
        return projected
    except (ValueError, KeyError):
        return None


def retained_value(agent, outcome, player_id):
    # Steady-state resource valuation, not a prediction of postcombat plays:
    # don't price temporary stats/keywords/control as permanent board gains.
    valued = planning_copy(outcome)
    agent.engine._clear_marked_damage(valued)
    agent.engine._revert_expired_control_changes(valued)
    agent.engine._revert_crew_vehicles(valued)
    hand = valued.players[player_id].hand
    me, opponent = valued.players[player_id], valued.players[3-player_id]
    return (evaluate_board(valued, player_id) - (me.life - opponent.life) * 1.6
            + life_value(me.life) - life_value(opponent.life) - len(hand) * 0.9
            + sum(agent._hand_retention_value(valued, cid, player_id) for cid in hand) * 0.45)


def life_value(life):
    # Utility, not a rules change: scarce life matters more than surplus life.
    return (min(max(life, 0), 5) * 2 + min(max(life - 5, 0), 5)
            + min(max(life - 10, 0), 10) * 0.35 + max(life - 20, 0) * 0.1)


def choose_response(agent, state, legal_moves, player_id):
    if not isinstance(state, MatchState) or agent.difficulty not in {'master', 'master_plus'}:
        return None
    between_strikes = (state.step == Step.COMBAT_DAMAGE and state.combat_damage_stage == 'first'
                       and not state.combat_damage_resolved)
    declared = state.step == Step.DECLARE_BLOCKERS and state.blockers_declared
    if not (between_strikes or declared) or state.pregame_pending:
        return None
    # The existing setup planner covers unanswered attacking-seat lethal lines.
    if state.active_player == player_id and not state.stack and not between_strikes:
        return None
    candidates = [move for move in legal_moves if move.get('type') in {'cast_spell', 'activate_ability'}]
    if not candidates or len(candidates) > 16:
        return None
    if sum('Creature' in effective_types(state, state.cards[cid]) for player in state.players.values()
           for cid in player.battlefield) > 6:
        return None
    actions = []
    for move in candidates:
        actions.extend(agent._combat_target_actions(state, move, player_id))
        if len(actions) > 64:
            return None
    passing = {'type': 'pass_priority'}
    baseline = response_outcome(agent, state, player_id, passing)
    if baseline is None:
        return None
    if baseline.winner == player_id:
        return passing

    def score(outcome):
        result = 1 if outcome.winner == player_id else -1 if outcome.winner is not None else 0
        return result, retained_value(agent, outcome, player_id)

    best_score = score(baseline)
    best = passing
    unknown = False
    for action in actions:
        outcome = response_outcome(agent, state, player_id, action)
        if outcome is None:
            unknown = True
            continue
        value = score(outcome)
        if value[0] > best_score[0] or value[0] == best_score[0] and value[1] > best_score[1] + 0.25:
            best, best_score = action, value
    # Unknown alternatives still go to the ordinary planner, not an assertion
    # that passing is optimal. All projected wins remain conditional on responses.
    return None if unknown and best == passing else best
