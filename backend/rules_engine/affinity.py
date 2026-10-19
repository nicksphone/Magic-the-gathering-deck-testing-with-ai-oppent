"""Affinity discounts use current controlled permanents at cost determination."""
import re
from functools import lru_cache

from game_state.state import Zone
from rules_engine.card_types import CREATURE_SUBTYPES, creature_subtype_candidates, is_token_card
from rules_engine.oracle_text import without_reminder_text
from rules_engine.type_effects import effective_types

TYPES = {'artifacts': 'Artifact', 'creatures': 'Creature', 'enchantments': 'Enchantment',
         'planeswalkers': 'Planeswalker', 'lands': 'Land', 'battles': 'Battle'}
LANDS = {'plains': 'Plains', 'islands': 'Island', 'swamps': 'Swamp',
         'mountains': 'Mountain', 'forests': 'Forest', 'gates': 'Gate', 'towns': 'Town'}
SUBTYPES = {'foods': ('Artifact', 'food'), 'equipment': ('Artifact', 'equipment'),
            'auras': ('Enchantment', 'aura')}
SPELLS = {'spells': None, 'artifact creature spells': {'Artifact', 'Creature'},
          'enchantment spells': {'Enchantment'},
          'creature and planeswalker spells': {'Creature', 'Planeswalker'},
          'instant and sorcery spells': {'Instant', 'Sorcery'}}


def supported_subject(subject):
    return (subject in TYPES or subject in LANDS or subject in SUBTYPES
            or subject in {'tokens', 'artifact creatures', 'snow lands', 'historic permanents', 'outlaws'}
            or bool(creature_subtype_candidates(subject) & CREATURE_SUBTYPES))


@lru_cache(maxsize=4096)
def affinity_clauses(text):
    """Only whole intrinsic or unconditional grant clauses are executable."""
    intrinsic, grants, gaps = [], [], []
    for line in without_reminder_text(text or '').lower().splitlines():
        if 'affinity for' not in line:
            continue
        line = line.strip().rstrip('.')
        own = re.fullmatch(r'affinity for (.+)', line)
        grant = re.fullmatch(r'(.+) you cast have affinity for (.+)', line)
        if own and supported_subject(own[1]):
            intrinsic.append(own[1])
        elif grant and grant[1] in SPELLS and supported_subject(grant[2]):
            grants.append((grant[1], grant[2]))
        else:
            gaps.append(line)
    return tuple(intrinsic), tuple(grants), tuple(gaps)


def _matches(state, card, subject):
    from rules_engine.continuous import has_keyword
    from rules_engine.land_types import effective_type_line, has_land_type
    from rules_engine.library_permissions import creature_types
    types = set(effective_types(state, card))
    if subject in TYPES:
        return TYPES[subject] in types
    if subject in LANDS:
        return 'Land' in types and has_land_type(state, card, LANDS[subject])
    if subject == 'tokens':
        return is_token_card(card)
    if subject == 'artifact creatures':
        return {'Artifact', 'Creature'} <= types
    if subject == 'snow lands':
        return 'Land' in types and 'Snow' in effective_type_line(state, card).split('—', 1)[0].split()
    subtypes = creature_types(card, state)
    if subject in SUBTYPES:
        kind, subtype = SUBTYPES[subject]
        return kind in types and subtype in subtypes
    if subject == 'historic permanents':
        return ('Artifact' in types or 'Legendary' in card.type_line.split('—', 1)[0].split()
                or 'Enchantment' in types and 'saga' in subtypes)
    candidates = ({'assassin', 'mercenary', 'pirate', 'rogue', 'warlock'} if subject == 'outlaws'
                  else creature_subtype_candidates(subject) & CREATURE_SUBTYPES)
    return bool(types & {'Creature', 'Kindred', 'Tribal'}) and (
        bool(candidates & subtypes) or has_keyword(state, card.id, 'changeling'))


def apply_affinity(context):
    if context.state is None or not context.is_spell:
        return context
    intrinsic, _, _ = affinity_clauses(context.oracle_text)
    subjects = list(intrinsic)
    from rules_engine.continuous import _static_oracle_text, printed_abilities_suppressed
    state = context.state
    controlled = [state.cards[cid] for cid in state.players[context.player_id].battlefield
                  if cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
                  and state.cards[cid].controller == context.player_id]
    for source in controlled:
        _, grants, _ = affinity_clauses(_static_oracle_text(source))
        if not grants or printed_abilities_suppressed(state, source.id):
            continue
        for kind, subject in grants:
            required = SPELLS[kind]
            types = context.spell_types or set()
            applies = required is None or (required <= types if kind == 'artifact creature spells'
                                            else bool(required & types))
            if applies:
                subjects.append(subject)
    # Repeated instances are additive; count each qualifying object once per instance.
    context.generic_reduction += sum(_matches(state, card, subject)
                                     for subject in subjects for card in controlled)
    return context
