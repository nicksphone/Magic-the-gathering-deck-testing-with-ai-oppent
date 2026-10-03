"""Parse recognized printed additional costs, never a spell's later effects."""
import re

from rules_engine.oracle_text import without_reminder_text

NUMBERS = {'a': 1, 'an': 1, **dict(zip(
    ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'], range(1, 11)))}
COUNT = r'(\d+|' + '|'.join(NUMBERS) + r')'
TYPES = r'(?:artifacts?|creatures?|enchantments?|lands?|planeswalkers?|battles?|permanents?)'


def _merge(left, right):
    merged = dict(left)
    for key, value in right.items():
        if key == 'sacrifice_kind':
            if merged.get(key, value) != value:
                return None
            merged[key] = value
        elif key == 'pay_life_x':
            if merged.get(key):
                return None
            merged[key] = True
        else:
            merged[key] = merged.get(key, 0) + value
    return merged


def _component(text):
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
    return None


def spell_additional_costs(text, card_name=''):
    """Return supported cost branches, or None for any unmodeled clause."""
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
            if len(re.split(r'\s+or\s+(?=(?:pay|discard|sacrifice)\b)', body)) > 1 and parsed.get('pay_life_x'):
                return None
            choices.append(parsed)
        combined = [_merge(previous, choice) for previous in branches for choice in choices]
        if len(branches) * len(choices) > 32 or any(choice is None for choice in combined):
            return None
        branches = combined
    return branches
