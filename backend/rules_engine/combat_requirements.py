"""Maximize recognized requirements without disobeying combat restrictions."""
from itertools import combinations

from game_state.state import Zone
from rules_engine.continuous import has_keyword
from rules_engine.combat_constraints import combat_rule_view
from rules_engine.declaration_limits import declaration_limit_view, attackers_within_limits, blockers_within_limits
from rules_engine.restrictions import card_cant_attack, card_cant_attack_alone, card_cant_block, card_cant_block_alone


def requirement_weights(state, ids, kind):
    bodies = {f'{kind}s each combat if able', f'{kind} each combat if able', f'must {kind} each combat if able'}
    return {cid: sum(row['body'] in bodies for row in combat_rule_view(state, cid)['active']) for cid in ids}


def attack_candidates(state):
    return [cid for cid in state.players[state.active_player].battlefield
            if state.cards[cid].zone == Zone.BATTLEFIELD and 'Creature' in state.cards[cid].types
            and not state.cards[cid].tapped
            and (not state.cards[cid].summoning_sick or has_keyword(state, cid, 'haste'))
            and not has_keyword(state, cid, 'defender') and not card_cant_attack(state, cid)]


def best_required_attack(state, pinned=(), targets=None):
    """Return a maximum-weight completion, preserving explicitly chosen attackers."""
    from rules_engine.combat import _valid_defenders
    candidates = attack_candidates(state)
    weights = requirement_weights(state, candidates, 'attack')
    selected = list(pinned)
    targets = dict(targets or {})
    defenders = sorted(_valid_defenders(state, 3-state.active_player))
    default = f'player:{3-state.active_player}'
    if default in defenders:
        defenders.remove(default)
        defenders.insert(0, default)
    if not attackers_within_limits(state, selected, targets):
        return None
    cap = declaration_limit_view(state, 'attack')['maximum']
    for cid in sorted(candidates, key=lambda c: (-weights[c], c)):
        if not weights[cid] or cid in selected:
            continue
        if cap == 1 and card_cant_attack_alone(state, cid):
            continue
        for defender in defenders:
            proposal = {**targets, cid: defender}
            if attackers_within_limits(state, selected + [cid], proposal):
                selected.append(cid)
                targets = proposal
                break
    if len(selected) == 1 and card_cant_attack_alone(state, selected[0]):
        for cid in candidates:
            if cid in selected:
                continue
            for defender in defenders:
                proposal = {**targets, cid: defender}
                if attackers_within_limits(state, selected + [cid], proposal):
                    return selected + [cid], proposal
        return ([], {}) if not pinned else None
    return selected, targets


def attack_requirement_score(state, ids):
    return sum(requirement_weights(state, ids, 'attack').values())


def best_required_blocks(state, pinned=None):
    """Exact branch-and-bound for recognized blocker requirements; no silent size cap.

    Only requirement-bearing boards enter the search. Optional blockers can be
    needed for menace/alone restrictions. Extra-block capacity is respected;
    incomplete attacker groups are discarded before scoring.
    """
    from rules_engine.combat import _can_block_attacker, _minimum_blockers_required, _max_attackers_blockable_by_creature
    defender = 3-state.active_player
    blockers = [cid for cid in state.players[defender].battlefield
                if state.cards[cid].zone == Zone.BATTLEFIELD and 'Creature' in state.cards[cid].types
                and not state.cards[cid].tapped and not card_cant_block(state, cid)]
    weights = requirement_weights(state, blockers, 'block')
    if not any(weights.values()):
        return pinned or {}
    cap = declaration_limit_view(state, 'block')['maximum']
    if cap == 0:
        return {} if not pinned else None
    minima = {aid: _minimum_blockers_required(state, aid) for aid in state.attackers}
    edges = {bid: [aid for aid in state.attackers if _can_block_attacker(state, state.cards[aid], state.cards[bid])]
             for bid in blockers}
    # A minimum larger than the available distinct blockers can never be met.
    edges = {bid: [aid for aid in aids if minima[aid] <= (cap if cap is not None else len(blockers))
                   and sum(aid in other for other in edges.values()) >= minima[aid]] for bid, aids in edges.items()}
    pinned = pinned or {}
    required_pairs = {bid: {aid for aid, ids in pinned.items() if bid in ids} for bid in blockers}
    order = sorted(blockers, key=lambda bid: (-weights[bid], bid))
    max_score = sum(sorted(weights.values(), reverse=True)[:cap]) if cap is not None else sum(weights.values())
    best, best_score = None, -1
    stack = [(0, {})]
    while stack:
        index, selected = stack.pop()
        slots = len(order) if cap is None else cap - len(selected)
        upper = sum(weights[bid] for bid in selected) + sum(sorted((weights[bid] for bid in order[index:]), reverse=True)[:slots])
        if upper <= best_score:
            continue
        if index == len(order):
            groups = {aid: [bid for bid, aids in selected.items() if aid in aids] for aid in state.attackers}
            groups = {aid: bids for aid, bids in groups.items() if len(bids) >= minima[aid]}
            used = {bid for bids in groups.values() for bid in bids}
            if len(used) == 1 and card_cant_block_alone(state, next(iter(used))):
                continue
            if any(not set(ids).issubset(groups.get(aid, [])) for aid, ids in pinned.items()):
                continue
            score = sum(weights[bid] for bid in used)
            if score > best_score:
                best, best_score = groups, score
            if score == max_score:
                break
            continue
        bid = order[index]
        if not required_pairs[bid]:
            stack.append((index + 1, selected))
        if slots <= 0:
            continue
        size = min(len(edges[bid]), _max_attackers_blockable_by_creature(state, state.cards[bid]))
        for aids in combinations(edges[bid], int(size)):
            if aids and required_pairs[bid].issubset(aids):
                stack.append((index + 1, {**selected, bid: aids}))
    return best


def block_requirement_score(state, blocks):
    return sum(requirement_weights(state, {bid for ids in blocks.values() for bid in ids}, 'block').values())
