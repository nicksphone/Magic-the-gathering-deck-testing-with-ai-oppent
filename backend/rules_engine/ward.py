from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import Zone, object_incarnation
from rules_engine.oracle_text import without_reminder_text
from rules_engine.player_counters import counter_count, PLAYER_COUNT_RE

WARD_LINE = re.compile(r'^ward\s*[—-]?\s*(.+)$', re.I | re.M)
MANA_WARD = re.compile(r'\bward\s*((?:\{[^}]+\})+)', re.I)
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
DYNAMIC_WARD_RE = re.compile(r'\bward\s+((?:\{[^}]+\})+, where X is the ' + PLAYER_COUNT_RE + r')(?=\s*(?:[.\n]|$))', re.I)


def printed_ward_costs(target, *, include_conditionals=True):
    """Printed keyword lists and bounded self-grants, not later effect bodies."""
    keywords = {str(k).lower() for k in getattr(target, 'keywords', []) or []}
    name = getattr(target, 'name', '')
    names = {name.lower(), name.split(',')[0].lower(), 'this creature', 'this permanent'}
    out = []
    for line in without_reminder_text(getattr(target, 'oracle_text', '') or '').splitlines():
        line = line.strip().rstrip('.')
        if (match := WARD_LINE.fullmatch(line)) and parse_ward_cost(match[1]) is not None:
            out.append(match[1])
            continue
        parts = [part.strip() for part in line.split(',')]
        if all(part.lower() in keywords or WARD_LINE.fullmatch(part) for part in parts):
            out.extend(match[1] for part in parts if (match := WARD_LINE.fullmatch(part)))
            continue
        match = re.fullmatch(r'(.+?) has ward (.+?)(?: as long as (.+))?', line, re.I)
        if not match or match[1].lower() not in names:
            continue
        condition = match[3].lower() if match[3] else None
        if condition is not None and not include_conditionals:
            continue
        conditions = {"it's untapped": False, 'it is untapped': False, "it's tapped": True, 'it is tapped': True}
        if condition is None or (condition in conditions and getattr(target, 'tapped', False) == conditions[condition]):
            out.append(match[2])
    return out


def unsupported_ward_costs(text):
    """Scan costs anywhere, including named/granted forms and keyword lists."""
    text = without_reminder_text(text or '')
    dynamic = {match.start() for match in DYNAMIC_WARD_RE.finditer(text) if parse_ward_cost(match[1]) is not None}
    for match in re.finditer(r'\bward(?:\s*[—-]\s*|\s+)([^\n.,]+)', text, re.I):
        if match.start() in dynamic:
            continue
        cost = re.split(r'\s+(?:as long as|until|and)\s+', match[1], maxsplit=1, flags=re.I)[0]
        if parse_ward_cost(cost) is None:
            yield cost


def parse_ward_cost(text):
    text = text.lower().strip().rstrip('.')
    match = re.fullmatch(r'((?:\{(?:\d+|[wubrgcsx]|[wubrg]/[wubrg]|[wubrg]/p|2/[wubrg])\})+), where x is the ' + PLAYER_COUNT_RE, text)
    if match and '{x}' in match[1]:
        return {'kind': 'player_counter_mana', 'template': match[1].upper(), 'counter': match[2]}
    if re.fullmatch(r'(?:\{(?:\d+|[wubrgcs]|[wubrg]/[wubrg]|[wubrg]/p|2/[wubrg])\})+', text):
        return {'kind': 'mana', 'cost': text.upper()}
    match = re.fullmatch(r'pay (\d+) life', text)
    if match:
        return {'kind': 'life', 'amount': int(match[1])}
    if text == "pay life equal to this creature's power":
        return {'kind': 'power_life'}
    match = re.fullmatch(r'(discard|sacrifice) (a|an|one|two|three|four|five|\d+) (.+?)s?', text)
    if not match:
        return None
    kind, count, subject = match.groups()
    amount = NUMBERS.get(count, int(count) if count.isdigit() else 0)
    if kind == 'discard' and subject == 'card':
        return {'kind': kind, 'amount': amount}
    quality = ''
    if subject.startswith(('legendary ', 'nonland ', 'nontoken ')):
        quality, subject = subject.split(' ', 1)
    if quality == 'legendary' and subject == 'artifact or legendary creature':
        subject = 'artifact or creature'
    if kind == 'sacrifice' and subject in {'creature', 'artifact', 'enchantment', 'permanent', 'artifact or creature'}:
        return {'kind': kind, 'amount': amount, 'subject': subject, 'quality': quality}
    return None


