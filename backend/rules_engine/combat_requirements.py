"""Maximize recognized requirements without disobeying combat restrictions."""
from itertools import combinations
from fractions import Fraction
import re

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
    from rules_engine.combat_payments import attack_payment_view
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
            if attack_payment_view(state, [cid], {cid: defender})['payments']:
                continue  # Paying an attack tax is optional, even for a requirement.
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
                if attack_payment_view(state, [cid], {cid: defender})['payments']:
                    continue
                if attackers_within_limits(state, selected + [cid], proposal):
                    return selected + [cid], proposal
        return ([], {}) if not pinned else None
    return selected, targets


def attack_requirement_score(state, ids):
    return sum(requirement_weights(state, ids, 'attack').values())


def parse_target_block_requirement(clause, card_name=''):
    def subject_supported(subject):
        return subject in {'this creature', 'cardname', card_name.lower(), 'enchanted creature', 'equipped creature'} or bool(
            card_name and card_name.lower().startswith(subject + ' '))

    specs = []
    for part in clause.split(', and '):
        match = re.fullmatch(r'all creatures able to block (.+) do so', part)
        if match and subject_supported(match[1]):
            specs.append({'subject': match[1], 'kind': 'all', 'minimum': None})
            continue
        match = re.fullmatch(r'(.+) must be blocked(?: by (\d+|one|two|three|four|five|six|seven|eight|nine|ten) or more creatures)? if able', part)
        if not match or not subject_supported(match[1]):
            return None
        from rules_engine.static_conditions import number
        minimum = number(match[2]) if match[2] else 1
        if minimum < 1:
            return None
        specs.append({'subject': match[1], 'kind': 'minimum', 'minimum': minimum})
    return specs or None


def target_block_requirements(state):
    """Public source-target provenance; each source creates independent requirements."""
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    losses = _printed_ability_loss_sources(state)
    rows = []
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            specs = [(clause, parse_target_block_requirement(clause, source.name))
                     for clause in static_clauses(source.oracle_text)]
            if source.zone != Zone.BATTLEFIELD or not any(spec for _, spec in specs):
                continue
            if printed_abilities_suppressed(state, cid, losses=losses):
                continue
            for clause, parsed in specs:
                for spec in parsed or []:
                    target = source.attached_to if spec['subject'] in {'enchanted creature', 'equipped creature'} else cid
                    if target in state.attackers and state.cards[target].zone == Zone.BATTLEFIELD:
                        rows.append({'source_id': cid, 'source_name': source.name,
                                     'attacker_id': target, 'clause': clause,
                                     'kind': spec['kind'], 'minimum': spec['minimum']})
    return rows


def targeted_block_score(requirements, blocks):
    """Pair requirements are independent; minimum-count requirements saturate."""
    return sum(len(set(blocks.get(row['attacker_id'], []))) if row['kind'] == 'all'
               else int(len(set(blocks.get(row['attacker_id'], []))) >= row['minimum'])
               for row in requirements)


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
    requirements = target_block_requirements(state)
    if not any(weights.values()) and not requirements:
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
    # Pair requirements can be worth one point per blocker; group requirements
    # can be worth only one each. Prefer pair edges on wide mixed boards.
    target_weights = {aid: sum((len(blockers) + 1 if row['kind'] == 'all' else 1)
                              for row in requirements if row['attacker_id'] == aid) for aid in state.attackers}
    edges = {bid: sorted(aids, key=lambda aid: (target_weights[aid], aid)) for bid, aids in edges.items()}
    capacities = {bid: int(min(len(edges[bid]), _max_attackers_blockable_by_creature(state, state.cards[bid]))) for bid in blockers}
    edge_weights = {}
    pair_targets = set()
    for aid in state.attackers:
        paired = sum(row['attacker_id'] == aid and row['kind'] == 'all' for row in requirements)
        thresholds = [row['minimum'] for row in requirements if row['attacker_id'] == aid and row['kind'] == 'minimum']
        # Saturated group score is bounded by slope * distinct blocker count.
        # Exact fractions avoid underestimating a bound through rounding.
        slope = max((Fraction(sum(minimum <= n for minimum in thresholds), n) for n in thresholds), default=0)
        edge_weights[aid] = paired + slope
        if paired:
            pair_targets.add(aid)
    potentials = {bid: weights[bid] + sum(sorted((edge_weights[aid] for aid in edges[bid]), reverse=True)[:capacities[bid]]) for bid in blockers}
    pinned = pinned or {}
    required_pairs = {bid: {aid for aid, ids in pinned.items() if bid in ids} for bid in blockers}
    order = sorted(blockers, key=lambda bid: (-potentials[bid], bid))
    max_score = sum(sorted(potentials.values(), reverse=True)[:cap]) if cap is not None else sum(potentials.values())
    saturated_bound = sum(sorted(weights.values(), reverse=True)[:cap]) if cap is not None else sum(weights.values())
    for row in requirements:
        available = sum(row['attacker_id'] in edges[bid] and capacities[bid] > 0 for bid in blockers)
        available = min(available, cap) if cap is not None else available
        saturated_bound += available if row['kind'] == 'all' else int(available >= row['minimum'])
    max_score = int(min(max_score, saturated_bound))
    best, best_score = None, -1
    stack = [(0, {})]
    while stack:
        index, selected = stack.pop()
        slots = len(order) if cap is None else cap - len(selected)
        upper = min(max_score, sum(potentials[bid] for bid in selected) + sum(sorted((potentials[bid] for bid in order[index:]), reverse=True)[:slots]))
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
            score = sum(weights[bid] for bid in used) + targeted_block_score(requirements, groups)
            if score > best_score:
                best, best_score = groups, score
            if score == max_score:
                break
            continue
        bid = order[index]
        prefer_skip = not weights[bid] and not any(aid in pair_targets for aid in edges[bid])
        if not required_pairs[bid] and not prefer_skip:
            stack.append((index + 1, selected))
        if slots <= 0:
            if not required_pairs[bid] and prefer_skip:
                stack.append((index + 1, selected))
            continue
        size = capacities[bid]
        for aids in combinations(edges[bid], int(size)):
            if aids and required_pairs[bid].issubset(aids):
                stack.append((index + 1, {**selected, bid: aids}))
        if not required_pairs[bid] and prefer_skip:
            stack.append((index + 1, selected))
    return best


def block_requirement_score(state, blocks):
    return sum(requirement_weights(state, {bid for ids in blocks.values() for bid in ids}, 'block').values()) + targeted_block_score(
        target_block_requirements(state), blocks)
