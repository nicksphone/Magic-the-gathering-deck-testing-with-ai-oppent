"""Bounded AI intent enumeration using shared combat rules, not new game limits."""
from itertools import combinations

from game_state.state import Zone
from rules_engine import combat
from rules_engine.combat_payments import block_tax_sources, block_payment_state
from rules_engine.combat_requirements import best_required_blocks, block_requirement_score, requirement_weights, target_block_requirements
from rules_engine.declaration_limits import blockers_within_limits
from rules_engine.restrictions import card_cant_block, card_cant_block_alone


def block_intents(state, attacker_ids, blocker_ids, *, node_budget=4096):
    """All explored legal direct intents, or None if the whole search exceeds budget.

    A budget exhaustion never labels a partially explored choice as optimal.
    Declaration costs are voluntary; requirement optima depend on volunteered IDs.
    """
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
