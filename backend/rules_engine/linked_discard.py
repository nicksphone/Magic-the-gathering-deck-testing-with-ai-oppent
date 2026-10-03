"""Recognize complete self-discard/follow-up instructions, not card names."""
import re


def linked_discard_gaps(text):
    if 'discard' not in text.lower():
        return []
    pattern = r'\bdiscard (?:any number of cards|up to \w+ cards?)\b|\bdiscard (?:all the cards in your hand|your hand), then\b'
    for line in text.splitlines():
        surface = re.sub(r'^\s*(?:\u2022\s*|[+\-\u2212]\d+:\s*)', '', line).strip()
        if re.search(pattern, surface, re.I) and linked_discard_effect(surface) is None:
            return ['linked discard sequence fidelity']
    return []


def linked_discard_effect(text):
    text = text.strip().lower()
    if not text.startswith('discard '):
        return None
    match = re.fullmatch(r'discard up to (one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?, then draw that many cards\.?', text)
    if match:
        from rules_engine.oracle_effects import _parse_count_token
        return {'up_to': True, 'amount': _parse_count_token(match[1]),
                'followup_effect': {'effect_key': 'draw_cards', 'payload': {}, 'count_field': 'amount'}}
    if re.fullmatch(r"discard (?:all the cards in your hand|your hand), then draw a card for each card you've discarded this turn\.?", text):
        return {'all_hand': True, 'followup_effect': {'effect_key': 'draw_cards', 'payload': {},
                'count_history': 'discards_this_turn'}}
    if re.fullmatch(r'discard any number of cards\.\s*search your library for up to that many basic land cards, reveal them, put them into your hand, then shuffle\.?', text):
        return {'up_to': True, 'followup_effect': {'effect_key': 'search_library',
                'payload': {'contains': 'basic_land', 'destination': 'hand', 'shuffle': True, 'up_to': True, 'reveal': True},
                'count_field': 'count'}}
    match = re.fullmatch(r'discard (?:all the cards in your hand|your hand), then draw (that many|one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?\.?', text)
    if match:
        from rules_engine.oracle_effects import _parse_count_token
        followup = {'effect_key': 'draw_cards', 'payload': {}}
        if match[1] == 'that many':
            followup['count_field'] = 'amount'
        else:
            followup['payload']['amount'] = _parse_count_token(match[1])
        return {'all_hand': True, 'followup_effect': followup}
    return None
