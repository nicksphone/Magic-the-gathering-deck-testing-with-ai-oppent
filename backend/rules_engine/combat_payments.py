"""Shared mana attack taxes, fixed before activating mana abilities."""
from rules_engine.type_effects import effective_types
import re
from copy import deepcopy
from functools import lru_cache

from game_state.state import Zone


@lru_cache(maxsize=2048)
def parse_attack_tax(clause):
    clause = re.sub(r'^domain\s*[—–-]\s*', '', clause)
    match = re.fullmatch(
        r"creatures can't attack you( or planeswalkers you control)? unless their controller pays "
        r"((?:\{[^{}]+\})+) for each (?:creature they control that's attacking you|of those creatures)"
        r"(, where x is the number of (?:enchantments you control|basic land types among lands you control))?", clause)
    if not match or (match[2] == '{x}') != bool(match[3]):
        return None
    from rules_engine.mana import hybrid_payment_symbols
    symbols = re.findall(r'\{([^{}]+)\}', match[2].upper())
    if match[2] != '{x}' and any(not (symbol.isdigit() or symbol in {'W', 'U', 'B', 'R', 'G', 'C', 'S'}
        or hybrid_payment_symbols('{' + symbol + '}')) for symbol in symbols):
        return None
    return {'planeswalkers': bool(match[1]), 'amount': None if match[2] == '{x}' else sum(int(s) for s in symbols if s.isdigit()),
            'mana_cost': match[2].upper(),
            'scaling': ('domain' if 'basic land types' in match[3] else 'enchantments') if match[3] else None}


@lru_cache(maxsize=2048)
def temporary_combat_tax(clause):
    """A rule-changing global tax, not a grant to only current creatures."""
    match = re.fullmatch(r"this turn, creatures can't (attack|block) unless their controller pays "
                         r"((?:\{[^{}]+\})+) for each (attacking|blocking) creature they control", clause)
    if not match or match[3] != {'attack': 'attacking', 'block': 'blocking'}[match[1]]:
        return None
    # Reuse the mana grammar; resolving X is supplied by the announced action.
    cost = match[2].upper()
    fixed = cost.replace('{X}', '{0}')
    parsed = parse_attack_tax(f"creatures can't attack you unless their controller pays {fixed.lower()} for each of those creatures")
    return {'kind': match[1], 'mana_cost': cost} if parsed else None


def active_combat_cost_effects(state, kind):
    return [row for row in state.combat_cost_effects
            if row['kind'] == kind and row['expires_turn'] >= state.turn]


@lru_cache(maxsize=2048)
def parse_static_combat_tax(clause, card_name=''):
    """Recognized mana costs with source/controller-relative conditions only."""
    condition = None
    prefix = re.fullmatch(r'(?:as long as|if) (.+?), (.+)', clause)
    if prefix:
        condition, clause = prefix.groups()
        from rules_engine.static_conditions import parse_static_condition
        parsed = parse_static_condition(condition, card_name)
        if parsed is None or parsed[0] not in {'source_status', 'graveyard', 'source_counters', 'lands', 'color_permanent', 'global_land'}:
            return None
    attack = parse_attack_tax(clause)
    if attack:
        return {**attack, 'kind': 'attack', 'condition': condition}
    block = re.fullmatch(r"creatures( you control| your opponents control)? can't block unless their controller pays "
                         r"((?:\{[^{}]+\})+) for each (?:blocking creature they control|of those creatures)", clause)
    if not block:
        recipient = re.fullmatch(r"(.+?) can't (attack(?: or block)?|block) unless (?:its|their) controller pays "
                                 r"((?:\{[^{}]+\})+)", clause)
        if not recipient:
            return None
        from rules_engine.combat_constraints import _supported_combat_subject
        if not _supported_combat_subject(recipient[1], card_name):
            return None
        fixed = parse_attack_tax(f"creatures can't attack you unless their controller pays {recipient[3]} for each of those creatures")
        if not fixed or fixed['scaling']:
            return None
        kinds = tuple(recipient[2].split(' or '))
        return {**fixed, 'kind': kinds[0], 'kinds': kinds, 'condition': condition,
                'scope': 'all', 'recipient_subject': recipient[1]}
    # The same fixed mana grammar supports both declaration kinds.
    fixed = parse_attack_tax(f"creatures can't attack you unless their controller pays {block[2]} for each of those creatures")
    if not fixed or fixed['scaling']:
        return None
    return {**fixed, 'kind': 'block', 'condition': condition,
            'scope': {' you control': 'controller', ' your opponents control': 'opponents'}.get(block[1], 'all')}


