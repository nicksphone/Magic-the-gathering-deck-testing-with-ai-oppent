"""Shared supported static predicates: parse immutable text, evaluate live state."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.card_types import CREATURE_SUBTYPES

NUMBERS = {word: value for value, word in enumerate(
    ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
TYPES = {'artifact', 'enchantment', 'creature', 'land', 'planeswalker', 'battle'}


def number(token):
    return int(token) if token.isdigit() else NUMBERS.get(token)


@lru_cache(maxsize=4096)
def parse_static_condition(text):
    characteristic = re.fullmatch(r"(?:it's|it is|(?:equipped|enchanted|fortified) (?:creature|permanent|land) is) (an? )?([a-z]+)", text)
    if characteristic:
        article, kind = characteristic.groups()
        if kind in COLORS or kind in TYPES or article and kind in CREATURE_SUBTYPES:
            return ('characteristic', kind)
    permanent = re.fullmatch(r'(you|an opponent|your opponents) controls? an? (.+?) permanent', text)
    if permanent:
        scope, colors = permanent.groups()
        mode = ' and ' if ' and ' in colors else ' or '
        colors = tuple(colors.split(mode))
        if all(color in COLORS for color in colors):
            return ('color_permanent', scope, mode, colors)
    for kind, pattern in (
        ('graveyard', r'there are (\w+) or more cards in your graveyard'),
        ('source_counters', r'this (?:equipment|aura|permanent) has (\w+) or more counters on it'),
        ('lands', r'you control (\w+) or more lands'),
    ):
        match = re.fullmatch(pattern, text)
        if match and number(match[1]) is not None:
            return (kind, number(match[1]))
    defender = re.fullmatch(r'defending player controls an? (island|forest|swamp|mountain|plains)', text)
    if defender:
        return ('defender_land', defender[1])
    global_land = re.fullmatch(r'there are (\w+) or more (islands|forests|swamps|mountains|plains) on the battlefield', text)
    if global_land and number(global_land[1]) is not None:
        subtype = global_land[2] if global_land[2] == 'plains' else global_land[2].removesuffix('s')
        return ('global_land', number(global_land[1]), subtype)
    counters = re.fullmatch(r'(?:it|this creature) has (\w+) or more ([+\-]\d+/[+\-]\d+) counters on it', text)
    if counters and number(counters[1]) is not None:
        return ('recipient_counters', number(counters[1]), counters[2])
    return None


def _land_count(state, player_ids, subtype=None):
    return sum(card.zone == Zone.BATTLEFIELD and 'Land' in card.types
               and (subtype is None or subtype in re.split(r'\s+', (card.type_line or '').lower().split('—')[-1]))
               for pid in player_ids for cid in state.players[pid].battlefield
               for card in [state.cards[cid]])


def evaluate_static_condition(state, source, target, text):
    spec = parse_static_condition(text)
    if spec is None:
        return None
    kind, *args = spec
    if kind == 'characteristic':
        from rules_engine.colors import card_color_symbols
        from rules_engine.continuous import _has_subtype
        characteristic = args[0]
        if characteristic in COLORS:
            return COLORS[characteristic] in card_color_symbols(target)
        if characteristic in TYPES:
            return characteristic.title() in target.types
        return _has_subtype(target, characteristic)
    if kind == 'color_permanent':
        from rules_engine.colors import card_color_symbols
        scope, mode, colors = args
        needed = {COLORS[color] for color in colors}
        players = [source.controller] if scope == 'you' else [pid for pid in state.players if pid != source.controller]
        return any((needed <= card_color_symbols(state.cards[cid]) if mode == ' and '
                    else bool(needed & card_color_symbols(state.cards[cid])))
                   for pid in players for cid in state.players[pid].battlefield)
    if kind == 'graveyard':
        return len(state.players[source.controller].graveyard) >= args[0]
    if kind == 'source_counters':
        return sum(max(0, amount) for name, amount in source.counters.items() if not name.startswith('__')) >= args[0]
    if kind == 'lands':
        return _land_count(state, [source.controller]) >= args[0]
    if kind == 'defender_land':
        return _land_count(state, [3-target.controller], args[0]) > 0
    if kind == 'global_land':
        return _land_count(state, list(state.players), args[1]) >= args[0]
    if kind == 'recipient_counters':
        return target.counters.get(args[1], 0) >= args[0]
    raise AssertionError(f'Unhandled static condition: {kind}')
