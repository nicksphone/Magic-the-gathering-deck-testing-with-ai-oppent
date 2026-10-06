"""Printed graveyard permissions do not waive timing, costs or prohibitions."""
import re

from game_state.state import Zone
from rules_engine.oracle_text import without_reminder_text
from rules_engine.query_context import scoped_query
from rules_engine.type_effects import effective_types
from rules_engine.zone_actions import is_departed_token


def _clauses(card):
    return [line.strip().lower() for line in without_reminder_text(card.oracle_text or '').splitlines()]


def _self_names(name):
    return '|'.join(re.escape(value) for value in dict.fromkeys(('this card', name.lower(), name.split(',')[0].lower())) if value)


def _self_permission(clause, name):
    return re.fullmatch(r'you may cast (?:' + _self_names(name) + r') from your graveyard'
                        r'(?: as long as you control an? (?P<subtype>[a-z]+)|(?P<only>, but not from anywhere else))?\.', clause)


def _typed_grant(clause, name):
    return re.fullmatch(r'(?:as long as (?:' + _self_names(name)
                        + r') is on the battlefield, )?you may cast (?P<type>[a-z]+) spells from your graveyard\.', clause)


def _limited_grant(clause):
    return re.fullmatch(r'once during each of your turns, you may cast '
                       r'(?:a permanent spell with mana value (?P<mv>\d+) or less|'
                       r'an? (?P<subtype>[a-z]+) creature spell) from your graveyard\.', clause)


def _per_type_grant(clause):
    return clause == ('during each of your turns, you may play a land and cast a permanent spell '
                      'of each permanent type from your graveyard.')


def limited_graveyard_casts(state, player_id, card):
    if (state.active_player != player_id or card.zone != Zone.GRAVEYARD
            or card.owner != player_id or card.id not in state.players[player_id].graveyard
            or is_departed_token(card)):
        return []
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.mana import mana_value
    choices = []
    types = set(effective_types(state, card))
    for cid in state.players[player_id].battlefield:
        source = state.cards[cid]
        clauses = _clauses(source)
        if (source.zone != Zone.BATTLEFIELD or source.controller != player_id
                or not any(_limited_grant(clause) or _per_type_grant(clause) for clause in clauses)
                or printed_abilities_suppressed(state, cid)):
            continue
        for index, clause in enumerate(clauses):
            grant = _limited_grant(clause)
            per_type = _per_type_grant(clause)
            if not grant and not per_type:
                continue
            permanent_types = types.intersection({'Creature', 'Artifact', 'Enchantment', 'Planeswalker', 'Battle'})
            limit = int(grant['mv']) if grant and grant['mv'] is not None else None
            if per_type:
                if not permanent_types:
                    continue
            elif limit is not None:
                if not types.intersection({'Creature', 'Artifact', 'Enchantment', 'Planeswalker', 'Battle'}):
                    continue
                if mana_value(card.mana_cost or '') > limit:
                    continue
            elif 'Creature' not in types or not _has_creature_subtype(state, card, grant['subtype']):
                continue
            for bucket in sorted(permanent_types) if per_type else ['spell']:
                key = f'{player_id}:{cid}:{source.zone_change_sequence}:{index}:{bucket}'
                if getattr(state, 'graveyard_permission_uses', {}).get(key) == state.turn:
                    continue
                choices.append({'key': key, 'source_name': source.name,
                                'type': bucket if per_type else None, 'max_mana_value': limit})
    return choices


def record_graveyard_permission(state, key):
    # Bound history to this turn; source-zone sequence distinguishes new objects.
    state.graveyard_permission_uses = {source: turn for source, turn in state.graveyard_permission_uses.items()
                                       if turn == state.turn}
    state.graveyard_permission_uses[key] = state.turn


def permission_gaps(text, name=''):
    for clause in without_reminder_text(text or '').lower().splitlines():
        clause = clause.strip()
        if ('from your graveyard' not in clause or not re.match(
                r'^(?:you may|(?:once during|during|as long as|until)[^.]*you may)\b', clause)):
            continue
        if (clause == 'you may play lands from your graveyard.' or _self_permission(clause, name)
                or _typed_grant(clause, name) or _limited_grant(clause) or _per_type_grant(clause)):
            continue
        return ['unsupported graveyard play permission']
    return []


def graveyard_only_cast(card):
    if 'not from anywhere else' not in (card.oracle_text or '').lower():
        return False
    return any(match and match['only'] for clause in _clauses(card)
               if (match := _self_permission(clause, card.name)))


