"""Closed bounded removal instructions using existing individual handlers."""
import re

from game_state.state import object_incarnation

KINDS = r'(?:artifact|battle|creature|enchantment|land|planeswalker|permanent)s?'
COUNT = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|[1-9]\d*)'
# The optional complete cost paragraph is not a target restriction. This
# compiler implements resolution only; casting-cost availability stays owned
# by the existing cost compiler.
COST = (r"(?:If it's not your turn, you may exile a (?:white|blue|black|red|green) "
        r"card from your hand rather than pay this spell's mana cost\.\s*)?")
BODY = re.compile(COST + r'(Destroy|Exile) up to (' + COUNT + r') target ('
                  + KINDS + r'(?:(?:, |,? (?:or|and/or) )' + KINDS + r')*)\.', re.I)


def instruction(text):
    from rules_engine.oracle_effects import _parse_count_token
    match = BODY.fullmatch((text or '').strip())
    if match is None:
        return None
    kinds = [kind.removesuffix('s') for kind in re.findall(KINDS, match[3].lower())]
    return {'effect_key': 'destroy_permanent' if match[1].lower() == 'destroy' else 'exile_permanent',
            'count': _parse_count_token(match[2].lower()),
            'allowed_types': ([] if 'permanent' in kinds else [kind.title() for kind in kinds])}


def effect(state, compiled, targets):
    ids = targets.get('target_card_ids', [])
    if ids and targets.get('target_card_id') is not None:
        return 'noop', {'__unsupported_instruction': 'mixed bounded target selection'}
    if targets.get('target_card_id') is not None:
        ids = [targets['target_card_id']]
    if len(ids) > compiled['count'] or len(ids) != len(set(ids)) or any(cid not in state.cards for cid in ids):
        return 'noop', {'__unsupported_instruction': 'invalid bounded target selection'}
    if targets.get('target_card_id') is not None:
        return compiled['effect_key'], {'target_card_id': targets['target_card_id']}
    return 'effect_sequence', {'effects': [
        {'effect_key': compiled['effect_key'], 'payload': {
            'target_card_id': cid, '__target_incarnation': object_incarnation(state.cards[cid]),
            '__target_zone_sequence': state.cards[cid].zone_change_sequence}}
        for cid in ids], '__ordered_distinct_targets': True}
