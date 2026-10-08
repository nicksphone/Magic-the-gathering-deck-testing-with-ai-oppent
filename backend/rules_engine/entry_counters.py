"""Prepare supported entry counters before battlefield mutation or token creation."""
from rules_engine.type_effects import effective_types
from copy import copy, deepcopy
from dataclasses import asdict
import re

from game_state.state import CardInstance, StackItem, Zone
from rules_engine.counter_replacements import counter_effect_amount
from rules_engine.oracle_effects import extract_saga_chapters
from rules_engine.oracle_text import without_reminder_text


def entry_counter_modifier(line):
    """Admit only the complete resident, other-creature entry instruction."""
    if re.fullmatch(r'each other creature you control enters with an additional '
                    r'\+1/\+1 counter on it\.', line.strip(), re.I):
        return {'operation': 'add', 'operand': 1}
    return None


def resident_entry_counter_options(state, card, controller):
    from game_state.state import object_incarnation
    from rules_engine.basic_land_layer import layer_four_view
    from rules_engine.continuous import printed_abilities_suppressed
    types = layer_four_view(state, entering=card, controller=controller)[2].get(
        card.id, effective_types(state, card))
    if 'Creature' not in types:
        return []
    options = []
    for pid in sorted(state.players):
        for cid in state.players[pid].battlefield:
            source = state.cards.get(cid)
            if (source is None or source.zone != Zone.BATTLEFIELD or cid == card.id
                    or source.controller != controller
                    or printed_abilities_suppressed(state, cid)):
                continue
            for index, line in enumerate(source.oracle_text.splitlines()):
                instruction = entry_counter_modifier(line)
                if instruction:
                    options.append({**instruction,
                        'source_id': f'{cid}:entry:{object_incarnation(source)}:{source.zone_change_sequence}:{index}',
                        'source_card_id': cid, 'name': source.name, 'clause': line,
                        'entry_producer': True})
    return options


def intrinsic_x_entry_instruction(line):
    return bool(re.fullmatch(r'This creature enters with X \+1/\+1 counters on it\.',
                             line.strip(), re.I))


def prospective_entry_ability_view(state, card, controller):
    from game_state.state import assign_static_order_on_battlefield_entry
    from rules_engine.basic_land_layer import layer_four_view
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.query_context import rule_query_scope, query_cache
    query_state = copy(state)
    query_state.cards = dict(state.cards)
    projected = deepcopy(card)
    projected.zone = Zone.BATTLEFIELD
    projected.controller = controller
    query_state.cards[card.id] = projected
    assign_static_order_on_battlefield_entry(query_state, card.id)
    with rule_query_scope(query_state):
        query_cache(query_state)[layer_four_view] = layer_four_view(
            query_state, entering=projected, controller=controller)
        return {'types': effective_types(query_state, card.id),
                'printed_suppressed': printed_abilities_suppressed(query_state, card.id)}


def intrinsic_entry_counter_options(state, controller, payload, used=()):
    """None is an invalid retained proof; an empty list is valid but inapplicable."""
    from game_state.state import object_incarnation
    proof = payload.get('__intrinsic_entry_counter')
    if proof is None:
        return []
    if not isinstance(proof, dict):
        return None
    card = state.cards.get(proof.get('source_card_id'))
    frame = payload.get('entry_item')
    entry = payload.get('entry_payload')
    if (card is None or card.zone != Zone.STACK or not isinstance(frame, dict)
            or not isinstance(entry, dict) or not isinstance(frame.get('payload'), dict)
            or frame.get('source_card_id') != card.id or frame.get('controller') != controller
            or not isinstance(frame.get('id'), str) or not frame['id']):
        return None
    x = entry.get('x_value', 0)
    if (type(x) is not int or x < 0 or type(proof.get('locked_x')) is not int
            or type(frame['payload'].get('x_value', 0)) is not int
            or frame['payload'].get('x_value', 0) != x):
        return None
    for retained in (entry, frame['payload']):
        announced = retained.get('__announced_targets')
        if (announced is not None and (not isinstance(announced, dict)
                or type(announced.get('x_value', 0)) is not int
                or announced.get('x_value', 0) != x)):
            return None
    index = proof.get('clause_index')
    lines = card.oracle_text.splitlines()
    if type(index) is not int or not 0 <= index < len(lines) or not intrinsic_x_entry_instruction(lines[index]):
        return None
    ref = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    expected = {'kind': 'intrinsic_x_plus_one',
        'source_id': f'{card.id}:intrinsic:{ref["incarnation"]}:{ref["zone_change_sequence"]}:{index}',
        'source_card_id': card.id, 'recipient_reference': ref,
        'recipient_zone': card.zone.value, 'recipient_owner': card.owner,
        'prospective_controller': controller, 'clause_index': index, 'clause': lines[index],
        'locked_x': x, 'frame_kind': 'permanent_spell_entry'}
    if proof != expected:
        return None
    view = prospective_entry_ability_view(state, card, controller)
    if (x == 0 or proof['source_id'] in used or view['printed_suppressed']
            or 'Creature' not in view['types']):
        return []
    return [{'source_id': proof['source_id'], 'source_card_id': card.id,
             'name': card.name, 'operation': 'add', 'operand': x,
             'clause': proof['clause'], 'entry_producer': True, 'intrinsic_entry': True}]


