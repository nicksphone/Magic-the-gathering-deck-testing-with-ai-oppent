"""Prepare supported entry counters before battlefield mutation or token creation."""
from copy import copy, deepcopy
from dataclasses import asdict
import re

from game_state.state import CardInstance, StackItem, Zone
from rules_engine.counter_replacements import counter_effect_amount
from rules_engine.oracle_effects import extract_saga_chapters
from rules_engine.oracle_text import without_reminder_text


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


def prepare_counter_entries(state, controller, cards, effect_key, payload, *, entry_payload=None, controllers=None):
    """Reenter the route with a ready packet; True means caller must stop here."""
    if '__entry_counters_by_id' in payload:
        return False
    options = deepcopy(entry_payload if entry_payload is not None else payload)
    if entry_payload is None:
        for key in ('x_value', '__escaped', '__phyrexian_life_symbols'):
            options.pop(key, None)
    resume_entry_batch(state, controller, {
        'entry_targets': [({**({'card_id': card.id} if card.id in state.cards else {'candidate': asdict(card)}),
                           'controller': (controllers or {}).get(card.id, controller)})
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
        data.setdefault('entry_payload', deepcopy(data['entry_options']))
        data.setdefault('entry_prepared', {})
        data.setdefault('entry_index', 0)
        if not prepare_entry_counters(state, target.get('controller', controller), data, card, 'permanent_entry_counters'):
            return
        data['entry_results'][card.id] = data['entry_payload']['__entry_counters_ready']
        data['entry_target_index'] += 1
        for key in ('entry_payload', 'entry_prepared', 'entry_index', 'entry_counts', 'consume_entry_counter'):
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
    if 'Planeswalker' in card.types and card.loyalty is not None:
        card.printed_characteristics.setdefault('loyalty', card.loyalty)
        card.loyalty = 0
    for kind, amount in payload['__entry_counters_by_id'].get(card.id, {}).items():
        put_counters(state, kind, amount, target_card_id=card.id, placement_checked=True)


def prepare_entry_counters(state, controller, data, card, resume_effect):
    entry = data['entry_payload']
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
        if 'Planeswalker' in card.types and card.loyalty is not None:
            loyalty = int(card.loyalty)
            counts['loyalty'] = loyalty
        if chapters:
            counts['lore'] = int(entry.get('__read_ahead_chapter', 1))
        if 'enters with x +1/+1 counters' in card.oracle_text.lower():
            counts['+1/+1'] = max(0, int(entry.get('x_value', 0)))
        if 'Creature' in card.types:
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
