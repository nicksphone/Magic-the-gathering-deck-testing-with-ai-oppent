"""Bounded, pure layer-four land setting; no later-layer suppression recursion."""
import re
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text
from rules_engine.query_context import query_cache


@dataclass(frozen=True)
class GrantedManaLandReplacement:
    """A land without a basic subtype, with one explicit granted tap ability."""
    granted_mana: str


@lru_cache(maxsize=4096)
def permanent_land_replacement(oracle_text):
    from rules_engine.land_types import BASIC_TYPES
    raw_lines = [line.strip() for line in (oracle_text or '').splitlines() if line.strip()]
    generic = re.compile(
        r'enchanted permanent is a colorless land with "\{T\}: Add \{([WUBRGC])\}\.?" '
        r'and loses all other card types and abilities\.', re.I)
    matches = [generic.fullmatch(line) for line in raw_lines]
    if any(matches):
        # All raw lines must be accounted for; unknown parentheses are not reminders.
        if sum(match is not None for match in matches) != 1:
            return None
        for line, match in zip(raw_lines, matches):
            if match is not None:
                continue
            enchant = re.fullmatch(r'enchant (.+)', line, re.I)
            subjects = re.split(r',? (?:or|and) |, ', enchant[1].lower()) if enchant else []
            if not subjects or any(subject not in {
                    'artifact', 'creature', 'enchantment', 'land', 'planeswalker', 'permanent'}
                    for subject in subjects):
                return None
        return GrantedManaLandReplacement(next(match[1].upper() for match in matches if match))
    for line in without_reminder_text(oracle_text or '').lower().splitlines():
        match = re.fullmatch(r'enchanted permanent is a colorless (plains|island|swamp|mountain|forest) land\.', line.strip())
        if match:
            return next(kind for kind in BASIC_TYPES if kind.lower() == match[1])
    return None


@lru_cache(maxsize=4096)
def _printed_layer_four_effect(oracle_text):
    from rules_engine.land_types import land_type_instructions
    from rules_engine.attached_characteristics import attached_compound
    return bool(land_type_instructions(oracle_text) or
                permanent_land_replacement(oracle_text) or attached_compound(oracle_text))


def layer_four_view(state, entering=None, controller=None, *, attached=False):
    cache = query_cache(state) if entering is None and controller is None else None
    key = (layer_four_view, 'attached') if attached else layer_four_view
    if cache is not None and key in cache:
        return cache[key]
    from rules_engine.type_effects import active_type_effects
    cards = [state.cards[cid] for player in state.players.values() for cid in player.battlefield
             if state.cards[cid].zone == Zone.BATTLEFIELD]
    if entering is not None:
        cards = [card for card in cards if card.id != entering.id] + [entering]
    if not any(_printed_layer_four_effect(getattr(card, 'oracle_text', '')) or
               any('creature_subtypes' in effect for effect in active_type_effects(card))
               for card in cards):
        result = () if attached else (MappingProxyType({}), frozenset(), MappingProxyType({}), frozenset())
        if cache is not None:
            cache[layer_four_view] = (MappingProxyType({}), frozenset(), MappingProxyType({}), frozenset())
            cache[(layer_four_view, 'attached')] = ()
    else:
        from rules_engine.type_effects import _base_effective_types, copiable_types
        rows = tuple((card.id, getattr(card, 'type_line', '') or '', getattr(card, 'oracle_text', '') or '',
                      controller if card is entering and controller is not None else card.controller,
                      tuple(_base_effective_types(state, card)),
                      max(state.next_effect_timestamp, state.next_static_order) if card is entering else
                      int(getattr(card, 'effect_timestamp', 0) or getattr(card, 'static_order', 0) or 0),
                      getattr(card, 'attached_to', None), card.name,
                      _type_operations(state, card),
                      tuple(copiable_types(card)),
                      int(getattr(card, 'battlefield_incarnation', None) if getattr(card, 'battlefield_incarnation', None) is not None
                          else getattr(card, 'effect_timestamp', 0) or getattr(card, 'static_order', 0) or 0),
                      int(getattr(card, 'zone_change_sequence', 0))) for card in cards)
        resolved = _resolve(rows)
        result = resolved[4] if attached else resolved[:4]
    if cache is not None:
        cache[key] = result
    return result