def retained_next_entry_options(state, controller, payload, used=()):
    """Validate inherited state instructions without inventing source provenance."""
    import hashlib
    import json
    from game_state.state import object_incarnation
    receipt = payload.get('__next_entry_counter')
    from rules_engine.next_creature_entry_trigger import entry_receipt, entry_options
    if isinstance(receipt, dict) and receipt.get('kind') == 'native_spell_bound':
        return entry_options(state, controller, payload, used, retained_next_entry_options)
    if receipt is None:
        frame = payload.get('entry_item')
        if isinstance(frame, dict) and entry_receipt(state, frame) is not None:
            return None
        card = state.cards.get(frame.get('source_card_id')) if isinstance(frame, dict) else None
        if card is not None and 'Creature' in effective_types(state, card) and any(
                '__native_next_cast' not in record and record.get('controller') == controller and record.get('expires_turn', state.turn) == state.turn
                for record in state.pending_entry_counters):
            return None
        return []
    if not isinstance(receipt, dict):
        return None
    index = receipt.get('index')
    frame = payload.get('entry_item')
    if (type(index) is not int or not 0 <= index < len(state.pending_entry_counters)
            or not isinstance(frame, dict) or frame.get('controller') != controller):
        return None
    record = state.pending_entry_counters[index]
    card = state.cards.get(frame.get('source_card_id'))
    if (not isinstance(record, dict) or '__native_next_cast' in record or card is None or card.zone != Zone.STACK
            or record != receipt.get('record') or record.get('controller') != controller
            or record.get('expires_turn', state.turn) != state.turn):
        return None
    try:
        fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
            ensure_ascii=True, allow_nan=False).encode()).hexdigest()
        amount = int(record.get('amount', 1))
    except (ValueError, TypeError):
        return None
    reference = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
    expected = {'index': index, 'record': record, 'fingerprint': fingerprint,
        'recipient_id': card.id, 'recipient_reference': reference, 'recipient_owner': card.owner,
        'recipient_zone': card.zone.value, 'frame_id': frame.get('id'), 'controller': controller,
        'source_id': f'pending-entry:{frame.get("id")}:{index}:{fingerprint}'}
    if receipt != expected or not isinstance(frame.get('id'), str) or not frame['id']:
        return None
    if ('__counter_entry_context' in payload
            and (type(payload.get('consume_entry_counter')) is not int
                 or payload['consume_entry_counter'] != index)):
        return None
    # Check native origins against their retained frame, never a live BF source.
    origin = record.get('__entry_origin')
    if origin is not None:
        from effects.handlers import retained_next_creature_entry_origin
        if not isinstance(origin, dict):
            return None
        rebuilt = retained_next_creature_entry_origin(state, controller, {
            '__resolving_item': origin.get('frame'),
            '__one_shot_child_position': origin.get('child_position'),
            'counter': record.get('counter', '+1/+1'), 'amount': record.get('amount', 1)})
        if rebuilt is None or rebuilt != origin:
            return None
    if (record.get('counter', '+1/+1') != '+1/+1' or payload.get('counter', '+1/+1') != '+1/+1'
            or amount <= 0 or receipt['source_id'] in used):
        return []
    return [{'source_id': receipt['source_id'],
             'name': 'Retained next-creature entry effect (' + ('native provenance' if origin else 'legacy provenance unknown') + ')',
             'operation': 'add', 'operand': amount, 'clause': None,
             'instruction_ref': fingerprint, 'entry_producer': True, 'next_entry_producer': True}]


