"""Pure layer-four basic-land type additions, replacements and source dependencies."""
import re
from functools import lru_cache
from rules_engine.query_context import query_cache

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


def _view(state, entering=None, controller=None):
    cache = query_cache(state) if entering is None and controller is None else None
    if cache is not None and 'view' in cache:
        return cache['view']
    result = _uncached_view(state, entering, controller)
    if cache is not None:
        cache['view'] = result
    return result


def _uncached_view(state, entering=None, controller=None):
    from rules_engine.basic_land_layer import layer_four_view
    return layer_four_view(state, entering, controller)[:2]


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