def prior_layer_abilities_lost(state, card):
    return card.zone == Zone.BATTLEFIELD and card.id in layer_four_view(state)[1]


def _type_operations(state, card):
    from rules_engine.type_effects import active_type_effects, devotion_type_condition
    from rules_engine.devotion import devotion_count
    operations = [(effect['timestamp'], 'add', tuple(effect['types'])) for effect in active_type_effects(card)]
    operations.extend((effect['timestamp'], 'creature_subtypes', tuple(effect['creature_subtypes']))
                      for effect in active_type_effects(card) if 'creature_subtypes' in effect)
    stamp = int(getattr(card, 'effect_timestamp', 0) or getattr(card, 'static_order', 0) or 0)
    condition = devotion_type_condition(getattr(card, 'oracle_text', ''), card.name)
    if condition and devotion_count(state, card.controller, condition[0]) < condition[1]:
        operations.insert(0, (stamp, 'remove', ('Creature',)))
    if '__crew_until_turn' in (getattr(card, 'counters', {}) or {}):
        operations.append((stamp, 'add', ('Artifact', 'Creature')))
    return tuple(operations)


@lru_cache(maxsize=512)
def _resolve(rows):
    from rules_engine.card_types import CARD_TYPES, CREATURE_SUBTYPES
    from rules_engine.land_types import LAND_TYPES, BASIC_TYPES, land_type_instructions, _split_line
    from rules_engine.attached_characteristics import attached_compound, AttachedEffect
    by_id = {row[0]: row for row in rows}
    types = {row[0]: list(row[4]) for row in rows}
    subtypes = {row[0]: _split_line(row[1])[1] for row in rows}
    for row in rows:
        if set(row[4]) & {'Creature', 'Kindred', 'Tribal'} and any(
                re.fullmatch(r'changeling\.?', line.strip(), re.I)
                for line in without_reminder_text(row[2]).splitlines()):
            subtypes[row[0]] = list(dict.fromkeys([*subtypes[row[0]], *sorted(CREATURE_SUBTYPES)]))
    lost, colorless, replaced = set(), set(), set()
    creature_replaced, started = set(), []
    effects = []
    replacement_targets = {row[6] for row in rows if permanent_land_replacement(row[2])}
    compound_targets = {row[6] for row in rows if attached_compound(row[2])}
    for row in rows:
        effects.extend((row, 'subtypes', instruction, index, row[5])
                       for index, instruction in enumerate(land_type_instructions(row[2])))
        replacement = permanent_land_replacement(row[2])
        if replacement:
            effects.append((row, 'replace', replacement, -1, row[5]))
        compound = attached_compound(row[2])
        if compound:
            effects.append((row, 'attached_replace', compound, -1, row[5]))
        # Resolved additions survive source loss and compete with replacement timestamps.
        if row[0] in replacement_targets | compound_targets or any(operation == 'creature_subtypes' for _, operation, _ in row[8]):
            effects.extend((row, operation, values, index, stamp)
                           for index, (stamp, operation, values) in enumerate(row[8]))
            types[row[0]] = list(row[9])
        if not row[1] and row[7].removeprefix('Snow-Covered ') in BASIC_TYPES:
            subtypes[row[0]] = [row[7].removeprefix('Snow-Covered ')]

    def targets(effect, current_types=types):
        source, operation, instruction, _, _ = effect
        if operation in {'add', 'remove', 'creature_subtypes'}:
            return {source[0]}
        if operation == 'replace':
            return {source[6]} if source[6] in by_id else set()
        if operation == 'attached_replace':
            return ({source[6]} if source[6] in by_id
                    and 'Enchantment' in current_types[source[0]]
                    and 'Aura' in subtypes[source[0]]
                    and 'Creature' in current_types[source[6]] else set())
        scope = instruction[0]
        return {cid for cid, row in by_id.items() if 'Land' in current_types[cid]
                and (scope != 'nonbasic lands' or not (
                    'Basic' in _split_line(row[1])[0].split() or
                    not row[1] and row[7].removeprefix('Snow-Covered ') in (*BASIC_TYPES, 'Wastes')))
                and (scope != 'lands you control' or row[3] == source[3])
                and (scope != 'enchanted land' or cid == source[6])}

    def removes_printed(effect):
        return effect[1] == 'replace' or effect[1] == 'subtypes' and not effect[2][2]

    def depends(effect, other):
        if effect is other or other[0][0] in lost and other[1] not in {'add', 'creature_subtypes'}:
            return False
        affected = targets(other)
        if removes_printed(other) and effect[1] not in {'add', 'creature_subtypes'} and effect[0][0] in affected:
            return True
        if (other[1] in {'replace', 'attached_replace'} or
                effect[1] == 'attached_replace' and other[1] in {'add', 'remove'}):
            changed = {cid: list(values) for cid, values in types.items()}
            for cid in affected:
                if other[1] in {'replace', 'attached_replace'}:
                    changed[cid] = ['Land'] if other[1] == 'replace' else ['Creature']
                elif other[1] == 'add':
                    changed[cid] = list(dict.fromkeys([*changed[cid], *other[2]]))
                else:
                    changed[cid] = [kind for kind in changed[cid] if kind not in other[2]]
            return targets(effect, changed) != targets(effect)
        return False

    while effects:
        available = [effect for effect in effects if not any(depends(effect, other) for other in effects)]
        effect = min(available or effects, key=lambda item: (item[4], item[0][0], item[3]))
        effects.remove(effect)
        source, operation, instruction, _, _ = effect
        if source[0] in lost and operation not in {'add', 'creature_subtypes'}:
            continue
        for cid in targets(effect):
            if operation == 'add':
                types[cid] = list(dict.fromkeys([*types[cid], *instruction]))
                subtypes[cid] = list(dict.fromkeys([*subtypes[cid], *(kind for kind in instruction if kind not in CARD_TYPES)]))
            elif operation == 'remove':
                types[cid] = [kind for kind in types[cid] if kind not in instruction]
            elif operation == 'creature_subtypes':
                subtypes[cid] = [word for word in subtypes[cid] if word.lower() not in CREATURE_SUBTYPES]
                subtypes[cid] = list(dict.fromkeys([*subtypes[cid], *(word.capitalize() for word in instruction)]))
            elif operation == 'replace':
                types[cid], subtypes[cid] = ['Land'], [instruction] if isinstance(instruction, str) else []
                lost.add(cid)
                colorless.add(cid)
                replaced.add(cid)
            elif operation == 'attached_replace':
                types[cid], subtypes[cid] = ['Creature'], list(instruction.subtypes)
                creature_replaced.add(cid)
                target = by_id[cid]
                started.append(AttachedEffect((source[0], source[10], source[11]),
                                              (cid, target[10], target[11]), source[5], instruction))
            else:
                _, values, addition = instruction
                if not addition:
                    subtypes[cid] = [word for word in subtypes[cid] if word not in LAND_TYPES]
                    lost.add(cid)
                subtypes[cid] = list(dict.fromkeys([*subtypes[cid], *values]))
    lines = {}
    for cid, row in by_id.items():
        if cid in replaced | creature_replaced or any(operation == 'creature_subtypes' for _, operation, _ in row[8]):
            supertypes = [word for word in _split_line(row[1])[0].split()
                          if word in {'Basic', 'Legendary', 'Snow', 'World', 'Ongoing'}]
            prefix = ' '.join([*supertypes, *(kind for kind in types[cid] if kind in CARD_TYPES)])
        else:
            prefix = _split_line(row[1])[0] or 'Land'
        if (cid in replaced | creature_replaced or any(operation == 'creature_subtypes' for _, operation, _ in row[8])
                or 'Land' in types[cid] and subtypes[cid] != _split_line(row[1])[1]):
            lines[cid] = prefix + (' \u2014 ' + ' '.join(subtypes[cid]) if subtypes[cid] else '')
    changed_types = {cid: tuple(values) for cid, values in types.items() if tuple(values) != by_id[cid][4]}
    return (MappingProxyType(lines), frozenset(lost), MappingProxyType(changed_types), frozenset(colorless),
            tuple(started))
