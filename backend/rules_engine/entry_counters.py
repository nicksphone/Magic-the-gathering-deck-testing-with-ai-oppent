"""Prepare supported permanent-spell entry counters before battlefield mutation."""
from copy import copy, deepcopy
from dataclasses import asdict
import re

from game_state.state import StackItem, Zone
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
    entry = data['entry_payload']
    chapters = extract_saga_chapters(card.oracle_text) if 'Saga' in card.type_line else []
    if (chapters and re.search(r'^read ahead\s*$', without_reminder_text(card.oracle_text), re.I | re.M)
            and '__read_ahead_chapter' not in entry):
        options = [str(number) for number in range(1, max(ch['number'] for ch in chapters)+1)]
        state.pending_mechanic_choice = {
            'kind': 'saga_entry', 'player_id': controller, 'controller': controller,
            'options': options, 'option_labels': {value: f'Start at chapter {value}' for value in options},
            'effect_key': 'permanent_spell_entry', 'effect_payload': data,
            'label': f'Choose the starting chapter for {card.name}',
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
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
            for index, pending in enumerate(state.pending_entry_counters):
                if pending.get('controller') == controller and pending.get('expires_turn', state.turn) == state.turn:
                    kind = pending.get('counter', '+1/+1')
                    counts[kind] = counts.get(kind, 0) + int(pending.get('amount', 1))
                    data['consume_entry_counter'] = index
                    break
        data['entry_counts'] = list(counts.items())
    projected = copy(card)
    projected.controller = controller
    # Only the recipient is projected. Incoming global abilities do not become
    # battlefield sources before entry; the actual source remains off the board.
    state.cards[card.id] = projected
    try:
        while data['entry_index'] < len(data['entry_counts']):
            kind, amount = data['entry_counts'][data['entry_index']]
            event = {**data, 'target_card_id': card.id, 'counter': kind,
                     'amount': data.get('amount', amount), '__counter_is_effect': True}
            life_symbols = int(entry.get('__phyrexian_life_symbols', 0))
            if (kind == 'loyalty' and life_symbols > 0
                    and re.search(r'^compleated\s*$', without_reminder_text(card.oracle_text), re.I | re.M)):
                event['__counter_entry_modifiers'] = [{
                    'source_id': f'{card.id}:entry:compleated', 'source_card_id': card.id,
                    'name': card.name, 'operation': 'subtract', 'operand': 2*life_symbols,
                    'clause': 'Compleated entry loyalty reduction',
                }]
            result = counter_effect_amount(state, controller, 'permanent_spell_entry', event)
            if result is None:
                return
            data['entry_prepared'][kind] = result
            data['entry_index'] += 1
            for key in ('amount', '__counter_used', '__counter_choice', '__counter_entry_modifiers'):
                data.pop(key, None)
    finally:
        state.cards[card.id] = card
    entry['__entry_counters_ready'] = data['entry_prepared']
    if 'consume_entry_counter' in data:
        entry['__consume_entry_counter'] = data['consume_entry_counter']
    finish_stack_resolution(state, StackItem(**data['entry_item']), entry)