def next_entry_commit_matches(state, item, payload):
    receipt = payload.get('__consume_entry_counter_receipt')
    if isinstance(receipt, dict) and receipt.get('kind') == 'native_spell_bound':
        from dataclasses import asdict
        legacy = receipt.get('legacy')
        completion = payload.get('__entry_counter_completion')
        return (payload.get('__consume_entry_counter') == (legacy.get('index') if legacy else None)
                and retained_next_entry_options(state, item.controller, {
                    'entry_item': asdict(item), '__next_entry_counter': receipt}) is not None
                and isinstance(completion, dict) and completion.get('entry_item') == asdict(item)
                and completion.get('__next_entry_counter') == receipt
                and completion.get('amount') == payload.get('__entry_counters_ready', {}).get('+1/+1')
                and entry_counter_context_matches(state, completion))
    if receipt is None:
        from dataclasses import asdict
        return ('__consume_entry_counter' not in payload
                and retained_next_entry_options(state, item.controller, {'entry_item': asdict(item)}) is not None)
    if not isinstance(receipt, dict) or payload.get('__consume_entry_counter') != receipt.get('index'):
        return False
    from dataclasses import asdict
    if retained_next_entry_options(state, item.controller, {
            'entry_item': asdict(item), '__next_entry_counter': receipt}) is None:
        return False
    if receipt['record'].get('counter', '+1/+1') == '+1/+1':
        completion = payload.get('__entry_counter_completion')
        if (not isinstance(completion, dict) or completion.get('entry_item') != asdict(item)
                or completion.get('__next_entry_counter') != receipt
                or completion.get('amount') != payload.get('__entry_counters_ready', {}).get('+1/+1')
                or not entry_counter_context_matches(state, completion)):
            return False
    return True


