"""Finalize AI combat intent against shared public-board declaration rules."""
from rules_engine import combat
from rules_engine.continuous import effective_power
from rules_engine.declaration_limits import declaration_limit_view, attackers_within_limits
from rules_engine.combat_requirements import attack_candidates, requirement_weights, best_required_attack, best_required_blocks, attack_requirement_score, target_block_requirements
from rules_engine.combat_payments import attack_tax_sources, attack_payment_view, attack_payment_state, block_tax_sources, block_payment_state
from rules_engine.restrictions import card_cant_attack_alone


def finalize_declaration(state, action):
    from game_state.state import MatchState, Step, Zone
    if not isinstance(state, MatchState):
        return action
    if state.pending_mechanic_choice or state.pending_replacement_choice or state.pending_trigger_order:
        return action
    kind = action.get('type')
    if kind == 'pass_priority' and not state.stack and not state.pregame_pending:
        if state.step == Step.DECLARE_ATTACKERS and state.priority_player == state.active_player and not state.attackers_declared:
            optimum = best_required_attack(state)
            if optimum and attack_requirement_score(state, optimum[0]) > 0:
                action = {'type': 'attack', 'attackers': []}
                kind = 'attack'
        elif state.step == Step.DECLARE_BLOCKERS and state.priority_player != state.active_player and not state.blockers_declared:
            optimum = best_required_blocks(state)
            if optimum:
                action = {'type': 'block', 'blocks': optimum}
                kind = 'block'
    if kind not in {'attack', 'block'}:
        return action
    if kind == 'block':
        action = {**action, 'blocks': {aid: bids if isinstance(bids, list) else [bids]
                                     for aid, bids in (action.get('blocks') or {}).items()}}
    candidates = attack_candidates(state) if kind == 'attack' else list(state.players[3-state.active_player].battlefield)
    weights = requirement_weights(state, candidates, kind)
    view = declaration_limit_view(state, kind)
    if not view['sources'] and not any(weights.values()) and not (
            attack_tax_sources(state) if kind == 'attack' else target_block_requirements(state) or block_tax_sources(state)):
        return action
    if kind == 'attack':
        from rules_engine.combat import _valid_defenders
        requested = list(action.get('attackers') or [])
        options = list(dict.fromkeys(requested + [cid for cid in candidates if weights.get(cid)]))
        options.sort(key=lambda cid: (-weights.get(cid, 0), cid not in requested, -effective_power(state, cid), cid))
        selected, targets = [], {}
        defenders = sorted(_valid_defenders(state, 3-state.active_player))
        default = f'player:{3-state.active_player}'
        for cid in options:
            if cid not in candidates or view['maximum'] == 1 and card_cant_attack_alone(state, cid):
                continue
            desired = (action.get('attack_targets') or {}).get(cid, default)
            for target in list(dict.fromkeys([desired, *defenders])):
                proposal = {**targets, cid: target}
                if cid not in requested and attack_payment_view(state, [cid], {cid: target})['payments']:
                    continue
                paid = attack_payment_state(state, selected + [cid], proposal) if target in defenders else None
                if (paid is not None and paid.players[state.active_player].life > 0
                        and attackers_within_limits(state, selected + [cid], proposal)
                        and all(paid.cards[chosen].zone == Zone.BATTLEFIELD and paid.cards[chosen].controller == state.active_player
                                and 'Creature' in paid.cards[chosen].types
                                for chosen in selected + [cid])):
                    selected.append(cid)
                    targets[cid] = target
                    break
        if len(selected) == 1 and card_cant_attack_alone(state, selected[0]):
            selected, targets = [], {}
        optimum = best_required_attack(state)
        completion = best_required_attack(state, selected, targets)
        if completion is None or optimum and attack_requirement_score(state, completion[0]) < attack_requirement_score(state, optimum[0]):
            completion = optimum
        selected, targets = completion or ([], {})
        details = {}
        attack_payment_state(state, selected, targets, payment_details=details)
        return {**action, 'attackers': selected, 'attack_targets': targets,
                'hybrid_choices': details.get('hybrid_choices') or None,
                'bands': [band for band in action.get('bands', []) if all(cid in selected for cid in band)]}
    blocks = {aid: bids if isinstance(bids, list) else [bids] for aid, bids in (action.get('blocks') or {}).items()}
    selected = {bid for bids in blocks.values() for bid in bids}
    if block_tax_sources(state):
        affordable = set()
        for bid in sorted(selected, key=lambda bid: (-sum(effective_power(state, aid) for aid, bids in blocks.items() if bid in bids), bid)):
            proposed = sorted(affordable | {bid})
            paid = block_payment_state(state, proposed)
            if paid is not None and paid.players[3-state.active_player].life > 0 and all(
                    paid.cards[cid].zone == Zone.BATTLEFIELD and paid.cards[cid].controller == 3-state.active_player
                    and 'Creature' in paid.cards[cid].types for cid in proposed):
                affordable.add(bid)
        selected = affordable
        blocks = {aid: [bid for bid in bids if bid in selected] for aid, bids in blocks.items()}
    if view['maximum'] is not None and len(selected) > view['maximum']:
        selected = set(sorted(selected, key=lambda bid: (-weights.get(bid, 0),
                       -sum(effective_power(state, aid) for aid, bids in blocks.items() if bid in bids), bid))[:view['maximum']])
        blocks = {aid: [bid for bid in bids if bid in selected] for aid, bids in blocks.items()}
    from ai.pending_effects import planning_copy
    sim = planning_copy(state)
    try:
        combat.declare_blockers(sim, blocks)
        blocks = sim.blocks
    except ValueError:
        blocks = best_required_blocks(state, volunteered=selected) or {}
        if block_payment_state(state, sorted({bid for bids in blocks.values() for bid in bids})) is None:
            blocks = best_required_blocks(state) or {}
    details = {}
    block_payment_state(state, sorted({bid for bids in blocks.values() for bid in bids}), payment_details=details)
    return {**action, 'blocks': blocks, 'hybrid_choices': details.get('hybrid_choices') or None}
