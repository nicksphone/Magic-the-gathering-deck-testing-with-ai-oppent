"""Resumable scalar counter events, with effect-only replacement provenance."""
from __future__ import annotations
from rules_engine.type_effects import effective_types

from functools import lru_cache
import re

from game_state.state import Zone
from rules_engine.counter_placement import counter_placement_forbidden
from rules_engine.oracle_text import without_reminder_text


@lru_cache(maxsize=4096)
def counter_modifier(line):
    """Recognize complete printed clauses, never a substring of a larger effect."""
    line = line.strip().lower().removesuffix('.')
    patterns = (
        (r'if an effect would put one or more counters on a permanent you control, it puts twice that many of those counters on that permanent instead', 'controlled_permanent', 'double'),
        (r'if you would put one or more counters on a permanent or player, put twice that many of each of those kinds of counters on that permanent or player instead', 'placer_self', 'double'),
        (r'if an opponent would put one or more counters on a permanent or player, they put half that many of each of those kinds of counters on that permanent or player instead, rounded down', 'placer_opponent', 'half'),
        (r'if one or more counters would be put on an artifact or creature you control, that many plus one of each of those kinds of counters are put on that permanent instead', 'controlled_artifact_creature', 'add'),
        (r'if you would get one or more counters, you get that many plus one of each of those kinds of counters instead', 'recipient_self', 'add'),
        (r'if you would put one or more counters on a creature or planeswalker you control or on yourself, put that many plus one of each of those kinds of counters on that permanent or player instead', 'placer_controlled', 'add'),
        (r'if one or more \+1/\+1 counters would be put on a creature you control, that many plus one \+1/\+1 counters are put on (?:it|that creature) instead', 'controlled_plus_creature', 'add'),
        (r'if one or more \+1/\+1 counters would be put on a creature you control, twice that many \+1/\+1 counters are put on (?:it|that creature) instead', 'controlled_plus_creature', 'double'),
        (r'if one or more \+1/\+1 counters would be put on a creature, twice that many \+1/\+1 counters are put on (?:it|that creature) instead', 'plus_creature', 'double'),
        (r'if one or more \+1/\+1 counters would be put on a permanent you control, that many plus one \+1/\+1 counters are put on that permanent instead', 'controlled_plus_permanent', 'add'),
    )
    return next(((scope, op) for pattern, scope, op in patterns if re.fullmatch(pattern, line)), None)


def counter_options(state, controller, payload, used=()):
    from rules_engine.continuous import printed_abilities_suppressed
    player = payload.get('target_player')
    card = state.cards.get(payload.get('target_card_id'))
    kind = payload['counter']
    context = payload.get('__counter_entry_context')
    if context is not None:
        from rules_engine.entry_counters import entry_counter_context_matches
        if not entry_counter_context_matches(state, payload):
            return []
    out = [dict(option) for option in payload.get('__counter_entry_modifiers', [])
           if option['source_id'] not in used]
    if payload.get('__intrinsic_entry_counter') and kind == '+1/+1':
        from rules_engine.entry_counters import intrinsic_entry_counter_options
        out.extend(intrinsic_entry_counter_options(state, controller, payload, used) or [])
    if payload.get('__next_entry_counter') and kind == '+1/+1':
        from rules_engine.entry_counters import retained_next_entry_options
        out.extend(retained_next_entry_options(state, controller, payload, used) or [])
    if context is not None and not payload.get('amount', 0):
        return [option for option in out if option.get('entry_producer')]
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            source = state.cards.get(cid)
            if source is None or source.zone != Zone.BATTLEFIELD:
                continue
            if printed_abilities_suppressed(state, cid):
                continue
            for index, line in enumerate(without_reminder_text(source.oracle_text).splitlines()):
                instruction = counter_modifier(line)
                ability_id = f'{cid}:counter:{index}'
                if instruction is None or ability_id in used:
                    continue
                scope, op = instruction
                controlled = card is not None and card.controller == source.controller
                applies = (
                    (scope == 'controlled_permanent' and controlled and payload.get('__counter_is_effect', True))
                    or (scope == 'placer_self' and controller == source.controller)
                    or (scope == 'placer_opponent' and controller != source.controller)
                    or (scope == 'controlled_artifact_creature' and controlled and bool({'Artifact', 'Creature'} & set(effective_types(state, card))))
                    or (scope == 'recipient_self' and player == source.controller)
                    or (scope == 'placer_controlled' and controller == source.controller
                        and (player == source.controller or controlled and bool({'Creature', 'Planeswalker'} & set(effective_types(state, card)))))
                    or (scope == 'controlled_plus_creature' and controlled and 'Creature' in effective_types(state, card) and kind == '+1/+1')
                    or (scope == 'plus_creature' and card is not None and 'Creature' in effective_types(state, card) and kind == '+1/+1')
                    or (scope == 'controlled_plus_permanent' and controlled and kind == '+1/+1')
                )
                if applies and (context is None or ability_id in {
                        receipt['source_id'] for receipt in context['source_references']}):
                    out.append({'source_id': ability_id, 'source_card_id': cid,
                                'name': source.name, 'operation': op, 'clause': line})
    return out


