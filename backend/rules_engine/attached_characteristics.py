"""Complete attached compounds and their pure, current-incarnation projections."""
from functools import lru_cache
import re
from typing import NamedTuple

from game_state.state import Zone, object_incarnation
from rules_engine.oracle_text import without_reminder_text


class CharacteristicCompound(NamedTuple):
    colors: tuple[str, ...]
    subtypes: tuple[str, ...]
    power: int
    toughness: int


class AttachedEffect(NamedTuple):
    source_ref: tuple[str, int, int]
    target_ref: tuple[str, int, int]
    timestamp: int
    compound: CharacteristicCompound


@lru_cache(maxsize=512)
def attached_compound(oracle_text):
    from rules_engine.card_types import CREATURE_SUBTYPES
    text = without_reminder_text(oracle_text or '').lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 2 or lines[0] != 'enchant creature':
        return None
    match = re.fullmatch(
        r'enchanted creature loses all abilities and is (?:a|an) '
        r'(white|blue|black|red|green|colorless) ([a-z][a-z -]*?)(?: creature)? '
        r'with base power and toughness (\d+)/(\d+)\.', lines[1])
    if not match:
        return None
    subtypes = tuple(match[2].split())
    if not subtypes or any(subtype not in CREATURE_SUBTYPES for subtype in subtypes):
        return None
    colors = {'white': ('W',), 'blue': ('U',), 'black': ('B',),
              'red': ('R',), 'green': ('G',), 'colorless': ()}
    return CharacteristicCompound(colors[match[1]], tuple(word.capitalize() for word in subtypes),
                                  int(match[3]), int(match[4]))


def effects_on(state, target_id):
    from rules_engine.basic_land_layer import layer_four_view
    target = state.cards.get(target_id)
    if target is None or target.zone != Zone.BATTLEFIELD:
        return ()
    effects = layer_four_view(state, attached=True)
    if not effects:
        return ()
    target_ref = (target_id, object_incarnation(target), target.zone_change_sequence)
    result = []
    for effect in effects:
        source = state.cards.get(effect.source_ref[0])
        if (effect.target_ref == target_ref and source is not None
                and source.zone == Zone.BATTLEFIELD and source.attached_to == target_id
                and effect.source_ref == (source.id, object_incarnation(source), source.zone_change_sequence)):
            result.append(effect)
    return tuple(result)
