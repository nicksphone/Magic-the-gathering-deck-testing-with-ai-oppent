"""Bounded public-outcome comparison for independent creature modifiers."""
from itertools import product

from ai.heuristics import evaluate_board
from ai.pending_effects import _projection_copy, _settle_announced_stack
from rules_engine.action_validation import ActionRejected, checked_action


def choose_modifier_targets(agent, state, player_id, action, targets, candidates, count):
    ids = [candidate['id'] for candidate in candidates]
    if not ids:
        return None
    from rules_engine.ordered_targets import ordered_creature_modifiers
    card = state.cards.get(action.get('card_id'))
    modifiers = ordered_creature_modifiers(card.oracle_text) if card else None
    # Unknown continuations still use public benefit/harm, never candidate order.
    fallback = []
    for index in range(count):
        modifier = modifiers[index] if modifiers and index < len(modifiers) else None
        preferred = None
        if modifier:
            power, toughness = modifier['power'], modifier['toughness']
            if power <= 0 and toughness <= 0:
                preferred = 3-player_id
            elif power >= 0 and toughness >= 0:
                preferred = player_id
        fallback.append(max(ids, key=lambda cid: (
            state.cards[cid].controller == preferred,
            agent._creature_threat_score(state, cid, player_id), cid)))
    if count != 2:
        return fallback
    # ponytail: six public candidates, 36 assignments; wider targeting needs a beam.
    ids = sorted(ids, key=lambda cid: (agent._creature_threat_score(state, cid, player_id), cid), reverse=True)[:6]
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opposing_hand = tuple(state.players[3-player_id].hand)
    scored = []
    for assignment in product(ids, repeat=count):
        selected = {key: value for key, value in targets.items() if key != 'target_card_id'}
        selected['target_card_ids'] = list(assignment)
        try:
            projected = checked_action(_projection_copy(state), agent.engine, player_id,
                                       {**action, 'targets': selected})
            if not _settle_announced_stack(projected):
                continue
        except ActionRejected:
            continue
        if (any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
                or tuple(projected.players[3-player_id].hand) != opposing_hand):
            continue
        score = (1000 if projected.winner == player_id else -1000) if projected.winner is not None else evaluate_board(projected, player_id)
        scored.append((score, assignment))
    return list(max(scored)[1]) if scored else fallback