def ward_instances(state, target):
    from rules_engine.continuous import effective_keyword_counts
    printed = {cost.lower(): cost for cost in printed_ward_costs(target)}
    out = []
    for keyword, count in effective_keyword_counts(state, target.id).items():
        match = WARD_LINE.fullmatch(keyword)
        if match and parse_ward_cost(match[1]) is not None:
            cost = printed.get(match[1], match[1])
            cost = re.sub(r'\{[^}]+\}', lambda symbol: symbol[0].upper(), cost)
            cost = re.sub(r'\bwhere x\b', 'where X', cost)
            out.extend([cost] * count)
    return out


def target_ids(payload):
    announced = payload.get('__announced_targets') or {}
    ids = {announced.get('target_card_id')}
    ids.update(announced.get('target_card_ids') or [])
    ids.update((announced.get('target_distribution') or {}).keys())
    for choice in (announced.get('mode_targets') or {}).values():
        ids.add(choice.get('target_card_id'))
        ids.update(choice.get('target_card_ids') or [])
        ids.update((choice.get('target_distribution') or {}).keys())
    if payload.get('__trigger_target_choice'):
        ids.add(payload.get('target_card_id'))
    return sorted(cid for cid in ids if isinstance(cid, str))


def capture_ward_triggers(state, controller, payload):
    out = []
    for cid in target_ids(payload):
        card = state.cards.get(cid)
        if card is None or card.zone != Zone.BATTLEFIELD or card.controller == controller:
            continue
        if (payload.get('__ordered_target_instances') or payload.get('__ordered_distinct_targets')
                or payload.get('__linked_target_instances')):
            references = (payload.get('target_instances', []) if payload.get('__linked_target_instances') else
                          [effect.get('payload') or {} for effect in payload.get('effects', [])])
            if not any(reference.get('target_card_id') == cid
                       and reference.get('__target_incarnation') == object_incarnation(card)
                       and reference.get('__target_zone_sequence') == card.zone_change_sequence
                       for reference in references):
                continue
        for cost in ward_instances(state, card):
            out.append({'source_card_id': cid, 'controller': card.controller, 'label': f'{card.name} ward {cost}',
                        'effect_key': 'ward_payment', 'payload': {'ward_cost': cost, 'ward_incarnation': object_incarnation(card)}})
    return out


def mark_stack_targets(state, item):
    from rules_engine.events import _push_triggers
    ids = target_ids(item.payload)
    previous = set(item.payload.get('__last_target_ids') or [])
    specs = item.payload.pop('__ward_trigger_specs', None)
    if specs is None:
        specs = [spec for spec in capture_ward_triggers(state, item.controller, item.payload)
                 if spec['source_card_id'] not in previous]
    item.payload['__last_target_ids'] = ids
    triggers = [{**spec, 'payload': {**spec['payload'], 'target_stack_id': item.id}} for spec in specs]
    _push_triggers(state, 'becomes_target', triggers)


def resolved_cost(state, payload, controller):
    cost = parse_ward_cost(payload['ward_cost'])
    if cost and cost['kind'] == 'player_counter_mana':
        amount = counter_count(state.players[controller], cost['counter'])
        cost = {'kind': 'mana', 'cost': cost['template'].replace('{X}', '{'+str(amount)+'}')}
    if cost and cost['kind'] == 'power_life':
        from rules_engine.continuous import effective_power
        card = state.cards.get(payload.get('__source_card_id'))
        current = card and card.zone == Zone.BATTLEFIELD and object_incarnation(card) == payload['ward_incarnation']
        power = effective_power(state, card.id) if current else (payload.get('__source_lki') or {}).get('power', 0)
        cost = {'kind': 'life', 'amount': max(0, int(power or 0))}
    return cost