def modified_count(amount, op, operand=1):
    if op == 'double':
        return amount*2
    if op == 'half':
        return amount//2
    if op == 'add':
        return amount+operand
    if op == 'subtract':
        return max(0, amount-operand)
    raise ValueError(f'Unknown counter replacement operation: {op}')


def counter_effect_amount(state, controller, effect_key, payload):
    """Return final amount or None while the affected player's event is paused."""
    from copy import deepcopy
    retained_event = payload.get('__entry_counter_event') if payload.get('counter') == '+1/+1' else None
    player = payload.get('target_player')
    card = state.cards.get(payload.get('target_card_id'))
    kind = payload['counter']
    amount = max(0, int(payload.get('amount', 1)))
    entry_event = payload.get('__counter_entry_context') is not None
    if not amount and not entry_event:
        return 0
    if counter_placement_forbidden(state, kind, target_player=player, target_card_id=payload.get('target_card_id')):
        target = state.players[player] if player is not None else card
        state.log.append(f'{target.name} cannot get {kind} counters.')
        return 0
    used = list(payload.get('__counter_used') or [])
    selected = payload.get('__counter_choice')
    while amount or entry_event:
        if entry_event:
            payload = {**payload, 'amount': amount, '__counter_used': used}
        options = counter_options(state, controller, payload, used)
        if not options:
            break
        chosen = next((option for option in options if option['source_id'] == selected), None)
        if chosen is None and len(options) > 1:
            affected = player if player is not None else card.controller
            state.pending_replacement_choice = {
                'resume_kind': 'counter_event', 'event': 'counter_placement',
                'player_id': affected, 'controller': controller, 'counter_effect': effect_key,
                'counter_payload': {**payload, 'amount': amount, '__counter_used': used, '__counter_choice': None},
                'options': options,
                'forecast_options': counter_options(state, controller, {**payload, '__counter_is_effect': True}, used),
            }
            state.priority_player = affected
            state.passed_priority = set()
            return None
        chosen = chosen or options[0]
        used.append(chosen['source_id'])
        before = amount
        amount = modified_count(amount, chosen['operation'], chosen.get('operand', 1))
        if payload.get('__entry_counter_event') and kind == '+1/+1':
            event = deepcopy(payload['__entry_counter_event'])
            event['amount'] = amount
            event['applied_ids'] = list(used)
            event['history'].append({'source_id': chosen['source_id'],
                'role': ('intrinsic' if chosen.get('intrinsic_entry') else
                         'one_shot' if chosen.get('next_entry_producer') else
                         'resident' if chosen.get('entry_producer') else 'modifier'),
                'instruction_ref': chosen.get('instruction_ref', chosen['clause']), 'before': before, 'after': amount})
            payload = {**payload, '__entry_counter_event': event}
        payload = {**payload, '__counter_is_effect': True}
        state.log.append(f"{chosen['name']} replaces {before} {kind} counters with {amount}.")
        selected = None
    if retained_event is not None and retained_event is not payload['__entry_counter_event']:
        retained_event.clear()
        retained_event.update(payload['__entry_counter_event'])
    return amount


def counter_vector_options(state, controller, payload, used=()):
    """One replacement ability modifies every applicable kind in this event."""
    options = {}
    for kind, amount in sorted(payload['counter_amounts'].items()):
        if not amount:
            continue
        for option in counter_options(state, controller, {**payload, 'counter': kind}, used):
            entry = options.setdefault(option['source_id'], {**option, 'counter_kinds': []})
            entry['counter_kinds'].append(kind)
    return list(options.values())


def counter_effect_amounts(state, controller, effect_key, payload):
    """Prepare a multi-kind event without physically placing any counters."""
    amounts = {kind: max(0, int(value)) for kind, value in payload['counter_amounts'].items()}
    for kind in amounts:
        if counter_placement_forbidden(state, kind, target_player=payload.get('target_player'),
                                       target_card_id=payload.get('target_card_id')):
            amounts[kind] = 0
    used = list(payload.get('__counter_used') or [])
    selected = payload.get('__counter_choice')
    while any(amounts.values()):
        event = {**payload, 'counter_amounts': amounts}
        options = counter_vector_options(state, controller, event, used)
        if not options:
            break
        chosen = next((option for option in options if option['source_id'] == selected), None)
        if chosen is None and len(options) > 1:
            affected = payload.get('target_player')
            if affected is None:
                affected = state.cards[payload['target_card_id']].controller
            state.pending_replacement_choice = {
                'resume_kind': 'counter_event', 'event': 'counter_placement',
                'player_id': affected, 'controller': controller, 'counter_effect': effect_key,
                'counter_payload': {**event, '__counter_used': used, '__counter_choice': None},
                'options': options, 'forecast_options': options,
            }
            state.priority_player = affected
            state.passed_priority = set()
            return None
        chosen = chosen or options[0]
        used.append(chosen['source_id'])
        before = dict(amounts)
        for kind in chosen['counter_kinds']:
            amounts[kind] = modified_count(amounts[kind], chosen['operation'], chosen.get('operand', 1))
        state.log.append(f"{chosen['name']} replaces counters {before} with {amounts}.")
        payload = {**payload, '__counter_is_effect': True}
        selected = None
    return amounts