def _has_creature_subtype(state, card, subtype):
    from rules_engine.continuous import has_keyword
    from rules_engine.library_permissions import creature_types
    return bool({'Creature', 'Kindred', 'Tribal'} & set(effective_types(state, card))) and (
        subtype in creature_types(card, state) or has_keyword(state, card.id, 'changeling'))


@scoped_query
def ordinary_graveyard_cast(state, player_id, card_id):
    return ordinary_graveyard_cast_view(state, player_id, state.cards[card_id])


def ordinary_graveyard_cast_view(state, player_id, card):
    card_id = card.id
    if (card.zone != Zone.GRAVEYARD or card.owner != player_id
            or card_id not in state.players[player_id].graveyard or is_departed_token(card)):
        return False
    from rules_engine.continuous import printed_abilities_suppressed
    for clause in _clauses(card):
        permission = _self_permission(clause, card.name)
        if not permission:
            continue
        subtype = permission['subtype']
        if subtype is None:
            return True
        if any(cid in state.cards and state.cards[cid].zone == Zone.BATTLEFIELD
               and state.cards[cid].controller == player_id
               and _has_creature_subtype(state, state.cards[cid], subtype)
               for cid in state.players[player_id].battlefield):
            return True
    for cid in state.players[player_id].battlefield:
        source = state.cards[cid]
        if source.zone != Zone.BATTLEFIELD or source.controller != player_id:
            continue
        for clause in _clauses(source):
            grant = _typed_grant(clause, source.name)
            if grant and (grant['type'].title() in effective_types(state, card)
                          or _has_creature_subtype(state, card, grant['type'])):
                if not printed_abilities_suppressed(state, cid):
                    return True
    return False


@scoped_query
def graveyard_land_choices(state, player_id, card_id):
    card = state.cards[card_id]
    if (card.zone != Zone.GRAVEYARD or card.owner != player_id
            or card_id not in state.players[player_id].graveyard or is_departed_token(card)):
        return []
    from rules_engine.continuous import printed_abilities_suppressed
    choices = []
    for cid in state.players[player_id].battlefield:
        source = state.cards[cid]
        clauses = _clauses(source)
        if (source.zone != Zone.BATTLEFIELD or source.controller != player_id
                or not any(clause == 'you may play lands from your graveyard.' or _per_type_grant(clause) for clause in clauses)
                or printed_abilities_suppressed(state, cid)):
            continue
        for index, clause in enumerate(clauses):
            if clause == 'you may play lands from your graveyard.':
                choices.append({'key': None, 'source_name': source.name})
            elif _per_type_grant(clause) and state.active_player == player_id:
                key = f'{player_id}:{cid}:{source.zone_change_sequence}:{index}:Land'
                if getattr(state, 'graveyard_permission_uses', {}).get(key) != state.turn:
                    choices.append({'key': key, 'source_name': source.name})
    return sorted(choices, key=lambda choice: choice['key'] is not None)


def graveyard_land_permission(state, player_id, card_id):
    return bool(graveyard_land_choices(state, player_id, card_id))


@scoped_query
def zone_cast_prohibited(state, player_id, zone):
    """Complete supported zone prohibitions also beat effect-authorized casts."""
    if zone == Zone.HAND:
        return False
    from rules_engine.continuous import printed_abilities_suppressed
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            if source.zone != Zone.BATTLEFIELD or printed_abilities_suppressed(state, cid):
                continue
            clauses = _clauses(source)
            if (zone in {Zone.GRAVEYARD, Zone.LIBRARY}
                    and "players can't cast spells from graveyards or libraries." in clauses):
                return True
            if (source.controller != player_id
                    and "your opponents can't cast spells from anywhere other than their hands." in clauses):
                return True
    return False


@scoped_query
def battlefield_entry_prohibited(state, card_id, selected_face_index=0):
    card = state.cards[card_id]
    if card.zone not in {Zone.GRAVEYARD, Zone.LIBRARY}:
        return False
    from rules_engine.card_faces import select_cast_face
    types = set(effective_types(state, select_cast_face(card, selected_face_index)))
    from rules_engine.continuous import printed_abilities_suppressed
    for player in state.players.values():
        for cid in player.battlefield:
            source = state.cards[cid]
            for clause in _clauses(source):
                block = re.fullmatch(r'(creature|nonland permanent) cards in graveyards and libraries '
                                     r"(?:can't|cannot) enter the battlefield\.", clause)
                if not block:
                    continue
                matches = ('Creature' in types if block[1] == 'creature' else
                           'Land' not in types and bool(types & {'Creature', 'Artifact', 'Enchantment', 'Planeswalker', 'Battle'}))
                if matches and source.zone == Zone.BATTLEFIELD and not printed_abilities_suppressed(state, cid):
                    return True
    return False
