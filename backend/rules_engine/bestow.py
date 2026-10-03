"""Bestow characteristics persist independently of printed Oracle text."""
from copy import copy
import re

from rules_engine.oracle_text import without_reminder_text


def bestow_cost(card):
    match = re.search(r'(?:^|\n)bestow\s+((?:\{[^}]+\})+)',
                      without_reminder_text(card.oracle_text or ''), re.I)
    return match[1] if match else None


def is_bestowed(card):
    return bool(getattr(card, 'bestow_characteristics', {}))


def begin_bestow(card):
    if is_bestowed(card):
        return
    card.bestow_characteristics = {'types': list(card.types), 'type_line': card.type_line}
    # Bestow replaces card/creature types, not supertypes or mana cost/colors.
    from rules_engine.card_types import CARD_TYPES
    supertypes = [value for value in card.types if value not in CARD_TYPES]
    card.types = supertypes + ['Enchantment']
    card.type_line = ' '.join(card.types) + ' \u2014 Aura'


def end_bestow(card):
    if not is_bestowed(card):
        return
    for key, value in card.bestow_characteristics.items():
        setattr(card, key, copy(value))
    card.bestow_characteristics = {}
    card.attached_to = None


def bestow_cast_view(card):
    view = copy(card)
    view.bestow_characteristics = dict(getattr(card, 'bestow_characteristics', {}))
    begin_bestow(view)
    return view
