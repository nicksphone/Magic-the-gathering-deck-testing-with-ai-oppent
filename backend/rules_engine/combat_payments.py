"""Shared mana attack taxes, fixed before activating mana abilities."""
import re
from copy import deepcopy
from functools import lru_cache

from game_state.state import Zone


@lru_cache(maxsize=2048)
def parse_attack_tax(clause):
    match = re.fullmatch(
        r"creatures can't attack you( or planeswalkers you control)? unless their controller pays "
        r"((?:\{[^{}]+\})+) for each (?:creature they control that's attacking you|of those creatures)"
        r"(, where x is the number of enchantments you control)?", clause)
    if not match or (match[2] == '{x}') != bool(match[3]):
        return None
    from rules_engine.mana import hybrid_payment_symbols
    symbols = re.findall(r'\{([^{}]+)\}', match[2].upper())
    if match[2] != '{x}' and any(not (symbol.isdigit() or symbol in {'W', 'U', 'B', 'R', 'G', 'C', 'S'}
        or hybrid_payment_symbols('{' + symbol + '}')) for symbol in symbols):
        return None
    return {'planeswalkers': bool(match[1]), 'amount': None if match[2] == '{x}' else sum(int(s) for s in symbols if s.isdigit()),
            'mana_cost': match[2].upper(),
            'scaling': 'enchantments' if match[3] else None}


def attack_tax_sources(state):
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    losses = _printed_ability_loss_sources(state)
    rows = []
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            specs = [(clause, parse_attack_tax(clause)) for clause in static_clauses(source.oracle_text)]
            if source.zone != Zone.BATTLEFIELD or not any(spec for _, spec in specs):
                continue
            if printed_abilities_suppressed(state, cid, losses=losses):
                continue
            for clause, spec in specs:
                if spec:
                    amount = spec['amount']
                    if amount is None:
                        amount = sum('Enchantment' in state.cards[other].types and state.cards[other].zone == Zone.BATTLEFIELD
                                     for other in state.players[source.controller].battlefield)
                    rows.append({**spec, 'amount': amount, 'mana_cost': f'{{{amount}}}' if spec['scaling'] else spec['mana_cost'], 'controller': source.controller,
                                 'source_id': cid, 'source_name': source.name, 'clause': clause})
    return rows


def attack_payment_view(state, ids, targets=None):
    targets = targets or {}
    sources = attack_tax_sources(state)
    payments = []
    for cid in ids:
        target = targets.get(cid, f'player:{3-state.active_player}')
        for source in sources:
            taxed = target == f"player:{source['controller']}"
            if source['planeswalkers'] and target.startswith('planeswalker:'):
                walker = state.cards.get(target.removeprefix('planeswalker:'))
                taxed = walker is not None and walker.controller == source['controller']
            if taxed:
                payments.append({**source, 'attacker_id': cid, 'target': target})
    total = sum(row['amount'] for row in payments)
    cost = ''.join(row['mana_cost'] for row in payments)
    from rules_engine.mana import hybrid_payment_symbols
    return {'total_generic': total, 'mana_cost': cost, 'payments': payments, 'hybrid_symbols': hybrid_payment_symbols(cost)}


def attack_payment_state(state, ids, targets=None, hybrid_choices=None, payment_details=None):
    """A payable detached declaration, or None; never spends authoritative mana."""
    view = attack_payment_view(state, ids, targets)
    if not view['payments']:
        return state
    from rules_engine.continuous import has_keyword
    from rules_engine.mana import auto_pay_cost
    paid = deepcopy(state)
    # Non-vigilant attackers tap before costs/mana abilities (CR 508.1f-i).
    for cid in ids:
        if not has_keyword(paid, cid, 'vigilance'):
            paid.cards[cid].tapped = True
    if not auto_pay_cost(paid, paid.active_player, view['mana_cost'],
                         payment_kind='combat', payment_types=set(), hybrid_choices=hybrid_choices,
                         payment_details=payment_details):
        return None
    if view['mana_cost'] == ''.join(f"{{{row['amount']}}}" for row in view['payments']):
        paid.log.append(f"{paid.players[paid.active_player].name} pays {view['total_generic']} mana in attack costs.")
    else:
        paid.log.append(f"{paid.players[paid.active_player].name} pays {view['mana_cost']} in attack costs.")
    return paid
