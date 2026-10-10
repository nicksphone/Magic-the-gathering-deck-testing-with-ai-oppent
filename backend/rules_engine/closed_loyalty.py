"""Closed raw loyalty surfaces, before any per-ability Oracle projection.

This is a bounded compiler for existing effects, not all planeswalker rules.
Unknown lines and all unaccounted parentheses reject the entire surface.
"""
import re


ABILITY = re.compile(r'(?P<cost>[+-]?(?:\d+|X)):\s*(?P<body>.+)', re.I)
COUNT = r'(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)'


def compile_instruction(text, name=''):
    """Account for every sentence and its single shared target, without erasure."""
    from rules_engine.oracle_effects import (
        COUNTER_RE, DRAW_RE, EACH_PLAYER_DRAW_RE, TARGETED_DRAW_RE,
        RECIPIENT_MILL_RE, _extract_keywords_from_text,
    )
    from rules_engine.continuous import _attached_keywords
    from rules_engine.loyalty_instructions import compile_extended

    extended = compile_extended(text, name)
    if extended is not None:
        if [step['effect_key'] for step in extended] == ['loyalty_counter', 'loyalty_animate']:
            animation = extended[1]['data']
            if (animation['power'] == animation['toughness'] == 0
                    and animation['subtype'].casefold() == 'elemental'
                    and set(animation['keywords']) <= {'vigilance', 'haste'}
                    and 'becomes a 0/0' in text.lower()
                    and COUNTER_RE.match(text.lower())):
                # The full-match grammar proves the body; reuse the native resumable handler.
                return [{'effect_key': 'add_counters', 'instruction': text[:-1]}]
        return extended

    if not text.endswith('.') or any(char in text for char in '()\n;"'):
        return None
    sentences = text[:-1].split('. ')
    if not sentences or any(not sentence for sentence in sentences):
        return None
    steps = []
    target_seen = False
    creature_target = False
    for sentence in sentences:
        clause = sentence.lower()
        if len(re.findall(r'\btarget\b', clause)) > 1:
            return None
        has_target = bool(re.search(r'\btarget\b', clause))
        if has_target and target_seen:
            return None
        if DRAW_RE.fullmatch(clause) or TARGETED_DRAW_RE.fullmatch(clause):
            key = 'draw_cards'
        elif EACH_PLAYER_DRAW_RE.fullmatch(clause):
            key = 'effect_sequence'
        elif RECIPIENT_MILL_RE.fullmatch(clause):
            key = 'mill_cards'
        elif re.fullmatch(r'you gain \d+ life', clause):
            key = 'gain_life'
        elif re.fullmatch(r'target player loses \d+ life', clause):
            key = 'lose_life'
        elif COUNTER_RE.fullmatch(clause):
            key = 'add_counters'
        elif re.fullmatch(r'deal (?:\d+|x) damage to any target', clause):
            key = 'deal_damage'
        elif (named_damage := re.fullmatch(r'(.+?) deals (\d+|x) damage to any target', clause)):
            source_names = {name.casefold(), name.split(',', 1)[0].casefold(),
                            'this planeswalker', 'this permanent'}
            if named_damage[1] not in source_names:
                return None
            key = 'deal_damage'
        elif re.fullmatch(r'destroy target (?:artifact|enchantment|artifact or enchantment)', clause):
            key = 'destroy_permanent'
        elif clause == 'destroy all creatures':
            key = 'destroy_all_creatures'
        elif re.fullmatch(r"exile each permanent with mana value x or less that(?:'s| is) one or more colors", clause):
            key = 'exile_colored_permanents_mana_value_at_most'
        elif re.fullmatch(r'exile target (?:tapped |untapped )?creature', clause):
            key = 'exile'
        else:
            grant = re.fullmatch(r'(it|target creature) gains (.+) until end of turn', clause)
            token = re.fullmatch(
                r'create ' + COUNT + r' \d+/\d+ (?:white|blue|black|red|green|colorless) '
                r'[a-z]+(?: [a-z]+)* creature tokens?(?: with (.+))?', clause)
            keywords = _attached_keywords(grant[2]) if grant else None
            token_keywords = _attached_keywords(token[1]) if token and token[1] else []
            if (grant and (grant[1] != 'it' or creature_target) and keywords
                    and not any(keyword.startswith('ward') for keyword in keywords)):
                key = 'grant_keyword'
            elif (token and token_keywords is not None
                    and set(token_keywords) == set(_extract_keywords_from_text(token[1] or ''))):
                key = 'create_token'
            else:
                return None
        steps.append({'effect_key': key, 'instruction': sentence})
        target_seen = target_seen or has_target
        creature_target = creature_target or bool(re.search(r'\btarget (?:tapped |untapped )?creature\b', clause))
    return steps


def compile_body(text, name=''):
    """Compile all printed lines or return None; costs/order/names are not recipes."""
    from rules_engine.loyalty_timing import ENTRY_TURN_PERMISSION

    if (not isinstance(text, str) or not isinstance(name, str) or len(text) > 16384
            or re.search(r'\d{11}', text)):
        return None
    lines = [line.strip() for line in text.replace('\u2212', '-').splitlines() if line.strip()]
    abilities, companions = [], []
    for line in lines:
        from rules_engine.loyalty_instructions import companion
        permission = ENTRY_TURN_PERMISSION.fullmatch(line)
        if companion(line, name) or line.casefold() == 'flash' or (permission and permission['source'].casefold()
                in {name.casefold(), 'this planeswalker', 'this permanent'}):
            if line.casefold() in {old.casefold() for old in companions}:
                return None
            companions.append(line)
            continue
        match = ABILITY.fullmatch(line)
        if match is None:
            return None
        instructions = compile_instruction(match['body'], name)
        if instructions is None:
            return None
        raw = match['cost'].upper()
        source_x = all(step['effect_key'] == 'loyalty_source_token' for step in instructions)
        if len(raw) > 10 or (re.search(r'\bx\b', match['body'], re.I) and not source_x and not raw.endswith('X')):
            return None
        x_cost = raw.endswith('X')
        delta = 0 if x_cost else int(raw)
        abilities.append({'delta': delta, 'x_cost': x_cost,
            'x_sign': (-1 if raw.startswith('-') else 1) if x_cost else 0,
            'text': match['body'],
            'label': f"{raw if x_cost else format(delta, '+d')}: {match['body']}",
            'instructions': instructions})
    return {'abilities': abilities, 'companions': companions} if abilities else None
