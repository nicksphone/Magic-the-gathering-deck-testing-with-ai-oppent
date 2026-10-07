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


def entry_counter_context_matches(state, payload):
    """Validate retained objects before a pending entry is allowed to resume."""
    from game_state.state import object_incarnation
    from rules_engine.continuous import printed_abilities_suppressed
    context = payload.get('__counter_entry_context')
    if context is None:
        return not payload.get('__counter_entry_producers')
    if not isinstance(context, dict):
        return False
    receipts = context.get('source_references')
    producers = payload.get('__counter_entry_producers')
    controller = context.get('recipient_controller')
    if (not isinstance(receipts, list) or not receipts
            or not all(isinstance(receipt, dict) for receipt in receipts)
            or not isinstance(producers, list) or not producers
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
                    '__counter_entry_context', '__counter_entry_producers'):
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
    if '__counter_entry_context' not in data:
        from game_state.state import object_incarnation
        from rules_engine.counter_replacements import counter_options
        excluded = {target.get('card_id', target.get('candidate', {}).get('id'))
                    for target in data.get('entry_targets', [])}
        producers = [option for option in resident_entry_counter_options(state, card, controller)
                     if option['source_card_id'] not in excluded]
        if producers:
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
        if 'enters with x +1/+1 counters' in card.oracle_text.lower():
            counts['+1/+1'] = max(0, int(entry.get('x_value', 0)))
        if 'Creature' in effective_types(state, card):
            if entry.get('__escaped'):
                match = re.search(r'escapes with (a|one|\d+) \+1/\+1 counters?', card.oracle_text, re.I)
                if match:
                    counts['+1/+1'] = counts.get('+1/+1', 0) + (1 if match[1].lower() in {'a', 'one'} else int(match[1]))
            for index, pending in enumerate(state.pending_entry_counters if data.get('entry_item') else []):
                if pending.get('controller') == controller and pending.get('expires_turn', state.turn) == state.turn:
                    kind = pending.get('counter', '+1/+1')
                    counts[kind] = counts.get(kind, 0) + int(pending.get('amount', 1))
                    data['consume_entry_counter'] = index
                    break
        for kind, amount in (entry.get('counters') or {}).items():
            counts[kind] = counts.get(kind, 0) + max(0, int(amount))
        if data.get('__counter_entry_producers'):
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
    if 'consume_entry_counter' in data:
        entry['__consume_entry_counter'] = data['consume_entry_counter']
    return True
