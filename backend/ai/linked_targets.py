"""Select complete controller-linked pairs using bounded public outcomes."""
from copy import deepcopy

from ai.heuristics import evaluate_board
from ai.pending_effects import _projection_copy, _settle_announced_stack
from rules_engine.action_validation import ActionRejected, checked_action


def choose_linked_pair(agent, state, player_id, action, hints):
    pairs = [pair for pair in hints['linked_target_pairs']
             if (pair['primary_id'] if pair['primary_kind'] == 'player'
                 else state.cards[pair['primary_id']].controller) != player_id]
    if not pairs:
        return None
    pairs.sort(key=lambda pair: (agent._creature_threat_score(state, pair['creature_id'], player_id),
                                str(pair['primary_id']), pair['creature_id']), reverse=True)
    # ponytail: evaluate at most 16 complete pairs; wider boards need a target beam.
    scored = []
    for index, pair in enumerate(pairs[:16]):
        projected = _projection_copy(state)
        libraries = {pid: tuple(player.library) for pid, player in projected.players.items()}
        opposing_hand = tuple(projected.players[3-player_id].hand)
        try:
            projected = checked_action(projected, agent.engine, player_id,
                                       {**action, 'targets': deepcopy(pair['targets'])})
            if not _settle_announced_stack(projected):
                continue
        except ActionRejected:
            continue
        if (any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
                or tuple(projected.players[3-player_id].hand) != opposing_hand):
            continue
        score = ((1000 if projected.winner == player_id else -1000) if projected.winner is not None
                 else evaluate_board(projected, player_id))
        scored.append((score, -index, pair))
    pair = max(scored, key=lambda item: item[:2])[2] if scored else pairs[0]
    return deepcopy(pair['targets'])


def _copy_option_rank(agent, state, player_id, choice, option):
    from rules_engine.land_history import landfall_status
    from rules_engine.continuous import effective_combat_stats
    copied = next(item for item in state.stack if item.id == choice['stack_id'])
    index = choice['linked_target_index']
    old = copied.payload['target_instances'][index]
    if option == 'keep':
        kind, value = old['kind'], old['id']
    else:
        key, value = option.split(':', 1)
        kind = 'player' if key == 'target_player' else 'planeswalker' if index == 0 else 'creature'
        if kind == 'player':
            value = int(value)
    status = landfall_status(state, copied.controller)
    amount = 0 if status is None else copied.payload['landfall_amount' if status else 'ordinary_amount']
    if kind == 'player':
        enemy = value != player_id
        return (1000 if enemy else -1000) if amount and state.players[value].life <= amount else 10 if enemy else -10
    card = state.cards.get(value)
    if card is None:
        return -1000
    from rules_engine.linked_targets import _same_object
    if option == 'keep' and not _same_object(state, old):
        return -1000
    if card.controller == player_id:
        return -10
    if kind == 'planeswalker':
        return 10 + agent._noncreature_permanent_threat_score(state, value, player_id)
    toughness = effective_combat_stats(state, value)[1]
    lethal = toughness is not None and amount > 0 and toughness <= amount + card.counters.get('__damage_marked', 0)
    return 10 + int(lethal) * 20 + agent._creature_threat_score(state, value, player_id)


def choose_linked_copy_option(agent, state, player_id, choice):
    """At most sixteen complete legal continuations, never hidden draw outcomes."""
    options = sorted(choice['options'], key=lambda option: (-_copy_option_rank(agent, state, player_id, choice, option), option))
    libraries = {pid: tuple(player.library) for pid, player in state.players.items()}
    opposing_hand = tuple(state.players[3-player_id].hand)
    scored = []
    # ponytail: 4x4 continuation beam; wider boards need adaptive search, not rule limits.
    for option in options[:4]:
        try:
            branch = checked_action(_projection_copy(state), agent.engine, player_id,
                                    {'type': 'choose_mechanic', 'card_ids': [option]})
            pending = branch.pending_mechanic_choice
            if pending and (pending.get('linked_target_index') != 1 or pending.get('stack_id') != choice['stack_id']):
                continue
            completions = sorted(pending['options'], key=lambda value: (-_copy_option_rank(agent, branch, player_id, pending, value), value))[:4] if pending else [None]
            for completion in completions:
                projected = (_projection_copy(branch) if completion is None else
                             checked_action(_projection_copy(branch), agent.engine, player_id,
                                            {'type': 'choose_mechanic', 'card_ids': [completion]}))
                if not _settle_announced_stack(projected):
                    continue
                if (any(tuple(player.library) != libraries[pid] for pid, player in projected.players.items())
                        or tuple(projected.players[3-player_id].hand) != opposing_hand):
                    continue
                score = ((1000 if projected.winner == player_id else -1000) if projected.winner is not None
                         else evaluate_board(projected, player_id))
                scored.append((score, -len(scored), option))
        except ActionRejected:
            continue
    return max(scored, key=lambda item: item[:2])[2] if scored else options[0]
