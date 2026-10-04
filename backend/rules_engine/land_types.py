"""Pure layer-four basic-land type additions, replacements and source dependencies."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text

BASIC_TYPES = ('Plains', 'Island', 'Swamp', 'Mountain', 'Forest')
# Comprehensive Rules 205.3i, 2026-09-25; other card types' subtypes survive 305.7.
LAND_TYPES = frozenset('Cave Desert Forest Gate Island Lair Locus Mine Mountain Plains Planet Power-Plant Sphere Swamp Tower Town'.split()) | {'Urza\u2019s', "Urza's"}


@lru_cache(maxsize=4096)
def land_type_instructions(oracle_text):
    result = []
    for line in without_reminder_text(oracle_text or '').splitlines():
        match = re.fullmatch(
            r'(each land|all lands|lands|nonbasic lands|lands you control|enchanted land) '
            r'(?:is|are) (.+?)( in addition to (?:its|their) other (?:land )?types)?\.',
            line.strip().lower())
        if not match:
            continue
        scope, types, addition = match.groups()
        if types == 'every basic land type':
            selected = BASIC_TYPES
        else:
            words = [word.removeprefix('a ').removeprefix('an ')
                     for word in re.split(r',? and |, ', types)]
            aliases = {word.lower(): word for word in BASIC_TYPES}
            aliases.update({word.lower() + 's': word for word in BASIC_TYPES if word != 'Plains'})
            if any(word not in aliases for word in words):
                continue
            selected = tuple(aliases[word] for word in words)
        result.append((scope, selected, bool(addition)))
    return tuple(result)


def _split_line(line):
    parts = re.split(r'\s+[\u2014\u2013-]\s+', line or '', maxsplit=1)
    return parts[0], parts[1].split() if len(parts) == 2 else []


def _rows(state, entering=None, controller=None):
    from rules_engine.type_effects import effective_types
    rows = tuple((cid, getattr(card, 'type_line', '') or '', getattr(card, 'oracle_text', '') or '',
                  getattr(card, 'controller', pid), 'Land' in effective_types(state, card),
                  int(getattr(card, 'effect_timestamp', 0) or getattr(card, 'static_order', 0) or 0),
                  getattr(card, 'attached_to', None), getattr(card, 'name', ''))
                 for pid, player in state.players.items() for cid in player.battlefield
                 for card in [state.cards[cid]] if getattr(card, 'zone', Zone.BATTLEFIELD) == Zone.BATTLEFIELD)
    if entering is not None:
        cid = getattr(entering, 'id', '__entering_land')
        rows = tuple(row for row in rows if row[0] != cid)
        rows += ((cid, entering.type_line or '', entering.oracle_text or '',
                  entering.controller if controller is None else controller,
                  'Land' in effective_types(state, entering),
                  max(state.next_effect_timestamp, state.next_static_order),
                  getattr(entering, 'attached_to', None), entering.name),)
    return rows


def _legacy_basic(row):
    return not row[1] and row[7].removeprefix('Snow-Covered ') in (*BASIC_TYPES, 'Wastes')


def _view(state, entering=None, controller=None):
    candidates = (state.cards[cid] for player in state.players.values() for cid in player.battlefield)
    if not any(land_type_instructions(getattr(card, 'oracle_text', '') or '') for card in candidates) and not (
            entering is not None and land_type_instructions(entering.oracle_text)):
        return {}, frozenset()
    return _resolve(_rows(state, entering, controller))


@lru_cache(maxsize=512)
def _resolve(rows):
    effects = [(row, instruction, index) for row in rows
               for index, instruction in enumerate(land_type_instructions(row[2]))]
    if not effects:
        return {}, frozenset()
    lands = {row[0]: row for row in rows if row[4]}
    subtypes = {cid: (_split_line(row[1])[1] or
                     ([row[7].removeprefix('Snow-Covered ')] if _legacy_basic(row) and row[7] != 'Wastes' else []))
                for cid, row in lands.items()}
    lost = set()

    def targets(effect):
        source, (scope, _, _), _ = effect
        return {cid for cid, row in lands.items()
                if (scope != 'nonbasic lands' or not ('Basic' in _split_line(row[1])[0].split() or _legacy_basic(row)))
                and (scope != 'lands you control' or row[3] == source[3])
                and (scope != 'enchanted land' or cid == source[6])}

    while effects:
        # Setting a source land's types removes its printed ability in this layer.
        # Such dependencies override timestamps; cycles fall back to timestamps.
        available = [effect for effect in effects if not any(
            other is not effect and not other[1][2] and other[0][0] not in lost
            and effect[0][0] in targets(other) for other in effects)]
        effect = min(available or effects, key=lambda item: (item[0][5], item[0][0], item[2]))
        effects.remove(effect)
        source, (_, types, addition), _ = effect
        if source[0] in lost:
            continue
        for cid in targets(effect):
            if not addition:
                subtypes[cid] = [word for word in subtypes[cid] if word not in LAND_TYPES]
                lost.add(cid)
            subtypes[cid] = list(dict.fromkeys([*subtypes[cid], *types]))
    lines = {cid: (_split_line(row[1])[0] or 'Land') + ' \u2014 ' + ' '.join(subtypes[cid])
             for cid, row in lands.items() if subtypes[cid] != _split_line(row[1])[1]}
    return lines, frozenset(lost)


def effective_type_line(state, card, *, entering=False, controller=None):
    original = getattr(card, 'type_line', '') or ''
    if state is None or (not entering and getattr(card, 'zone', None) != Zone.BATTLEFIELD):
        return original
    return _view(state, card if entering else None, controller)[0].get(getattr(card, 'id', None), original)


def printed_land_abilities_lost(state, card, *, entering=False, controller=None):
    return (state is not None and (entering or getattr(card, 'zone', None) == Zone.BATTLEFIELD)
            and getattr(card, 'id', None) in _view(state, card if entering else None, controller)[1])


def has_land_type(state, card, subtype):
    line = effective_type_line(state, card)
    return (subtype.lower() in {word.lower() for word in _split_line(line)[1] if word in LAND_TYPES}
            or not line and getattr(card, 'name', '').removeprefix('Snow-Covered ').lower() == subtype.lower())
