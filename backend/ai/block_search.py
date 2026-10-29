"""Bounded AI intent enumeration using shared combat rules, not new game limits."""
from itertools import combinations

from game_state.state import Zone
from rules_engine import combat
from rules_engine.combat_payments import block_tax_sources, block_payment_state
from rules_engine.combat_requirements import best_required_blocks, block_requirement_score, requirement_weights, target_block_requirements
from rules_engine.declaration_limits import blockers_within_limits
from rules_engine.restrictions import card_cant_block, card_cant_block_alone
from rules_engine.query_context import rule_query_scope

EXACT_BLOCK_INTENT_LIMIT = 64
BLOCK_SHORTLIST_SIZE = 16


def block_projection_intents(state, intents):
    """Shortlist legal intents for a conditional forecast, not a win proof.

    Small sets retain exhaustive search. On larger sets, cheap public combat
    estimates diversify survival, trades and retention before native resolution.
    Triggers, prevention and damage allocation still belong to that resolution.
    Unknown characteristics leave the bounded forecast unknown as well.
    """
    if len(intents) <= EXACT_BLOCK_INTENT_LIMIT:
        return intents
    from ai.heuristics import _creature_value
    from rules_engine.continuous import effective_combat_stats, effective_keywords

    with rule_query_scope(state):
        defender = 3 - state.active_player
        ids = sorted(set(state.attackers) | {bid for row in intents for bids in row.values() for bid in bids})
        stats = {cid: effective_combat_stats(state, cid) for cid in ids}
        if any(power is None or toughness is None for power, toughness in stats.values()):
            return None
        keywords = {cid: set(effective_keywords(state, cid)) for cid in ids}
        values = {cid: _creature_value(state, cid) for cid in ids}
        remaining = {cid: max(1, stats[cid][1] - state.cards[cid].counters.get('__damage_marked', 0))
                     for cid in ids}
        groups = {}

        def estimate(aid, bids):
            key = aid, tuple(sorted(bids))
            if key in groups:
                return groups[key]
            power = max(0, stats[aid][0])
            damage = power * (2 if 'double strike' in keywords[aid] else 1)
            dead = set()
            if bids:
                first = [bid for bid in bids if keywords[bid] & {'first strike', 'double strike'}]
                early_kill = ('indestructible' not in keywords[aid] and
                    (sum(max(0, stats[bid][0]) for bid in first) >= remaining[aid]
                     or any(stats[bid][0] > 0 and 'deathtouch' in keywords[bid] for bid in first)))
                if early_kill and not keywords[aid] & {'first strike', 'double strike'}:
                    damage = 0
                budget = damage
                for bid in sorted(bids, key=lambda cid: (-values[cid], cid)):
                    lethal = 1 if 'deathtouch' in keywords[aid] else remaining[bid]
                    if budget >= lethal:
                        budget -= lethal
                        if 'indestructible' not in keywords[bid]:
                            dead.add(bid)
                hitters = [bid for bid in bids if bid not in dead
                           or not keywords[aid] & {'first strike', 'double strike'}
                           or keywords[bid] & {'first strike', 'double strike'}]
                killed = ('indestructible' not in keywords[aid] and
                    (sum(max(0, stats[bid][0]) * (2 if 'double strike' in keywords[bid] else 1)
                         for bid in hitters) >= remaining[aid]
                     or any(stats[bid][0] > 0 and 'deathtouch' in keywords[bid] for bid in hitters)))
                face = max(0, damage - sum(1 if 'deathtouch' in keywords[aid] else remaining[bid]
                                          for bid in bids)) if 'trample' in keywords[aid] else 0
            else:
                killed, face = False, damage
            if state.attack_targets.get(aid, f'player:{defender}') != f'player:{defender}':
                face = 0
            groups[key] = face, values[aid] if killed else 0, dead
            return groups[key]

        ranked = []
        for row in intents:
            face, gain, lost = 0, 0.0, set()
            for aid in state.attackers:
                damage, trade, dead = estimate(aid, row.get(aid, ()))
                face += damage
                gain += trade
                lost.update(dead)
            loss = sum(values[cid] for cid in sorted(lost))
            key = tuple(sorted((aid, tuple(sorted(bids))) for aid, bids in row.items()))
            ranked.append((face < state.players[defender].life, face, gain - loss, loss, key, row))
        orders = [sorted(ranked, key=key, reverse=True) for key in (
            lambda item: (item[0], -item[1], item[2], item[4]),
            lambda item: (item[0], item[2], -item[1], item[4]),
            lambda item: (item[0], -item[3], item[2], item[4]),
        )]
        selected, seen = [], set()
        no_block = next((row for row in intents if not row), None)
        if no_block is not None:
            selected.append(no_block)
            seen.add(())
        for candidates in zip(*orders):
            for candidate in candidates:
                if candidate[4] not in seen:
                    selected.append(candidate[5])
                    seen.add(candidate[4])
                    if len(selected) == BLOCK_SHORTLIST_SIZE:
                        return selected
        return selected