def static_combat_tax_sources(state, kind):
    from rules_engine.combat_constraints import static_clauses
    from rules_engine.continuous import printed_abilities_suppressed, _printed_ability_loss_sources
    losses = _printed_ability_loss_sources(state)
    rows = []
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            specs = [(clause, parse_static_combat_tax(clause, source.name)) for clause in static_clauses(source.oracle_text)]
            if source.zone != Zone.BATTLEFIELD or not any(spec for _, spec in specs):
                continue
            if printed_abilities_suppressed(state, cid, losses=losses):
                continue
            for clause, spec in specs:
                if spec and kind in spec.get('kinds', (spec['kind'],)):
                    if spec['condition']:
                        from rules_engine.static_conditions import evaluate_static_condition
                        if evaluate_static_condition(state, source, source, spec['condition']) is not True:
                            continue
                    amount = spec['amount']
                    if spec['scaling'] == 'domain':
                        from rules_engine.domain import basic_land_type_count
                        amount = basic_land_type_count(state, source.controller)
                    elif amount is None:
                        amount = sum('Enchantment' in effective_types(state, state.cards[other]) and state.cards[other].zone == Zone.BATTLEFIELD
                                     for other in state.players[source.controller].battlefield)
                    rows.append({**spec, 'kind': kind, 'amount': amount, 'mana_cost': f'{{{amount}}}' if spec['scaling'] else spec['mana_cost'], 'controller': source.controller,
                                 'source_id': cid, 'source_name': source.name, 'clause': clause})
    return rows


def attack_tax_sources(state):
    return static_combat_tax_sources(state, 'attack') + active_combat_cost_effects(state, 'attack')


def _tax_recipient(state, source, cid):
    if not source.get('recipient_subject'):
        return True
    from rules_engine.combat_constraints import _recipient_body
    return _recipient_body(state, state.cards[source['source_id']], state.cards[cid],
                           f"{source['recipient_subject']} can't {source['kind']}") is not None


def attack_payment_view(state, ids, targets=None):
    targets = targets or {}
    sources = attack_tax_sources(state)
    payments = []
    for cid in ids:
        target = targets.get(cid, f'player:{3-state.active_player}')
        for source in sources:
            if not _tax_recipient(state, source, cid):
                continue
            taxed = source.get('scope') == 'all' or target == f"player:{source['controller']}"
            if source.get('planeswalkers') and target.startswith('planeswalker:') and source.get('scope') != 'all':
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
    if not paid.trigger_staging:
        paid.trigger_staging = True
        paid.trigger_staging_event = 'declare_attackers'
    # Non-vigilant attackers tap before costs/mana abilities (CR 508.1f-i).
    from rules_engine.resource_events import tap_permanents
    tap_permanents(paid, [cid for cid in ids if not has_keyword(paid, cid, 'vigilance')])
    if not auto_pay_cost(paid, paid.active_player, view['mana_cost'],
                         payment_kind='combat', payment_types=set(), hybrid_choices=hybrid_choices,
                         payment_details=payment_details):
        return None
    if view['mana_cost'] == ''.join(f"{{{row['amount']}}}" for row in view['payments']):
        paid.log.append(f"{paid.players[paid.active_player].name} pays {view['total_generic']} mana in attack costs.")
    else:
        paid.log.append(f"{paid.players[paid.active_player].name} pays {view['mana_cost']} in attack costs.")
    return paid


def block_tax_sources(state):
    defender = 3-state.active_player
    return [row for row in static_combat_tax_sources(state, 'block') + active_combat_cost_effects(state, 'block')
            if row['scope'] == 'all' or (row['controller'] == defender) == (row['scope'] == 'controller')]


def block_payment_view(state, ids):
    payments = [{**source, 'blocker_id': cid} for cid in dict.fromkeys(ids) for source in block_tax_sources(state)
                if _tax_recipient(state, source, cid)]
    cost = ''.join(row['mana_cost'] for row in payments)
    from rules_engine.mana import hybrid_payment_symbols
    return {'mana_cost': cost, 'payments': payments, 'hybrid_symbols': hybrid_payment_symbols(cost)}


def block_payment_state(state, ids, hybrid_choices=None, payment_details=None):
    """Chosen blockers may tap for mana before actually becoming blockers."""
    view = block_payment_view(state, ids)
    if not view['payments']:
        return state
    from rules_engine.mana import auto_pay_cost
    paid = deepcopy(state)
    defender = 3-state.active_player
    if not auto_pay_cost(paid, defender, view['mana_cost'], payment_kind='combat', payment_types=set(),
                         hybrid_choices=hybrid_choices, payment_details=payment_details):
        return None
    paid.log.append(f"{paid.players[defender].name} pays {view['mana_cost']} in block costs.")
    return paid
