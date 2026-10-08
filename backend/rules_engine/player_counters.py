"""Shared player counters and explicitly supported Oracle counter clauses."""
from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import Step

PLAYER_COUNT_RE = r'number of ([a-z-]+) counters you have'
GAIN_RE = re.compile(r'(.+), you get (a|an|one|two|three|four|five|\d+) ([a-z-]+) counters?\.?', re.I)
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
COMBAT_STEPS = {Step.BEGIN_COMBAT, Step.DECLARE_ATTACKERS, Step.DECLARE_BLOCKERS,
                Step.COMBAT_DAMAGE, Step.END_COMBAT}


def counter_count(player, kind):
    # Keep the legacy poison field authoritative for existing combat/SBA paths.
    return max(0, int(player.poison if kind == 'poison' else player.counters.get(kind, 0)))


def public_counters(player):
    return {kind: counter_count(player, kind) for kind in sorted(set(player.counters) | {'poison'})
            if counter_count(player, kind)}


def gain_clause(line):
    """Return a bounded instruction; do not infer an unknown trigger condition."""
    match = GAIN_RE.fullmatch(line.strip())
    if not match:
        energy = re.fullmatch(r'(.+), you get ((?:\{E\}){1,64})'
                              r'(?: \(([^()]*)\))?\s*\.?', line.strip(), re.I)
        if energy is None:
            return None
        prefix, symbols, reminder = energy.groups()
        prefix, amount, counter = prefix.lower(), len(symbols)//3, 'energy'
        if reminder is not None:
            count = re.fullmatch(r'(a|an|one|two|three|four|five|\d+) energy counters?', reminder, re.I)
            if count is None:
                return None
            word = count[1].lower()
            if (int(word) if word.isdigit() else NUMBERS[word]) != amount:
                return None
    else:
        prefix, count, counter = (value.lower() for value in match.groups())
        amount = int(count) if count.isdigit() else NUMBERS[count]
    if prefix == 'at the beginning of your end step, if a permanent you controlled left the battlefield this turn':
        return ('end_step_departure', amount, counter, None, None)
    if prefix == 'whenever another creature you control dies':
        return ('another_death', amount, counter, None, None)
    cast = re.fullmatch(r'whenever you cast an? (creature|artifact|enchantment|instant|sorcery|instant or sorcery) spell(?: with mana value (\d+) or greater)?', prefix)
    if cast:
        return ('cast', amount, counter, cast[1], int(cast[2]) if cast[2] else None)
    entry = re.fullmatch(r'(?:landfall\s*[—-]\s*)?whenever an? (creature|land|artifact|enchantment) you control(?: with power (\d+) or less)? enters(?: the battlefield)?', prefix)
    if entry:
        return ('entry', amount, counter, entry[1], int(entry[2]) if entry[2] else None)
    if prefix in {"whenever you cast a spell during an opponent's turn", 'whenever you cast a spell during combat'}:
        return ('cast_opponent_turn' if "opponent's" in prefix else 'cast_combat', amount, counter, None, None)
    return None


def gain_matches(state, source, event, payload, instruction):
    kind, _, _, selector, threshold = instruction
    if kind == 'end_step_departure':
        return (event == 'begin_step' and payload.get('step') == 'end_step'
                and payload.get('active_player') == source.controller
                and source.controller in state.players_with_permanent_departure)
    if kind == 'another_death':
        return (event == 'creature_dies' and payload.get('controller') == source.controller
                and payload.get('card_id') != source.id)
    if kind.startswith('cast'):
        if event != 'spell_cast' or payload.get('controller') != source.controller:
            return False
        if kind == 'cast_opponent_turn':
            return state.active_player != source.controller
        if kind == 'cast_combat':
            return state.step in COMBAT_STEPS
        card = state.cards.get(payload.get('source_card_id'))
        if not card or not set(selector.split(' or ')).intersection(t.lower() for t in effective_types(state, card)):
            return False
        from rules_engine.mana import mana_value
        return threshold is None or mana_value(card.mana_cost, x_value=int(payload.get('x_value', 0))) >= threshold
    if event != 'enters_battlefield':
        return False
    card = state.cards.get(payload.get('card_id'))
    if not card or card.controller != source.controller or selector.title() not in effective_types(state, card):
        return False
    from rules_engine.continuous import effective_power
    return threshold is None or effective_power(state, card.id) <= threshold


def gain_triggers(state, source, event, payload, oracle):
    if 'you get' not in oracle:
        return [], oracle
    from rules_engine.oracle_text import without_reminder_text
    raw_lines = (source.oracle_text or '').splitlines()
    triggers, remaining = [], []
    for line in oracle.splitlines():
        # The event surface has erased parentheses; recognition must use raw text.
        candidates = {raw.strip() for raw in raw_lines
                      if without_reminder_text(raw).strip().casefold() == line.strip().casefold()}
        instruction = gain_clause(next(iter(candidates))) if len(candidates) == 1 else None
        if instruction is None:
            remaining.append(line)
            continue
        if gain_matches(state, source, event, payload, instruction):
            kind, amount, counter, _, _ = instruction
            triggers.append({'source_card_id': source.id, 'controller': source.controller,
                'label': f'{source.name} {counter} counter trigger', 'effect_key': 'add_player_counters',
                'payload': {'target_player': source.controller, 'counter': counter, 'amount': amount,
                            'requires_departure': kind == 'end_step_departure'}})
    return triggers, '\n'.join(remaining)

