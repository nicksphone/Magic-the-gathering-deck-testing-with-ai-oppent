"""Bounded current-turn damage finishes, conditional on opposing passes."""
from copy import deepcopy

from ai.pending_effects import (UncertainSimulation, planning_copy,
                                settled_public_position, simulation_checked_action)
from game_state.state import MatchState, Step
from rules_engine.action_validation import ActionRejected
from rules_engine.engine import RulesEngine


def winning_damage_action(agent, state, legal_moves, player_id):
    """Return a checked winning prefix, not a promise of unopposed play."""
    if (not isinstance(state, MatchState) or state.winner is not None
            or state.pregame_pending or state.active_player != player_id
            or state.priority_player != player_id
            or state.step not in {Step.PRECOMBAT_MAIN, Step.POSTCOMBAT_MAIN}
            or state.pending_mechanic_choice or state.pending_replacement_choice
            or state.pending_trigger_order
            or any(item.controller != player_id for item in state.stack)):
        return None
    from ai.agent import _card_for_move, _oracle_text

    opponent = 3 - player_id
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opposing_hand = tuple(state.players[opponent].hand)
    rules = RulesEngine()
    remaining = 24

    def settle(projected):
        # Settlement drops diagnostic history; reject cast/cost gaps before that copy.
        if any(line.startswith('Oracle effect not inferred') for line in projected.log):
            return None
        result = settled_public_position(projected, player_id)
        if result is None:
            return None
        if (result.turn != state.turn or result.step != state.step
                or any(tuple(player.library) != libraries[pid] for pid, player in result.players.items())
                or tuple(result.players[opponent].hand) != opposing_hand
                or any(line.startswith('Oracle effect not inferred') for line in result.log)):
            return None
        return result

    def offers(node, moves):
        candidates, maximum = [], {}
        for move in moves:
            if move.get('type') != 'cast_spell' or move.get('card_id') not in node.players[player_id].hand:
                continue
            card = _card_for_move(node, move)
            if card is None or not {'Instant', 'Sorcery'}.intersection(card.types):
                continue
            estimate = agent._burn_damage_estimate(_oracle_text(card))
            if estimate > 0:
                candidates.append((move, card))
                maximum[move['card_id']] = max(estimate, maximum.get(move['card_id'], 0))
        # This cheap fixed-damage gate can miss exotic finishes; it never proves a win.
        if sum(sorted(maximum.values(), reverse=True)[:3]) < node.players[opponent].life:
            return []
        result = []
        for move, card in candidates[:8]:
            action = deepcopy(agent._materialize_action(node, move, player_id))
            if action.get('_invalid_ai_choice'):
                continue
            targets = dict(action.get('targets') or {})
            for key in ('target_card_id', 'target_card_ids', 'target_stack_id',
                        'target_distribution', 'mode_targets'):
                targets.pop(key, None)
            targets['target_player'] = opponent
            action['targets'] = targets
            # Compound spells are checked by actual execution, not an effect-key whitelist.
            result.append(action)
        return result

    def search(node, depth, moves=None):
        nonlocal remaining
        if node.winner is not None or remaining <= 0 or node.priority_player != player_id:
            return None
        actions = offers(node, moves if moves is not None else rules.legal_moves(node, player_id))
        for action in actions:
            if remaining <= 0:
                break
            remaining -= 1
            try:
                projected = simulation_checked_action(node, rules, player_id, action)
                projected = settle(projected)
            except (ActionRejected, UncertainSimulation):
                continue
            if projected is None:
                continue
            if projected.winner == player_id:
                return action
            if depth > 1 and projected.winner is None and search(projected, depth - 1) is not None:
                return action
        return None

    try:
        projected = settle(planning_copy(state))
        if projected is None:
            return None
        if state.stack and projected.winner == player_id:
            return {'type': 'pass_priority'}
        action = search(projected, 3, None if state.stack else legal_moves)
        return {'type': 'pass_priority'} if action is not None and state.stack else action
    except (ActionRejected, UncertainSimulation):
        return None
