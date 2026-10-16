"""Completed nonmana activations and complete paid, referred-ability copies."""
from copy import deepcopy
from dataclasses import asdict
import re

from game_state.state import StackItem, Zone, object_incarnation


CLAUSE = re.compile(
    r"Whenever you activate an ability, if it isn't a mana ability, "
    r"(you may pay (?:\{(?:\d{1,6}|[WUBRGCS])\})+\. If you do, "
    r"copy that ability\. You may choose new targets for the copy\.)", re.I)
BODY = re.compile(r'copy that ability\. You may choose new targets for the copy\.', re.I)


def compile_clause(clause):
    if not isinstance(clause, str) or len(clause) > 8192:
        return None
    match = CLAUSE.fullmatch(' '.join(clause.split()))
    return match[1] if match else None


def _retained_item(data):
    if (type(data) is not dict or type(data.get('payload')) is not dict
            or type(data.get('controller')) is not int
            or any(type(data.get(key)) is not str or not data[key]
                   for key in ('id', 'source_card_id', 'effect_key', 'label'))
            or data['payload'].get('__announced_stack_kind') != 'activated'
            or data['payload'].get('__completed_nonmana_activation') is not True
            or data['payload'].get('__stack_copy_kind')):
        raise ValueError('Invalid retained completed activation')
    return StackItem(**deepcopy(data))


def record_activation_complete(state, item):
    if (not any(current is item for current in state.stack)
            or item.controller not in state.players
            or (item.payload or {}).get('__announced_stack_kind') != 'activated'):
        raise ValueError('Activation completion requires its actual announced item')
    if item.payload.get('__stack_copy_kind') or item.payload.get('__completed_nonmana_activation'):
        return
    item.payload['__completed_nonmana_activation'] = True
    from rules_engine.events import emit_event
    emit_event(state, 'nonmana_ability_activated', {
        'controller': item.controller, 'source_stack_id': item.id,
        'original_item': asdict(item),
    })


def collect_activation_copy_triggers(state, payload):
    original = _retained_item(payload.get('original_item'))
    if (original.controller != payload.get('controller')
            or original.id != payload.get('source_stack_id')):
        raise ValueError('Activation event does not bind its completed item')
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.paid_triggers import compile_paid_instruction
    out = []
    for cid in state.players[original.controller].battlefield:
        source = state.cards[cid]
        if (source.zone != Zone.BATTLEFIELD or source.controller != original.controller
                or printed_abilities_suppressed(state, cid)):
            continue
        for clause in source.oracle_text.splitlines():
            instruction = compile_clause(clause)
            if instruction is None:
                continue
            key, data = compile_paid_instruction(state, source, source.controller, instruction, payload)
            data.update(__activation_copy_clause=clause, __activation_copy_source={
                'card_id': cid, 'incarnation': object_incarnation(source),
                'zone_change_sequence': source.zone_change_sequence,
                'controller': source.controller})
            out.append({'source_card_id': cid, 'controller': source.controller,
                        'label': source.name + ' activation trigger', 'effect_key': key, 'payload': data})
    return out


def paid_copy_body(body, event_payload):
    if BODY.fullmatch(body) is None:
        return None
    original = _retained_item(event_payload.get('original_item'))
    if (original.id != event_payload.get('source_stack_id')
            or original.controller != event_payload.get('controller')):
        raise ValueError('Paid copy lacks its genuine activation binding')
    return 'copy_referred_ability', {'__activation_copy_original': asdict(original)}


def retain_countered_activation(state, item):
    """Refresh only existing referred copies before the actual original departs."""
    if (item.payload or {}).get('__announced_stack_kind') != 'activated':
        return
    payloads = [frame.payload for frame in state.stack]
    for triggers in (state.staged_triggers, state.cleanup_deferred_triggers):
        payloads.extend(trigger['payload'] for trigger in triggers)
    for group in (state.pending_trigger_order or {}).get('groups', {}).values():
        payloads.extend(trigger['payload'] for trigger in group)
    for data in payloads:
        receipt = data.get('__activation_copy_original')
        if receipt is not None and _retained_item(receipt).id == item.id:
            data['__activation_copy_original'] = asdict(item)


def resolve_copy_referred_ability(state, controller, payload):
    if compile_clause(payload.get('__activation_copy_clause')) != payload.get('__optional_payment_instruction'):
        raise ValueError('Referred ability copy lost its complete paid clause')
    original = _retained_item(payload.get('__activation_copy_original'))
    source = payload.get('__activation_copy_source')
    if (type(source) is not dict or source.get('controller') != original.controller
            or not payload.get('__optional_payment_paid')):
        raise ValueError('Referred ability copy lacks its source or actual payment')
    live = next((item for item in state.stack if item.id == original.id), None)
    if live is not None:
        if live.source_card_id != original.source_card_id or live.controller != original.controller:
            raise ValueError('Referred activation identity changed')
        original = live
    from effects.handlers import _copy_stack_object
    _copy_stack_object(state, controller, {'may_choose_new_targets': True}, 'ability', retained_item=original)