def block_intents(state, attacker_ids, blocker_ids, *, node_budget=4096):
    """All explored legal direct intents, or None if the whole search exceeds budget.

    A budget exhaustion never labels a partially explored choice as optimal.
    Declaration costs are voluntary; requirement optima depend on volunteered IDs.
    """
    # Payment probes mutate detached clones, never this query-scoped root.
    with rule_query_scope(state):
        return _block_intents(state, attacker_ids, blocker_ids, node_budget=node_budget)


def _block_intents(state, attacker_ids, blocker_ids, *, node_budget=4096):
    if node_budget < 1:
        raise ValueError('AI search node budget must be positive')
    defender = 3-state.active_player
    attacker_ids = list(dict.fromkeys(cid for cid in attacker_ids if cid in state.attackers and cid in state.cards))
    blocker_ids = list(dict.fromkeys(cid for cid in blocker_ids if cid in state.cards
                      and state.cards[cid].zone == Zone.BATTLEFIELD and state.cards[cid].controller == defender
                      and 'Creature' in state.cards[cid].types and not state.cards[cid].tapped and not card_cant_block(state, cid)))
    choices = {}
    for bid in blocker_ids:
        targets = [aid for aid in attacker_ids if combat._can_block_attacker(state, state.cards[aid], state.cards[bid])]
        capacity = combat._max_attackers_blockable_by_creature(state, state.cards[bid])
        choices[bid] = [group for count in range(min(len(targets), int(capacity) if capacity != float('inf') else len(targets))+1)
                       for group in combinations(targets, count)]
    requirements = any(requirement_weights(state, blocker_ids, 'block').values()) or bool(target_block_requirements(state))
    taxed = bool(block_tax_sources(state))
    optimum_scores, payments = {}, {}
    intents = []
    visits = 0
    exhausted = False

    def visit(index, groups):
        nonlocal visits, exhausted
        visits += 1
        if visits > node_budget:
            exhausted = True
            return
        if index == len(blocker_ids):
            selected = tuple(sorted({bid for ids in groups.values() for bid in ids}))
            if len(selected) == 1 and card_cant_block_alone(state, selected[0]):
                return
            if any(len(ids) < combat._minimum_blockers_required(state, aid) for aid, ids in groups.items()):
                return
            if not blockers_within_limits(state, groups):
                return
            if requirements:
                key = selected if taxed else ()
                if key not in optimum_scores:
                    optimum = best_required_blocks(state, volunteered=selected)
                    optimum_scores[key] = block_requirement_score(state, optimum) if optimum is not None else None
                optimum = optimum_scores[key]
                if optimum is None or block_requirement_score(state, groups) < optimum:
                    return
            if taxed:
                if selected not in payments:
                    paid = block_payment_state(state, list(selected))
                    payments[selected] = paid is not None and paid.players[defender].life > 0
                if not payments[selected]:
                    return
            intents.append({aid: list(ids) for aid, ids in groups.items()})
            return
        bid = blocker_ids[index]
        for targets in choices[bid]:
            for aid in targets:
                groups.setdefault(aid, []).append(bid)
            visit(index+1, groups)
            for aid in targets:
                groups[aid].pop()
                if not groups[aid]:
                    del groups[aid]
            if exhausted:
                return

    visit(0, {})
    return None if exhausted else intents
