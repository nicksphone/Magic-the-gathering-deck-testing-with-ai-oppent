"""Separate printed creature-token colors, card types and subtypes."""
import re

DESCRIPTOR = re.compile(
    r'\bcreate\s+(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|x|\d+)\s+'
    r'(?:tapped(?: and attacking)?\s+)?\d+/\d+\s+([a-z -]+?)\s+creature\s+tokens?\b',
    re.IGNORECASE,
)
COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}


def complete_quoted_creature_token_body(text):
    """One complete token creation with its inherent, quoted artifact-count text."""
    match = re.fullmatch(
        r'Create (a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+) '
        r'(\d+)/(\d+) [a-z -]+? creature tokens? with ([\"\u201c\'])(.+)([\"\u201d\'])\.?',
        text.strip(), re.I | re.S)
    if match is None or {'"': '"', '\u201c': '\u201d', "'": "'"}[match[4]] != match[6]:
        return None
    body = match[5]
    if not re.fullmatch(r'This (?:token|creature|permanent) gets [+-]\d+/[+-]\d+ '
                        r'for each artifact you control\.', body, re.I):
        return None
    descriptor = creature_token_descriptor(text)
    if descriptor is None:
        return None
    from rules_engine.oracle_effects import _parse_count_token
    return {**descriptor, 'power': int(match[2]), 'toughness': int(match[3]),
            'amount': _parse_count_token(match[1]), 'oracle_text': body, 'keywords': []}


def complete_x_creature_token_body(text):
    """Receipt for one complete announced-X token body, not a prefix match."""
    from rules_engine.oracle_effects import _extract_keywords_from_text
    from rules_engine.casting_resources import KEYWORDS
    lines = [line.strip() for line in (text or '').strip().splitlines()]
    while lines and lines[0].split(' (', 1)[0].lower() in KEYWORDS:
        header = lines.pop(0)
        if '(' in header or ')' in header:
            # This is the complete printed resource-reminder contract, not
            # permission to erase arbitrary parentheses.
            if header.casefold() != ('Convoke (Your creatures can help cast this spell. Each creature you tap '
                          "while casting this spell pays for {1} or one mana of that creature's color.)").casefold():
                return None
    body = '\n'.join(lines)
    match = DESCRIPTOR.match(body)
    if match is None or not re.match(r'create x\b', body, re.I):
        return None
    tail = body[match.end():]
    keywords = []
    if tail != '.':
        if not tail.startswith(' with ') or not tail.endswith('.'):
            return None
        keywords = re.split(r',? and |, ', tail[6:-1].lower())
        if not keywords or any(_extract_keywords_from_text(word) != [word] for word in keywords):
            return None
    return {'descriptor': creature_token_descriptor(body), 'keywords': keywords, 'residual': ''}


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
