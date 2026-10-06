"""Complete self-land animation instructions; native object-bound overlays."""
import re

from game_state.state import Zone, allocate_effect_timestamp, object_incarnation


def animation_candidate(source, instruction):
    subjects = {'this land', 'this permanent', 'it', source.name.lower(),
                source.name.split(',', 1)[0].lower()} - {''}
    subject = '|'.join(re.escape(value) for value in sorted(subjects))
    return bool(re.match(rf'(?:until end of turn, )?(?:{subject}) becomes\b', instruction, re.I))


def compile_self_land_animation(state, source, instruction):
    """Pure full-body recognition, never a partially supported effect."""
    from rules_engine.card_types import CREATURE_SUBTYPES
    body = re.sub(r'\s+', ' ', instruction.strip()).lower()
    if not animation_candidate(source, body):
        return None
    subjects = {'this land', 'this permanent', 'it', source.name.lower(),
                source.name.split(',', 1)[0].lower()} - {''}
    subject = '|'.join(re.escape(value) for value in sorted(subjects))
    match = re.fullmatch(
        rf'(?P<prefix>until end of turn, )?(?:{subject}) becomes (?:a|an) '
        r'(?P<power>\d+)/(?P<toughness>\d+) (?:(?P<description>.+?) )?creature'
        r'(?: with (?P<abilities>.+?))?(?P<suffix> until end of turn)?\. '
        rf"(?:it's|it is|(?:{subject}) is) still a land\.", body)
    if match is None or bool(match['prefix']) == bool(match['suffix']):
        return None
    words = (match['description'] or '').split()
    aliases = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
    colors = []
    while words and words[0] in aliases:
        colors.append(aliases[words.pop(0)])
        if len(words) > 1 and words[0] == 'and' and words[1] in aliases:
            words.pop(0)
    if words == ['colorless']:
        colors, words = [], []
        explicit_color = True
    else:
        explicit_color = bool(colors)
    if any(word not in CREATURE_SUBTYPES for word in words):
        return None
    abilities = match['abilities'] or ''
    if abilities == 'all creature types':
        subtypes, keywords = sorted(CREATURE_SUBTYPES), []
    elif abilities:
        # Deliberately bounded to simple implemented evergreen grants.
        keywords = re.split(r',? and |, ', abilities)
        if any(word not in {'flying', 'vigilance', 'haste', 'trample', 'reach',
                            'lifelink', 'deathtouch', 'menace', 'first strike',
                            'double strike', 'indestructible', 'hexproof'} for word in keywords):
            return None
        subtypes = words
    else:
        subtypes, keywords = words, []
    card = state.cards.get(source.id)
    if card is None or card.zone != Zone.BATTLEFIELD:
        return None
    from rules_engine.type_effects import effective_types
    if 'Land' not in effective_types(state, card):
        return None
    return 'animate_self_land', {
        'target_card_id': card.id,
        'source_incarnation': object_incarnation(card),
        'source_zone_change_sequence': card.zone_change_sequence,
        'base_power': int(match['power']), 'base_toughness': int(match['toughness']),
        'creature_subtypes': subtypes, 'keywords': keywords,
        **({'colors': sorted(set(colors))} if explicit_color else {}),
    }


def resolve_self_land_animation(state, controller, payload):
    from effects.handlers import set_base_stats
    from rules_engine.keyword_effects import add_keyword_effect
    from rules_engine.type_effects import add_type_effect
    card = state.cards.get(payload['target_card_id'])
    if (card is None or card.zone != Zone.BATTLEFIELD
            or object_incarnation(card) != payload['source_incarnation']
            or card.zone_change_sequence != payload['source_zone_change_sequence']):
        return
    stamp = allocate_effect_timestamp(state)
    add_type_effect(state, card.id, ['Creature'], until_end_of_turn=True,
                    timestamp=stamp, source_card_id=card.id,
                    creature_subtypes=payload['creature_subtypes'], colors=payload.get('colors'))
    set_base_stats(state, controller, {**payload, 'effect_timestamp': object_incarnation(card),
                                     'resolution_timestamp': stamp, 'until_end_of_turn': True})
    add_keyword_effect(state, card.id, payload['keywords'], until_end_of_turn=True,
                       timestamp=stamp, source_card_id=card.id)
