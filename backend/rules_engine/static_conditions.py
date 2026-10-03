"""Shared supported static predicates: parse immutable text, evaluate live state."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.card_types import CREATURE_SUBTYPES, graveyard_card_types, is_token_card

NUMBERS = {word: value for value, word in enumerate(
    ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
COLORS = {'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G'}
TYPES = {'artifact', 'enchantment', 'creature', 'land', 'planeswalker', 'battle'}


def static_clause_components(text):
    """Preserve one predicate while separating complete coordinated actions."""
    text = re.sub(r'^[a-z][a-z ]*\s+[—–-]\s+', '', text.strip().rstrip('.'))
    prefix = re.fullmatch(r'as long as (.+?), (.+)', text)
    suffix = re.fullmatch(r'(.+?) as long as (.+)', text)
    if not prefix and not suffix:
        return (text,)
    body, condition = (prefix[2], prefix[1]) if prefix else suffix.groups()
    receiver = re.match(r'(.+?) (?:gets?|has|have)\b', body)
    if receiver is None:
        return (text,)
    actions = re.split(r"(?:,\s*(?:and\s+)?| and )(?=gets?\b|has\b|have\b|attacks?\b|blocks?\b|must\b|can't\b|cannot\b)", body)
    return tuple((action if index == 0 else receiver[1] + ' ' + action)
                 + ' as long as ' + condition for index, action in enumerate(actions))


def number(token):
    return int(token) if token.isdigit() else NUMBERS.get(token)


@lru_cache(maxsize=4096)
def parse_static_condition(text, card_name=''):
    if card_name:
        aliases = {card_name.lower(), card_name.lower().split(',', 1)[0]}
        for alias in sorted(aliases, key=len, reverse=True):
            text = re.sub(r'^' + re.escape(alias) + r'(?= is\b)', 'this permanent', text)
    status = re.fullmatch(r'this (?:creature|permanent|equipment|aura|land) is (tapped|untapped|attacking|blocking)', text)
    if status:
        return ('source_status', status[1])
    recipient_status = re.fullmatch(r"(?:it's|it is) (tapped|untapped|attacking|blocking)", text)
    if recipient_status:
        return ('recipient_status', recipient_status[1])
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
        ('graveyard', r'(\w+) or more cards are in your graveyard'),
        ('graveyard_types', r'there are (\w+) or more card types among cards in your graveyard'),
        ('life', r'you have (\w+) or more life'),
        ('source_counters', r'this (?:equipment|aura|permanent) has (\w+) or more counters on it'),
        ('lands', r'you control (\w+) or more lands'),
    ):
        match = re.fullmatch(pattern, text)
        if match and number(match[1]) is not None:
            return (kind, number(match[1]))
    permanent_count = re.fullmatch(r'you control (\w+) or more (artifacts|enchantments|creatures|planeswalkers|battles)', text)
    if permanent_count and number(permanent_count[1]) is not None:
        return ('permanents', number(permanent_count[1]), permanent_count[2][:-1].title())
    opponent_resource = re.fullmatch(
        r'an opponent has (\w+) or (more cards in their graveyard|less life|fewer life)', text)
    if opponent_resource and number(opponent_resource[1]) is not None:
        return ('opponent_graveyard' if opponent_resource[2].startswith('more') else 'opponent_life',
                number(opponent_resource[1]))
    if text == 'you have no cards in hand':
        return ('empty_hand',)
    own_land = re.fullmatch(r'you control an? (island|forest|swamp|mountain|plains)', text)
    if own_land:
        return ('own_land', own_land[1])
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
               and (subtype is None or subtype in re.split(r'\s+', re.split(r'\s+[—–-]\s+', (card.type_line or '').lower())[-1]))
               for pid in player_ids for cid in state.players[pid].battlefield
               for card in [state.cards[cid]])


def evaluate_static_condition(state, source, target, text):
    spec = parse_static_condition(text, source.name)
    if spec is None:
        return None
    kind, *args = spec
    if kind in {'source_status', 'recipient_status'}:
        subject = source if kind == 'source_status' else target
        if subject.zone != Zone.BATTLEFIELD:
            return False
        return {'tapped': subject.tapped, 'untapped': not subject.tapped,
                'attacking': subject.id in state.attackers,
                'blocking': any(subject.id in ids for ids in state.blocks.values())}[args[0]]
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
        return sum(not is_token_card(state.cards[cid]) for cid in state.players[source.controller].graveyard) >= args[0]
    if kind == 'graveyard_types':
        return len(graveyard_card_types(state, [source.controller])) >= args[0]
    if kind == 'opponent_graveyard':
        return any(sum(not is_token_card(state.cards[cid]) for cid in player.graveyard) >= args[0]
                   for pid, player in state.players.items() if pid != source.controller)
    if kind == 'opponent_life':
        return any(player.life <= args[0] for pid, player in state.players.items() if pid != source.controller)
    if kind == 'life':
        return state.players[source.controller].life >= args[0]
    if kind == 'permanents':
        return sum(state.cards[cid].zone == Zone.BATTLEFIELD and args[1] in state.cards[cid].types
                   for cid in state.players[source.controller].battlefield) >= args[0]
    if kind == 'empty_hand':
        return not state.players[source.controller].hand
    if kind == 'own_land':
        return _land_count(state, [source.controller], args[0]) > 0
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
