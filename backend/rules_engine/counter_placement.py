"""Physical counter placement and bounded, unconditional Oracle prohibitions."""
from __future__ import annotations

import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.continuous import _static_oracle_text, _static_text_from_oracle
from rules_engine.oracle_text import without_reminder_text


@lru_cache(maxsize=4096)
def parse_counter_prohibition(clause, name=''):
    match = re.fullmatch(r"(players|you|your opponents) can't get(?: ([a-z-]+))? counters", clause)
    if match:
        return ('player', match[1], match[2])
    subject = rf'(?:this (?:creature|permanent|artifact)|{re.escape(name.lower())})'
    if re.fullmatch(subject + r" can't have counters put on (?:it|them)", clause):
        return ('self', None, None)
    match = re.fullmatch(r"counters can't be put on (.+)", clause)
    if match:
        types = tuple(re.split(r',?\s+or\s+|,\s*', match[1]))
        if all(value in {'artifacts', 'creatures', 'enchantments', 'lands', 'planeswalkers', 'battles'} for value in types):
            return ('types', types, None)
    match = re.fullmatch(r"creatures you control can't have ([+-]\d+/[+-]\d+) counters put on them", clause)
    if match:
        return ('controlled_creature', None, match[1])
    return None


def unsupported_counter_prohibitions(oracle_text):
    static = {value.strip() for value in re.split(r'[.\n]', _static_text_from_oracle(oracle_text))}
    for clause in re.split(r'[.\n]', without_reminder_text(oracle_text).lower()):
        clause = clause.strip()
        if not re.search(r"(?:can't|cannot).*counters|counters.*(?:can't|cannot).*put", clause):
            continue
        if clause not in static or not parse_counter_prohibition(clause):
            return True
    return False


def counter_placement_forbidden(state, kind, *, target_player=None, target_card_id=None):
    target = state.cards.get(target_card_id)
    if target is not None and not any(target.id in player.battlefield for player in state.players.values()):
        for clause in re.split(r'[.\n]', _static_oracle_text(target)):
            instruction = parse_counter_prohibition(clause.strip(), target.name)
            if instruction is not None and instruction[0] == 'self':
                return True
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards.get(cid)
            if source is None or source.zone != Zone.BATTLEFIELD:
                continue
            # Only standalone static sentences, not reminder, quoted, activated,
            # conditional or triggered instructions that have not resolved.
            for clause in re.split(r'[.\n]', _static_oracle_text(source)):
                clause = clause.strip()
                instruction = parse_counter_prohibition(clause, source.name)
                if instruction is None:
                    continue
                category, selector, counter = instruction
                if target_player is not None and category == 'player' and (counter is None or counter == kind):
                    if (selector == 'players' or
                            (selector == 'you' and target_player == source.controller) or
                            (selector == 'your opponents' and target_player != source.controller)):
                        return True
                elif target is not None:
                    if category == 'self' and source.id == target.id:
                        return True
                    if category == 'types' and any(value[:-1].title() in target.types for value in selector):
                        return True
                    if (category == 'controlled_creature' and counter == kind and 'Creature' in target.types
                            and target.controller == source.controller):
                        return True
    return False


def put_counters(state, kind, amount, *, target_player=None, target_card_id=None, placement_checked=False):
    """Return actual counters placed; internal damage/buff markers are not counters.

    Scalar replacements and replacement ordering are supplied by callers.
    Lore placement emits chapter events after the physical count changes.
    Legacy poison, lore and loyalty storage remain authoritative.
    Entry packets commit an already checked event without consulting abilities
    that only became active when the recipient entered.
    """
    amount = max(0, int(amount))
    if not amount or str(kind).startswith('__'):
        return 0
    if target_player is not None:
        target = state.players.get(target_player)
    else:
        target = state.cards.get(target_card_id)
        if target is None or target.zone != Zone.BATTLEFIELD:
            return 0
    if target is None:
        return 0
    if not placement_checked and counter_placement_forbidden(state, kind, target_player=target_player, target_card_id=target_card_id):
        state.log.append(f'{target.name} cannot get {kind} counters.')
        return 0
    if target_player is not None and kind == 'poison':
        target.poison += amount
    elif (target_player is None and kind == 'loyalty'
          and (target.loyalty is not None or 'Planeswalker' in target.types)):
        target.loyalty = int(target.loyalty or 0) + amount
    else:
        key = '__lore' if target_player is None and kind == 'lore' and 'Saga' in target.type_line else kind
        before = int(target.counters.get(key, 0))
        target.counters[key] = before + amount
        if key == '__lore':
            from rules_engine.events import emit_event
            emit_event(state, 'saga_lore_added', {
                'card_id': target.id, 'old_lore': before, 'new_lore': before + amount,
            })
    return amount