def payment_cards(state, player, cost):
    if cost['kind'] == 'discard':
        return list(state.players[player].hand)
    if cost['kind'] != 'sacrifice':
        return []
    subject, quality = cost['subject'], cost['quality']
    return [cid for cid in state.players[player].battlefield
            if (subject == 'permanent' or (subject == 'artifact or creature' and {'Artifact', 'Creature'} & set(effective_types(state, state.cards[cid]))) or subject.title() in effective_types(state, state.cards[cid]))
            and (quality != 'legendary' or 'Legendary' in state.cards[cid].type_line)
            and (quality != 'nonland' or 'Land' not in effective_types(state, state.cards[cid]))
            and (quality != 'nontoken' or not state.cards[cid].is_token)]


def can_pay(state, player, cost):
    if cost is None:
        return False
    if cost['kind'] == 'mana':
        from rules_engine.mana import can_pay_with_pool_and_lands
        return can_pay_with_pool_and_lands(state, player, cost['cost'], payment_kind='ward')
    if cost['kind'] == 'life':
        from rules_engine.replacement import can_pay_life
        return can_pay_life(state, player, cost['amount'])
    return len(payment_cards(state, player, cost)) >= cost['amount']


def resolve_ward(state, controller, payload):
    item = next((i for i in state.stack if i.id == payload['target_stack_id']), None)
    if item is None:
        return
    cost = resolved_cost(state, payload, controller)
    display_cost = payload['ward_cost']
    if cost and parse_ward_cost(display_cost)['kind'] == 'player_counter_mana':
        display_cost = f"{cost['cost']} ({display_cost})"
    state.pending_mechanic_choice = {'kind': 'ward_payment', 'player_id': item.controller, 'count': 1,
        'options': ['decline', 'pay'] if can_pay(state, item.controller, cost) else ['decline'],
        'option_labels': {'pay': f"Pay ward: {display_cost}", 'decline': 'Decline ward payment'},
        'label': f"Ward for {item.label}: {display_cost}", 'ward_cost': cost,
        'effect_payload': dict(payload), 'controller': controller}
    state.priority_player = item.controller
    state.passed_priority = set()


def finish_ward_choice(state, player, action):
    from rules_engine.stack_engine import resume_paused_resolution
    from effects.handlers import counter_spell, counter_ability
    from rules_engine.targeting import stack_object_kind
    pending = state.pending_mechanic_choice
    ids = action.get('card_ids')
    if (pending['player_id'] != player or not isinstance(ids, list) or len(ids) != pending['count']
            or len(set(ids)) != len(ids) or any(cid not in pending['options'] for cid in ids)):
        return False
    payload, cost = pending['effect_payload'], pending['ward_cost']
    item = next((i for i in state.stack if i.id == payload['target_stack_id']), None)
    if pending['kind'] == 'ward_payment' and ids == ['pay']:
        if not can_pay(state, player, cost):
            return False
        if cost['kind'] in {'discard', 'sacrifice'}:
            pending.update(kind='ward_cost_cards', options=payment_cards(state, player, cost), count=cost['amount'], label=f"Choose cards to {cost['kind']} for ward")
            return True
    paid = ids != ['decline']
    if paid:
        if not can_pay(state, player, cost):
            return False
        if cost['kind'] == 'mana':
            from rules_engine.mana import auto_pay_cost
            if not auto_pay_cost(state, player, cost['cost'], payment_kind='ward'):
                return False
        elif cost['kind'] == 'life':
            from rules_engine.replacement import pay_life
            pay_life(state, player, cost['amount'])
        elif cost['kind'] == 'discard':
            from rules_engine.zone_actions import discard_selected
            if any(cid not in payment_cards(state, player, cost) for cid in ids) or not discard_selected(state, player, ids):
                return False
        else:
            if any(cid not in payment_cards(state, player, cost) for cid in ids):
                return False
            from rules_engine.zone_actions import sacrifice_selected
            if not sacrifice_selected(state, player, ids):
                return False
        payment = 'counter tax' if pending['kind'] == 'counter_payment' else 'ward'
        state.log.append(f"{state.players[player].name} pays {payment}: {payload['ward_cost']}.")
    elif item is not None:
        handler = counter_spell if stack_object_kind(state, item) == 'spell' else counter_ability
        handler(state, pending['controller'], {'target_stack_id': item.id,
            'uncounterable': bool(payload.get('uncounterable')) if pending['kind'] == 'counter_payment' else False})
    state.pending_mechanic_choice = None
    resume_paused_resolution(state, pending)
    return True
