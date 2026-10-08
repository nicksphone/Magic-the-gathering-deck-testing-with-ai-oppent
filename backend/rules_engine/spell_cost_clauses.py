"""Parse recognized printed additional costs, never a spell's later effects."""
import re

from rules_engine.oracle_text import without_reminder_text
from rules_engine.card_types import CREATURE_SUBTYPES, creature_subtype_candidates

NUMBERS = {'a': 1, 'an': 1, **dict(zip(
    ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'], range(1, 11)))}
COUNT = r'(\d+|' + '|'.join(NUMBERS) + r')'
TYPES = r'(?:artifacts?|creatures?|enchantments?|lands?|planeswalkers?|battles?|permanents?)'


def _merge(left, right):
    for flag, count in [('discard_all', 'discard_cards'), ('sacrifice_all', 'sacrifice_creatures')]:
        if ((left.get(flag) and (right.get(count) or right.get(flag)))
                or (right.get(flag) and left.get(count))):
            return None
    if (left.get('discard_all') and right.get('discard_x')) or (right.get('discard_all') and left.get('discard_x')):
        return None
    merged = dict(left)
    for key, value in right.items():
        if key == 'sacrifice_kind':
            if merged.get(key, value) != value:
                return None
            merged[key] = value
        elif key in {'pay_life_x', 'discard_x', 'discard_all', 'sacrifice_all'}:
            if merged.get(key):
                return None
            merged[key] = True
        else:
            merged[key] = merged.get(key, 0) + value
    return merged


def _component(text):
    if text == 'discard your hand':
        return {'discard_all': True}
    if text == 'sacrifice all permanents you control':
        return {'sacrifice_all': True, 'sacrifice_kind': 'permanent'}
    if text == 'discard x cards':
        return {'discard_x': True}
    match = re.fullmatch(r'pay ' + COUNT + r' life', text)
    if match:
        value = match[1]
        return {'pay_life': int(value) if value.isdigit() else NUMBERS[value]}
    if text == 'pay x life':
        return {'pay_life_x': True}
    match = re.fullmatch(r'discard ' + COUNT + r' cards?', text)
    if match:
        value = match[1]
        return {'discard_cards': int(value) if value.isdigit() else NUMBERS[value]}
    match = re.fullmatch(r'sacrifice ' + COUNT + r' (' + TYPES + r'(?: or ' + TYPES + r')?)', text)
    if match:
        value = match[1]
        kinds = [kind.removesuffix('s') for kind in match[2].split(' or ')]
        return {'sacrifice_creatures': int(value) if value.isdigit() else NUMBERS[value],
                'sacrifice_kind': '_or_'.join(kinds)}
    match = re.fullmatch(r'sacrifice ' + COUNT + r' (white|blue|black|red|green) (' + TYPES + r')', text)
    if match:
        value = match[1]
        return {'sacrifice_creatures': int(value) if value.isdigit() else NUMBERS[value],
                'sacrifice_kind': match[2] + '_' + match[3].removesuffix('s')}
    match = re.fullmatch(r'sacrifice ' + COUNT + r' ([a-z][a-z -]*)', text)
    if match:
        subtypes = creature_subtype_candidates(match[2]) & CREATURE_SUBTYPES
        if len(subtypes) == 1:
            value = match[1]
            return {'sacrifice_creatures': int(value) if value.isdigit() else NUMBERS[value],
                    'sacrifice_kind': 'subtype_' + next(iter(subtypes))}
    return None


def fixed_cost_component(text):
    """Shared fixed life/discard/typed-sacrifice component, not an X payment."""
    parsed = _component(text.strip().rstrip('.').lower())
    return parsed if parsed and not any(parsed.get(key) for key in
        ['pay_life_x', 'discard_x', 'discard_all', 'sacrifice_all']) else None


def resource_x_effect_gaps(text):
    """Price recognition must not enable an unmodeled X recipient/card count."""
    gaps = []
    if re.search(r'\bx targets?\b', text, re.I):
        gaps.append('resource-X target cardinality')
    if re.search(r'search your library for[^.\n]*\bx\b', text, re.I):
        gaps.append('resource-X search cardinality')
    return gaps


def compile_optional_hand_exile_discount(text, card_name=''):
    """Price only a closed complete body already covered by the target compiler."""
    if not re.search(r'\bas an additional cost to cast\b[^.]*\byou may exile\b', text or '', re.I):
        return None
    from rules_engine.oracle_effects import compile_complete_x_bounded_exile_instruction
    contract = compile_complete_x_bounded_exile_instruction(text, card_name)
    if not contract or '__unsupported_instruction' in contract:
        return {'unsupported_hand_exile': True}
    match = re.search(r'exile any number of (white|blue|black|red|green) cards from your hand\.\s*'
                      r'This spell costs \{(\d+)\} less to cast for each card exiled this way\.', text, re.I)
    if not match:
        return {'unsupported_hand_exile': True}
    return {'hand_exile_color': {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}[match[1].lower()],
            'hand_exile_generic_reduction': int(match[2])}


def spell_additional_costs(text, card_name=''):
    """Return supported cost branches, or None for any unmodeled clause."""
    hand_exile = compile_optional_hand_exile_discount(text, card_name)
    if hand_exile is not None:
        return None if hand_exile.get('unsupported_hand_exile') else [hand_exile]
    text = without_reminder_text(text or '').lower()
    sentences = re.findall(r'\bas an additional cost to cast\b[^.\n]*(?:\.|$)', text)
    if len(sentences) != len(re.findall(r'\bas an additional cost to cast\b', text)):
        return None
    if not sentences:
        return [{}]
    reference = r'(?:this spell|' + re.escape(card_name.lower()) + ')' if card_name else r'[^,\n]+'
    branches = [{}]
    for sentence in sentences:
        header = re.fullmatch(r'as an additional cost to cast ' + reference + r',\s*(.*?)\.?', sentence)
        if not header:
            return None
        body = header[1].rstrip('.').strip()
        choices = []
        for branch in re.split(r'\s+or\s+(?=(?:pay|discard|sacrifice)\b)', body):
            parsed = {}
            for component in re.split(r',?\s+and\s+|,\s*', branch):
                item = _component(component.strip())
                if item is None:
                    return None
                parsed = _merge(parsed, item)
                if parsed is None:
                    return None
            if len(re.split(r'\s+or\s+(?=(?:pay|discard|sacrifice)\b)', body)) > 1 and any(parsed.get(key) for key in ['pay_life_x','discard_x']):
                return None
            choices.append(parsed)
        combined = [_merge(previous, choice) for previous in branches for choice in choices]
        if len(branches) * len(choices) > 32 or any(choice is None for choice in combined):
            return None
        branches = combined
    return branches
