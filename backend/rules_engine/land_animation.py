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


def compile_self_creature_change(state, source, instruction):
    """Admit a complete self subtype/base-P/T instruction before clause splitting."""
    from rules_engine.card_types import CREATURE_SUBTYPES
    body = re.sub(r'\s+', ' ', instruction.strip()).lower()
    if not (re.match(r'this creature becomes\b', body)
            or re.match(r'if\b.*\b(?:this creature|it) becomes\b', body)):
        return None
    unsupported = ('noop', {'__unsupported_instruction': instruction})
    subtype = '(?:' + '|'.join(re.escape(word) for word in
                              sorted(CREATURE_SUBTYPES, key=lambda word: (-len(word), word))) + ')'
    match = re.fullmatch(
        rf'(?:if this creature is (?:a|an) (?P<required>{subtype}), it becomes|this creature becomes) '
        rf'(?:a|an) (?P<subtypes>{subtype}(?: {subtype})*) '
        r'with base power and toughness (?P<power>\d+)/(?P<toughness>\d+)'
        r'(?:, (?P<keywords>.+))?\.', body)
    if match is None:
        return unsupported
    keywords = re.split(r',? and |, ', match['keywords']) if match['keywords'] else []
    if any(word not in {'flying', 'vigilance', 'haste', 'trample', 'reach',
                        'lifelink', 'deathtouch', 'menace', 'first strike',
                        'double strike', 'indestructible', 'hexproof'} for word in keywords):
        return unsupported
    card = state.cards.get(source.id)
    if card is None or card.zone != Zone.BATTLEFIELD:
        return unsupported
    try:
        power, toughness = int(match['power']), int(match['toughness'])
    except ValueError:
        return unsupported
    return 'change_self_creature_characteristics', {
        'target_card_id': card.id,
        'source_incarnation': object_incarnation(card),
        'source_zone_change_sequence': card.zone_change_sequence,
        'base_power': power, 'base_toughness': toughness,
        'creature_subtypes': re.findall(subtype, match['subtypes']),
        'keywords': keywords, 'required_subtype': match['required'],
    }


def resolve_self_creature_change(state, controller, payload):
    from effects.handlers import set_base_stats
    from rules_engine.action_validation import ActionRejected
    from rules_engine.keyword_effects import add_keyword_effect
    from rules_engine.library_permissions import creature_types
    from rules_engine.type_effects import add_type_effect
    fields = ('base_power', 'base_toughness', 'creature_subtypes', 'keywords', 'required_subtype')
    reference = payload.get('__activation_source_reference')
    if (type(payload.get('target_card_id')) is not str
            or payload['target_card_id'] != payload.get('__source_card_id')
            or type(reference) is not dict or set(reference) != {'incarnation', 'zone_change_sequence'}
            or any(type(reference[key]) is not int or reference[key] < 0 for key in reference)
            or any(type(payload.get(key)) is not int or payload[key] < 0
                   for key in ('source_incarnation', 'source_zone_change_sequence', 'base_power', 'base_toughness'))
            or payload['source_incarnation'] != reference['incarnation']
            or payload['source_zone_change_sequence'] != reference['zone_change_sequence']
            or any(type(payload.get(key)) is not list or any(type(word) is not str for word in payload[key])
                   for key in ('creature_subtypes', 'keywords'))
            or 'required_subtype' not in payload
            or payload['required_subtype'] is not None and type(payload['required_subtype']) is not str
            or type(payload.get('__ability_raw_effect_text')) is not str):
        raise ActionRejected('Malformed self-creature change binding')
    card = state.cards.get(payload['target_card_id'])
    if (card is None or card.zone != Zone.BATTLEFIELD
            or object_incarnation(card) != payload['source_incarnation']
            or card.zone_change_sequence != payload['source_zone_change_sequence']):
        return
    admitted = compile_self_creature_change(state, card, payload['__ability_raw_effect_text'])
    if (admitted is None or admitted[0] != 'change_self_creature_characteristics'
            or any(payload[key] != admitted[1][key] for key in fields)):
        raise ActionRejected('Self-creature change lost its complete instruction')
    if payload['required_subtype'] is not None and payload['required_subtype'] not in creature_types(card, state):
        return
    stamp = allocate_effect_timestamp(state)
    # Creature subtypes never add the Creature card type to this object.
    add_type_effect(state, card.id, [], creature_subtypes=payload['creature_subtypes'],
                    timestamp=stamp, source_card_id=card.id, until_end_of_turn=False)
    set_base_stats(state, controller, {**payload, 'effect_timestamp': object_incarnation(card),
                                     'resolution_timestamp': stamp, 'until_end_of_turn': False})
    add_keyword_effect(state, card.id, payload['keywords'], timestamp=stamp,
                       source_card_id=card.id, until_end_of_turn=False)
