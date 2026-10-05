"""Bounded public life-event outcomes, including affected-player ordering."""
from effects.registry import resolve_effect
from ai.pending_effects import _projection_copy
from rules_engine.action_validation import ActionRejected, checked_action
from rules_engine.engine import RulesEngine
from rules_engine.replacement import replacement_options, player_cant_gain_life
from rules_engine.state_based_actions import apply_state_based_actions


def life_target_score(state, controller, target_player, amount):
    if amount <= 0:
        return None
    if player_cant_gain_life(state, target_player):
        return 0.0
    options = replacement_options(state, 'life_gain', target_player=target_player)
    if not options:
        return float(amount if target_player == controller else -amount)
    # A gain-to-draw replacement is an unknown private outcome, not a free peek.
    for option in options:
        text = (state.cards[option['source_id']].oracle_text or '').lower()
        if 'if you would gain life, draw that many cards instead' in text:
            return None
    projected = _projection_copy(state)
    if projected.pending_mechanic_choice:
        if projected.pending_mechanic_choice.get('kind') != 'copy_target':
            return None
        # This forecast supplies a hypothetical recipient, not a still-open choice.
        projected.pending_mechanic_choice = None
    if projected.pending_replacement_choice or projected.pending_trigger_order:
        return None
    projected.replacement_choice_required = True
    private = {pid: (tuple(p.library), tuple(p.hand)) for pid, p in state.players.items()}
    before = state.players[controller].life - state.players[3-controller].life
    budget = [16]

    def outcome(position, depth=0):
        if any((tuple(p.library), tuple(p.hand)) != private[pid]
               for pid, p in position.players.items()):
            return None
        pending = position.pending_replacement_choice
        if pending:
            if pending.get('resume_kind') != 'gain_event' or depth >= 8:
                return None
            scores = []
            for option in pending['options']:
                if budget[0] <= 0:
                    return None
                budget[0] -= 1
                branch = _projection_copy(position)
                try:
                    branch = checked_action(branch, RulesEngine(), pending['player_id'], {
                        'type': 'choose_replacement',
                        'replacement_source_id': option['source_id']})
                except ActionRejected:
                    return None
                score = outcome(branch, depth+1)
                if score is None:
                    return None
                scores.append(score)
            if not scores:
                return None
            return (max if pending['player_id'] == controller else min)(scores)
        apply_state_based_actions(position)
        own, enemy = position.players[controller].life, position.players[3-controller].life
        if position.winner is not None:
            if position.winner == 0:
                return 0.0
            return 1000.0 if position.winner == controller else -1000.0
        return float(own - enemy - before)

    resolve_effect(projected, controller, 'gain_life', {'target_player': target_player, 'amount': amount})
    return outcome(projected)
