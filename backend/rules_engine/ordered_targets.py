"""Bounded ordered counter allocations with explicitly different recipients."""
import re

from rules_engine.oracle_text import without_reminder_text
from rules_engine.spell_cost_clauses import NUMBERS


def ordered_counter_allocations(text):
    clauses = re.split(r',\s*(?:and\s+)?', without_reminder_text(text).lower().strip().rstrip('.'))
    if len(clauses) < 2:
        return None
    amounts = []
    counter = None
    ordinals = ['second', 'third', 'fourth', 'fifth', 'sixth']
    for index, clause in enumerate(clauses):
        recipient = 'target creature' if index == 0 else (
            '(?:another target creature|a second target creature)' if index == 1
            else 'a ' + ordinals[index-1] + ' target creature' if index <= len(ordinals) else '')
        if not recipient:
            return None
        match = re.fullmatch(('put ' if index == 0 else '')
                             + r'(a|an|one|two|three|four|five|six|\d+) ([+-]\d+/[+-]\d+) counters? on '
                             + recipient, clause)
        if match is None or counter is not None and counter != match[2]:
            return None
        counter = match[2]
        amount = int(match[1]) if match[1].isdigit() else 1 if match[1] in {'a', 'an'} else NUMBERS[match[1]]
        amounts.append(amount)
    return {'amounts': amounts, 'counter': counter}
