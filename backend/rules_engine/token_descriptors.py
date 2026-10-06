"""Separate printed creature-token colors, card types and subtypes."""
import re

DESCRIPTOR = re.compile(
    r'\bcreate\s+(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|x|\d+)\s+'
    r'(?:tapped(?: and attacking)?\s+)?\d+/\d+\s+([a-z -]+?)\s+creature\s+tokens?\b',
    re.IGNORECASE,
)
COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}


def creature_token_descriptor(text: str) -> dict | None:
    match = DESCRIPTOR.search(text)
    if match is None:
        return None
    words = match[1].lower().split()
    colors = []
    while words and words[0] in {*COLORS, 'colorless', 'and'}:
        word = words.pop(0)
        if word in COLORS and COLORS[word] not in colors:
            colors.append(COLORS[word])
    card_types = []
    while words and words[-1] in {'artifact', 'enchantment'}:
        card_types.insert(0, words.pop().title())
    subtypes = ' '.join(words).title()
    types = [*card_types, 'Creature', 'Token']
    type_line = 'Token ' + ' '.join([*card_types, 'Creature'])
    if subtypes:
        type_line += ' \u2014 ' + subtypes
    return {'name': subtypes or 'Token', 'types': types, 'type_line': type_line,
            'colors': colors}
