"""Resumable scalar counter events, with effect-only replacement provenance."""
from __future__ import annotations

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
        (r'if one or more \+1/\+1 counters would be put on a creature you control, that many plus one \+1/\+1 counters are put on it instead', 'controlled_plus_creature', 'add'),
        (r'if one or more \+1/\+1 counters would be put on a creature you control, twice that many \+1/\+1 counters are put on (?:it|that creature) instead', 'controlled_plus_creature', 'double'),
        (r'if one or more \+1/\+1 counters would be put on a creature, twice that many \+1/\+1 counters are put on (?:it|that creature) instead', 'plus_creature', 'double'),
        (r'if one or more \+1/\+1 counters would be put on a permanent you control, that many plus one \+1/\+1 counters are put on that permanent instead', 'controlled_plus_permanent', 'add'),
    )
    return next(((scope, op) for pattern, scope, op in patterns if re.fullmatch(pattern, line)), None)


def counter_options(state, controller, payload, used=()):
    player = payload.get('target_player')
    card = state.cards.get(payload.get('target_card_id'))
    kind = payload['counter']
    out = [dict(option) for option in payload.get('__counter_entry_modifiers', [])
           if option['source_id'] not in used]
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            source = state.cards.get(cid)
            if source is None or source.zone != Zone.BATTLEFIELD:
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
                    or (scope == 'controlled_artifact_creature' and controlled and bool({'Artifact', 'Creature'} & set(card.types)))
                    or (scope == 'recipient_self' and player == source.controller)
                    or (scope == 'placer_controlled' and controller == source.controller
                        and (player == source.controller or controlled and bool({'Creature', 'Planeswalker'} & set(card.types))))
                    or (scope == 'controlled_plus_creature' and controlled and 'Creature' in card.types and kind == '+1/+1')
                    or (scope == 'plus_creature' and card is not None and 'Creature' in card.types and kind == '+1/+1')
                    or (scope == 'controlled_plus_permanent' and controlled and kind == '+1/+1')
                )
                if applies:
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
    player = payload.get('target_player')
    card = state.cards.get(payload.get('target_card_id'))
    kind = payload['counter']
    amount = max(0, int(payload.get('amount', 1)))
    if not amount:
        return 0
    if counter_placement_forbidden(state, kind, target_player=player, target_card_id=payload.get('target_card_id')):
        target = state.players[player] if player is not None else card
        state.log.append(f'{target.name} cannot get {kind} counters.')
        return 0
    used = list(payload.get('__counter_used') or [])
    selected = payload.get('__counter_choice')
    while amount:
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
        payload = {**payload, '__counter_is_effect': True}
        state.log.append(f"{chosen['name']} replaces {before} {kind} counters with {amount}.")
        selected = None
    return amount