def entry_counter_context_matches(state, payload):
    """Validate retained objects before a pending entry is allowed to resume."""
    from game_state.state import object_incarnation
    from rules_engine.continuous import printed_abilities_suppressed
    context = payload.get('__counter_entry_context')
    if context is None:
        return (not any(payload.get(key) for key in (
            '__counter_entry_producers', '__intrinsic_entry_counter', '__entry_counter_event'))
            and retained_next_entry_options(state, payload.get('entry_item', {}).get('controller'), payload) is not None)
    if not isinstance(context, dict):
        return False
    receipts = context.get('source_references')
    producers = payload.get('__counter_entry_producers')
    controller = context.get('recipient_controller')
    intrinsic = payload.get('__intrinsic_entry_counter')
    next_entry = payload.get('__next_entry_counter')
    next_options = retained_next_entry_options(state, controller, payload)
    if next_options is None:
        return False
    if (not isinstance(receipts, list) or (not receipts and not intrinsic and not next_entry)
            or not all(isinstance(receipt, dict) for receipt in receipts)
            or not isinstance(producers, list) or (not producers and not intrinsic and not next_entry)
            or controller not in state.players):
        return False
    if ('target_card_id' in payload and payload['target_card_id'] != context.get('recipient_id')):
        return False
    if 'entry_item' in payload:
        if (payload['entry_item'].get('source_card_id') != context.get('recipient_id')
                or payload['entry_item'].get('controller') != controller):
            return False
    elif 'entry_targets' in payload:
        index = payload.get('entry_target_index')
        targets = payload['entry_targets']
        if not isinstance(index, int) or not isinstance(targets, list) or not 0 <= index < len(targets):
            return False
        target = targets[index]
        if (target.get('card_id', target.get('candidate', {}).get('id')) != context.get('recipient_id')
                or target.get('controller') != controller):
            return False
    card = state.cards.get(context.get('recipient_id'))
    if card is None:
        candidate = next((target.get('candidate') for target in payload.get('entry_targets', [])
                          if target.get('candidate', {}).get('id') == context.get('recipient_id')), None)
        if candidate is None or candidate != context.get('candidate'):
            return False
        card = CardInstance(**{**candidate, 'zone': Zone(candidate['zone'])})
    if (card.zone.value != context.get('recipient_zone')
            or card.owner != context.get('recipient_owner')
            or {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
            != context.get('recipient_reference')):
        return False
    if (intrinsic is None and payload.get('entry_item')
            and any(intrinsic_x_entry_instruction(line) for line in card.oracle_text.splitlines())):
        return False
    if intrinsic is None and next_entry is None and '__entry_counter_event' in payload:
        return False
    if intrinsic is not None and intrinsic_entry_counter_options(state, controller, payload) is None:
        return False
    if (intrinsic is not None or next_entry is not None and (
            next_entry.get('kind') == 'native_spell_bound' or next_entry['record'].get('counter', '+1/+1') == '+1/+1')) and payload.get('counter', '+1/+1') == '+1/+1':
        if intrinsic is None and not next_entry:
            return False
        event = payload.get('__entry_counter_event')
        expected_id = (intrinsic or next_entry)['source_id'] + ':entry-event:' + payload['entry_item']['id']
        if (not isinstance(event, dict) or event.get('version') != 1
                or event.get('event_id') != expected_id or event.get('counter') != '+1/+1'
                or event.get('recipient_reference') != context['recipient_reference']
                or not isinstance(event.get('history'), list)
                or event.get('applied_ids') != (payload.get('__counter_used') or [])):
            return False
        if ('__counter_entry_modifiers' in payload
                and payload['__counter_entry_modifiers'] != producers):
            return False
        from rules_engine.counter_replacements import counter_modifier, modified_count
        amount = 0
        seen = []
        for step in event['history']:
            if (not isinstance(step, dict) or step.get('source_id') in seen
                    or type(step.get('before')) is not int or type(step.get('after')) is not int
                    or step.get('before') != amount):
                return False
            source_id = step.get('source_id')
            if intrinsic is not None and source_id == intrinsic['source_id']:
                operation, operand, role, clause = 'add', intrinsic['locked_x'], 'intrinsic', intrinsic['clause']
                if not intrinsic_entry_counter_options(state, controller, payload):
                    return False
            elif source_id in {option['source_id'] for option in next_options}:
                option = next(option for option in next_options if option['source_id'] == source_id)
                operation, operand, role, clause = 'add', option['operand'], 'one_shot', option['instruction_ref']
            elif source_id in {option['source_id'] for option in producers}:
                option = next(option for option in producers if option['source_id'] == source_id)
                operation, operand, role, clause = option['operation'], option['operand'], 'resident', option['clause']
            else:
                receipt = next((receipt for receipt in receipts if receipt.get('source_id') == source_id), None)
                instruction = counter_modifier(receipt['clause']) if receipt else None
                if instruction is None or amount <= 0:
                    return False
                operation, operand, role, clause = instruction[1], 1, 'modifier', receipt['clause']
            amount = modified_count(amount, operation, operand)
            if step != {'source_id': source_id, 'role': role, 'instruction_ref': clause,
                        'before': step['before'], 'after': amount}:
                return False
            seen.append(source_id)
        if (seen != event['applied_ids'] or event.get('amount') != amount
                or payload.get('amount', amount) != amount):
            return False
    for receipt in receipts:
        source = state.cards.get(receipt.get('source_card_id'))
        if (source is None or source.zone != Zone.BATTLEFIELD
                or source.controller != receipt.get('controller')
                or not any(source.id in player.battlefield for player in state.players.values())
                or printed_abilities_suppressed(state, source.id)
                or {'incarnation': object_incarnation(source), 'zone_change_sequence': source.zone_change_sequence}
                != receipt.get('reference')
                or receipt.get('clause') not in source.oracle_text.splitlines()):
            return False
        try:
            index = int(receipt['source_id'].rsplit(':', 1)[1])
        except (KeyError, AttributeError, ValueError):
            return False
        lines = (source.oracle_text.splitlines() if receipt['source_id'] in {
            option['source_id'] for option in producers}
            else without_reminder_text(source.oracle_text).splitlines())
        if index < 0 or index >= len(lines) or lines[index] != receipt.get('clause'):
            return False
        if (receipt['source_id'] not in {option['source_id'] for option in producers}
                and receipt['source_id'] != f'{source.id}:counter:{index}'):
            return False
    excluded = context.get('batch_recipient_ids')
    if not isinstance(excluded, list):
        return False
    expected = [option for option in resident_entry_counter_options(state, card, controller)
                if option['source_card_id'] not in excluded]
    if producers != expected:
        return False
    if any(not any(receipt.get('source_id') == option['source_id']
                   and receipt.get('source_card_id') == option['source_card_id']
                   and receipt.get('clause') == option['clause'] for receipt in receipts)
           for option in producers):
        return False
    if any(option.get('entry_producer') and option not in producers
           for option in payload.get('__counter_entry_modifiers', [])):
        return False
    return True


def begin_spell_entry(state, item, payload):
    resume_spell_entry(state, item.controller, {
        'entry_item': asdict(item), 'entry_payload': deepcopy(payload),
        'entry_prepared': {}, 'entry_index': 0,
    })
    pending = state.pending_mechanic_choice
    if pending and pending.get('kind') == 'entry_mode' and not state.pending_replacement_choice:
        from rules_engine.retained_counter_prohibition import current
        published = next((frame for frame in state.stack if frame.id == pending.get('__stack_id')), None)
        if (published is not None and published.effect_key == 'modal_entry'
                and published.source_card_id == item.source_card_id
                and not any(frame.id == item.id for frame in state.stack)
                and current(state, published.payload.get('__counter_source_ref'))):
            return True
    return not (state.pending_mechanic_choice or state.pending_replacement_choice)


def resume_spell_entry(state, controller, payload):
    from rules_engine.stack_engine import finish_stack_resolution
    card = state.cards.get(payload['entry_item']['source_card_id'])
    if card is None or card.zone != Zone.STACK:
        return
    data = deepcopy(payload)
    if prepare_entry_counters(state, controller, data, card, 'permanent_spell_entry'):
        finish_stack_resolution(state, StackItem(**data['entry_item']), data['entry_payload'])


def prepare_counter_entries(state, controller, cards, effect_key, payload, *, entry_payload=None, controllers=None, projections=None):
    """Reenter the route with a ready packet; True means caller must stop here."""
    if '__entry_counters_by_id' in payload:
        return False
    options = deepcopy(entry_payload if entry_payload is not None else payload)
    if entry_payload is None:
        for key in ('x_value', '__escaped', '__phyrexian_life_symbols'):
            options.pop(key, None)
    resume_entry_batch(state, controller, {
        'entry_targets': [({**({'card_id': card.id} if card.id in state.cards else {'candidate': asdict(card)}),
                           'controller': (controllers or {}).get(card.id, controller),
                           **({'projection': asdict(projections[card.id])} if card.id in (projections or {}) else {})})
                          for card in cards],
        'entry_target_index': 0, 'entry_results': {},
        'entry_effect': effect_key, 'entry_completion_payload': deepcopy(payload),
        'entry_options': options, 'entry_completion_controller': controller,
    })
    return True


def resume_entry_batch(state, controller, payload):
    from effects.registry import resolve_effect
    data = deepcopy(payload)
    while data['entry_target_index'] < len(data['entry_targets']):
        target = data['entry_targets'][data['entry_target_index']]
        if 'candidate' in target:
            raw = target['candidate']
            card = CardInstance(**{**raw, 'zone': Zone(raw['zone'])})
        else:
            card = state.cards.get(target['card_id'])
            if card is None or card.zone == Zone.BATTLEFIELD:
                state.log.append('Entry packet lost its off-battlefield recipient; entry aborted.')
                return
            if 'projection' in target:
                raw = target['projection']
                card = CardInstance(**{**raw, 'zone': Zone(raw['zone'])})
        data.setdefault('entry_payload', deepcopy(data['entry_options']))
        data.setdefault('entry_prepared', {})
        data.setdefault('entry_index', 0)
        if not prepare_entry_counters(state, target.get('controller', controller), data, card, 'permanent_entry_counters'):
            return
        data['entry_results'][card.id] = data['entry_payload']['__entry_counters_ready']
        data['entry_target_index'] += 1
        for key in ('entry_payload', 'entry_prepared', 'entry_index', 'entry_counts', 'consume_entry_counter',
                    '__counter_entry_context', '__counter_entry_producers',
                    '__intrinsic_entry_counter', '__entry_counter_event', '__next_entry_counter'):
            data.pop(key, None)
    staged_here = not state.trigger_staging
    if staged_here:
        state.trigger_staging = True
        state.trigger_staging_event = 'entry_batch'
    resolve_effect(state, data.get('entry_completion_controller', controller), data['entry_effect'], {
        **data['entry_completion_payload'], '__entry_counters_by_id': data['entry_results'],
        '__entry_candidates': [target['candidate'] for target in data['entry_targets'] if 'candidate' in target],
    })
    if staged_here and not (state.pending_mechanic_choice or state.pending_replacement_choice):
        from rules_engine.events import flush_staged_triggers
        flush_staged_triggers(state)


def commit_entry_counters(state, card, payload):
    from rules_engine.counter_placement import put_counters
    if 'Planeswalker' in effective_types(state, card):
        card.printed_characteristics.setdefault('loyalty', card.loyalty)
        card.loyalty = 0
    for kind, amount in payload['__entry_counters_by_id'].get(card.id, {}).items():
        put_counters(state, kind, amount, target_card_id=card.id, placement_checked=True)


def prepare_entry_counters(state, controller, data, card, resume_effect):
    from rules_engine.card_faces import day_night_entry_face
    card = day_night_entry_face(state, card)
    entry = data['entry_payload']
    if (data.get('entry_item') and '__next_entry_counter' not in data
            and '__counter_entry_context' not in data and 'Creature' in effective_types(state, card)):
        import hashlib
        import json
        from game_state.state import object_incarnation
        for index, record in enumerate(state.pending_entry_counters):
            if '__native_next_cast' not in record and record.get('controller') == controller and record.get('expires_turn', state.turn) == state.turn:
                fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()
                frame_id = data['entry_item']['id']
                data['__next_entry_counter'] = {
                    'index': index, 'record': deepcopy(record), 'fingerprint': fingerprint,
                    'recipient_id': card.id, 'recipient_reference': {
                        'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence},
                    'recipient_owner': card.owner, 'recipient_zone': card.zone.value,
                    'frame_id': frame_id, 'controller': controller,
                    'source_id': f'pending-entry:{frame_id}:{index}:{fingerprint}'}
                data['consume_entry_counter'] = index
                break
    if (data.get('entry_item') and '__counter_entry_context' not in data):
        from rules_engine.next_creature_entry_trigger import entry_receipt
        native = entry_receipt(state, data['entry_item'])
        if native is False:
            from rules_engine.action_validation import ActionRejected
            raise ActionRejected('Stale native spell-bound entry receipt')
        if native is not None:
            native['legacy'] = data.get('__next_entry_counter')
            data['__next_entry_counter'] = native
    if any(line.strip().lower().startswith('this creature enters with x +1/+1 counters')
           and not intrinsic_x_entry_instruction(line) for line in card.oracle_text.splitlines()):
        state.log.append('Unknown complete intrinsic-X entry instruction; entry preparation refused.')
        return False
    if '__counter_entry_context' not in data:
        from game_state.state import object_incarnation
        from rules_engine.counter_replacements import counter_options
        excluded = {target.get('card_id', target.get('candidate', {}).get('id'))
                    for target in data.get('entry_targets', [])}
        producers = [option for option in resident_entry_counter_options(state, card, controller)
                     if option['source_card_id'] not in excluded]
        intrinsic_lines = [(index, line) for index, line in enumerate(card.oracle_text.splitlines())
                           if intrinsic_x_entry_instruction(line)]
        if len(intrinsic_lines) > 1:
            state.log.append('Repeated intrinsic-X entry instructions need an explicit producer contract.')
            return False
        if intrinsic_lines and data.get('entry_item'):
            index, line = intrinsic_lines[0]
            ref = {'incarnation': object_incarnation(card), 'zone_change_sequence': card.zone_change_sequence}
            data['__intrinsic_entry_counter'] = {
                'kind': 'intrinsic_x_plus_one',
                'source_id': f'{card.id}:intrinsic:{ref["incarnation"]}:{ref["zone_change_sequence"]}:{index}',
                'source_card_id': card.id, 'recipient_reference': ref,
                'recipient_zone': card.zone.value, 'recipient_owner': card.owner,
                'prospective_controller': controller, 'clause_index': index, 'clause': line,
                'locked_x': entry.get('x_value', 0), 'frame_kind': 'permanent_spell_entry'}
            data['__entry_counter_event'] = {'version': 1,
                'event_id': data['__intrinsic_entry_counter']['source_id'] + ':entry-event:' + data['entry_item']['id'],
                'recipient_reference': ref, 'counter': '+1/+1', 'amount': 0,
                'applied_ids': [], 'history': []}
        if ('__entry_counter_event' not in data and data.get('__next_entry_counter')
                and (data['__next_entry_counter'].get('kind') == 'native_spell_bound'
                     or data['__next_entry_counter']['record'].get('counter', '+1/+1') == '+1/+1')):
            data['__entry_counter_event'] = {'version': 1,
                'event_id': data['__next_entry_counter']['source_id'] + ':entry-event:' + data['entry_item']['id'],
                'recipient_reference': (
                    {key: data['__next_entry_counter']['reference'][key]
                     for key in ('incarnation', 'zone_change_sequence')}
                    if data['__next_entry_counter'].get('kind') == 'native_spell_bound'
                    else data['__next_entry_counter']['recipient_reference']),
                'counter': '+1/+1', 'amount': 0, 'applied_ids': [], 'history': []}
        if producers or data.get('__intrinsic_entry_counter') or data.get('__next_entry_counter'):
            original = state.cards.get(card.id)
            projected = copy(card)
            projected.controller = controller
            state.cards[card.id] = projected
            try:
                modifiers = counter_options(state, controller, {
                    'target_card_id': card.id, 'counter': '+1/+1', 'amount': 1,
                    '__counter_is_effect': True})
            finally:
                if original is None:
                    state.cards.pop(card.id, None)
                else:
                    state.cards[card.id] = original
            data['__counter_entry_producers'] = producers
            recipient = original or card
            data['__counter_entry_context'] = {
                'recipient_id': card.id, 'recipient_zone': recipient.zone.value,
                'recipient_owner': recipient.owner, 'recipient_controller': controller,
                'recipient_reference': {'incarnation': object_incarnation(recipient),
                                        'zone_change_sequence': recipient.zone_change_sequence},
                **({'candidate': asdict(card)} if original is None else {}),
                'batch_recipient_ids': sorted(value for value in excluded if value is not None),
                'source_references': [{
                    'source_id': option['source_id'], 'source_card_id': option['source_card_id'],
                    'clause': option['clause'], 'controller': state.cards[option['source_card_id']].controller,
                    'reference': {'incarnation': object_incarnation(state.cards[option['source_card_id']]),
                                  'zone_change_sequence': state.cards[option['source_card_id']].zone_change_sequence},
                } for option in producers + modifiers],
            }
    if not entry_counter_context_matches(state, data):
        return False
    chapters = extract_saga_chapters(card.oracle_text) if 'Saga' in card.type_line else []
    if (chapters and re.search(r'^read ahead\s*$', without_reminder_text(card.oracle_text), re.I | re.M)
            and '__read_ahead_chapter' not in entry):
        options = [str(number) for number in range(1, max(ch['number'] for ch in chapters)+1)]
        state.pending_mechanic_choice = {
            'kind': 'saga_entry', 'player_id': controller, 'controller': controller,
            'options': options, 'option_labels': {value: f'Start at chapter {value}' for value in options},
            'effect_key': resume_effect, 'effect_payload': data,
            'label': f'Choose the starting chapter for {card.name}',
        }
        state.priority_player = controller
        state.passed_priority = set()
        return False
    if 'entry_counts' not in data:
        counts = {}
        from rules_engine.kicker import permanent_kicker
        kicker = permanent_kicker(card.oracle_text)
        if kicker and entry.get('__kicked'):
            counts.update(kicker.get('counters', {}))
        if 'Planeswalker' in effective_types(state, card) and card.loyalty is not None:
            loyalty = int(card.loyalty)
            counts['loyalty'] = loyalty
        if chapters:
            counts['lore'] = int(entry.get('__read_ahead_chapter', 1))
        if ('enters with x +1/+1 counters' in card.oracle_text.lower()
                and not data.get('__intrinsic_entry_counter')):
            counts['+1/+1'] = max(0, int(entry.get('x_value', 0)))
        if 'Creature' in effective_types(state, card):
            if entry.get('__escaped'):
                match = re.search(r'escapes with (a|one|\d+) \+1/\+1 counters?', card.oracle_text, re.I)
                if match:
                    counts['+1/+1'] = counts.get('+1/+1', 0) + (1 if match[1].lower() in {'a', 'one'} else int(match[1]))
            for index, pending in enumerate(state.pending_entry_counters if data.get('entry_item') else []):
                if '__native_next_cast' not in pending and pending.get('controller') == controller and pending.get('expires_turn', state.turn) == state.turn:
                    kind = pending.get('counter', '+1/+1')
                    if kind != '+1/+1':
                        counts[kind] = counts.get(kind, 0) + int(pending.get('amount', 1))
                    else:
                        counts.setdefault(kind, 0)
                    data['consume_entry_counter'] = index
                    break
        for kind, amount in (entry.get('counters') or {}).items():
            counts[kind] = counts.get(kind, 0) + max(0, int(amount))
        if data.get('__intrinsic_entry_counter') and counts.get('+1/+1', 0):
            # Legacy seeds have no retained instruction/PRE receipt. Do not
            # silently aggregate them ahead of a newly selectable producer.
            state.log.append('Intrinsic entry needs a retained mixed-producer origin; entry preparation refused.')
            return False
        if (data.get('__counter_entry_producers') or data.get('__intrinsic_entry_counter')
                or data.get('__entry_counter_event')):
            counts.setdefault('+1/+1', 0)
        data['entry_counts'] = list(counts.items())
    projected = copy(card)
    projected.controller = controller
    # Only the recipient is projected. Incoming global abilities do not become
    # battlefield sources before entry; the actual source remains off the board.
    previous = state.cards.get(card.id)
    state.cards[card.id] = projected
    try:
        while data['entry_index'] < len(data['entry_counts']):
            kind, amount = data['entry_counts'][data['entry_index']]
            event = {**data, 'target_card_id': card.id, 'counter': kind,
                     'amount': data.get('amount', amount), '__counter_is_effect': True}
            if kind == '+1/+1' and data.get('__counter_entry_producers'):
                event['__counter_entry_modifiers'] = data['__counter_entry_producers']
            life_symbols = int(entry.get('__phyrexian_life_symbols', 0)) if data.get('entry_item') else 0
            if (kind == 'loyalty' and life_symbols > 0
                    and re.search(r'^compleated\s*$', without_reminder_text(card.oracle_text), re.I | re.M)):
                event['__counter_entry_modifiers'] = [{
                    'source_id': f'{card.id}:entry:compleated', 'source_card_id': card.id,
                    'name': card.name, 'operation': 'subtract', 'operand': 2*life_symbols,
                    'clause': 'Compleated entry loyalty reduction',
                }]
            result = counter_effect_amount(state, controller, resume_effect, event)
            if result is None:
                return False
            data['entry_prepared'][kind] = result
            data['entry_index'] += 1
            for key in ('amount', '__counter_used', '__counter_choice', '__counter_entry_modifiers'):
                data.pop(key, None)
    finally:
        if previous is None:
            state.cards.pop(card.id, None)
        else:
            state.cards[card.id] = previous
    entry['__entry_counters_ready'] = data['entry_prepared']
    if 'consume_entry_counter' in data or data.get('__next_entry_counter', {}).get('kind') == 'native_spell_bound':
        if 'consume_entry_counter' in data:
            entry['__consume_entry_counter'] = data['consume_entry_counter']
        entry['__consume_entry_counter_receipt'] = deepcopy(data['__next_entry_counter'])
        if (data['__next_entry_counter'].get('kind') == 'native_spell_bound'
                or data['__next_entry_counter']['record'].get('counter', '+1/+1') == '+1/+1'):
            event = data['__entry_counter_event']
            entry['__entry_counter_completion'] = {
                'entry_item': deepcopy(data['entry_item']), 'entry_payload': deepcopy(entry),
                'target_card_id': card.id, 'counter': '+1/+1', 'amount': event['amount'],
                **({'consume_entry_counter': data['consume_entry_counter']} if 'consume_entry_counter' in data else {}),
                '__counter_used': list(event['applied_ids']),
                **{key: deepcopy(data[key]) for key in (
                    '__counter_entry_context', '__counter_entry_producers', '__next_entry_counter',
                    '__intrinsic_entry_counter', '__entry_counter_event') if key in data},
            }
    return True
