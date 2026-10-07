"""Complete temporary creature instructions using native object-bound layers."""
import re

from game_state.state import Zone, allocate_effect_timestamp, object_incarnation


def temporary_characteristics_candidate(instruction):
    return bool(re.match(
        r'\s*until end of turn, target creature loses all abilities and becomes\b',
        instruction, re.IGNORECASE))


def compile_temporary_characteristics(instruction, action_targets):
    """Recognize the whole body, including the only supported following reward."""
    from rules_engine.card_types import CREATURE_SUBTYPES
    body = re.sub(r'\s+', ' ', instruction.strip()).lower()
    match = re.fullmatch(
        r'until end of turn, target creature loses all abilities and becomes '
        r'(?:a|an) (white|blue|black|red|green) ([a-z]+) '
        r'with base power and toughness (\d+)/(\d+)\.( draw a card\.)?', body)
    if match is None or match[2] not in CREATURE_SUBTYPES:
        return None
    return 'temporary_creature_characteristics', {
        'target_card_id': action_targets.get('target_card_id'),
        'colors': [{'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}[match[1]]],
        'creature_subtypes': [match[2]],
        'base_power': int(match[3]), 'base_toughness': int(match[4]),
        'draw_after_change': bool(match[5]),
    }


def resolve_temporary_characteristics(state, controller, payload):
    from effects.handlers import set_base_stats
    from effects.registry import resolve_effect
    from rules_engine.keyword_effects import add_keyword_effect
    from rules_engine.type_effects import add_type_effect, effective_types
    card = state.cards.get(payload.get('target_card_id'))
    if card is None or card.zone != Zone.BATTLEFIELD or 'Creature' not in effective_types(state, card):
        return
    # Whole-spell targeting is checked by the stack before this single handler.
    stamp = allocate_effect_timestamp(state)
    source_id = payload.get('__source_card_id')
    add_type_effect(state, card.id, ['Creature'], until_end_of_turn=True,
                    timestamp=stamp, source_card_id=source_id,
                    creature_subtypes=payload['creature_subtypes'], colors=payload['colors'])
    set_base_stats(state, controller, {**payload, 'effect_timestamp': object_incarnation(card),
                                     'resolution_timestamp': stamp, 'until_end_of_turn': True})
    add_keyword_effect(state, card.id, ['all abilities'], operation='remove', until_end_of_turn=True,
                       timestamp=stamp, source_card_id=source_id)
    if payload['draw_after_change']:
        resolve_effect(state, controller, 'draw_cards', {
            **{key: value for key, value in payload.items() if key.startswith('__')},
            'amount': 1, 'target_player': controller,
        })
