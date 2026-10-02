"""Bounded public-board tax planning, not a combat optimality oracle."""
from copy import deepcopy

from game_state.state import Step, Zone
from rules_engine.combat_payments import temporary_combat_tax, attack_payment_state, block_payment_state
from rules_engine.combat_requirements import attack_candidates
from rules_engine.continuous import effective_power
from rules_engine.costs import apply_activated_costs
from rules_engine.restrictions import card_cant_block


def combat_tax_plan(state, move, player_id):
    label = str(move.get('ability_label') or '').lower().split(':', 1)[-1].strip().rstrip('.')
    spec = temporary_combat_tax(label)
    if not spec:
        return None
    empty = {'x_value': 0, 'score': -30.0}
    kind = spec['kind']
    if state.stack or (kind == 'attack' and not (state.active_player != player_id and state.step == Step.BEGIN_COMBAT)):
        return empty
    if kind == 'block' and not (state.active_player == player_id and state.step == Step.DECLARE_ATTACKERS and state.attackers_declared and state.attackers):
        return empty
    opponent = 3-player_id
    if kind == 'attack':
        candidates = sorted(attack_candidates(state), key=lambda cid: (-effective_power(state, cid), cid))
    else:
        from rules_engine.combat import _can_block_attacker
        candidates = sorted(cid for cid in state.players[opponent].battlefield
                            if state.cards[cid].zone == Zone.BATTLEFIELD and 'Creature' in state.cards[cid].types
                            and not state.cards[cid].tapped and not card_cant_block(state, cid)
                            and any(_can_block_attacker(state, state.cards[aid], state.cards[cid]) for aid in state.attackers))
    if not candidates:
        return empty

    def affordable(board):
        selected = []
        for cid in candidates:
            proposal = selected + [cid]
            paid = attack_payment_state(board, proposal) if kind == 'attack' else block_payment_state(board, proposal)
            if paid is not None and paid.players[opponent].life > 0 and all(
                    paid.cards[chosen].zone == Zone.BATTLEFIELD and paid.cards[chosen].controller == opponent for chosen in proposal):
                selected.append(cid)
        return selected

    baseline = affordable(state)
    if not baseline:
        return empty
    best = empty
    # A search budget for AI evaluation only; engine costs/legality have no X cap.
    for x in range(1, 21):
        projected = deepcopy(state)
        source = state.cards.get(move.get('card_id'))
        if not source or not apply_activated_costs(projected, player_id, source.id, str(move.get('mana_cost') or ''), x_value=x):
            continue
        if projected.players[player_id].life <= 0:
            continue
        projected.combat_cost_effects.append({'kind': kind, 'scope': 'all', 'mana_cost': spec['mana_cost'].replace('{X}', f'{{{x}}}'),
                                             'amount': x, 'controller': player_id, 'expires_turn': state.turn,
                                             'source_id': move.get('card_id'), 'source_name': source.name if source else '', 'clause': label})
        after = affordable(projected)
        denied = max(0, len(baseline)-len(after))
        pressure = (sum(max(0, effective_power(state, cid)) for cid in baseline if cid not in after)
                    if kind == 'attack' else min(denied, len(state.attackers)) * 2)
        score = 3.0 * denied + pressure - 0.8 * x - 1.0
        if denied and score > best['score'] and score > 0:
            best = {'x_value': x, 'score': score}
    return best
