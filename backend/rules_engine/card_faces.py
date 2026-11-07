"""Selected spell characteristics, separate from the card's printed identity."""
from copy import copy

from game_state.state import _infer_keywords
from game_state.state import Zone
from rules_engine.card_types import is_token_card, printed_card_types

FACE_FIELDS = ("name", "oracle_text", "mana_cost", "type_line", "types", "power", "toughness", "printed_power", "printed_toughness", "loyalty", "keywords", "image_uri", "selected_face_index", "colors")
EXILE_PLAY_DURATIONS = frozenset({'this_turn', 'controller_next_turn', 'next_controller_end_step'})


def select_cast_face(card, index=None):
    faces = list(getattr(card, "card_faces", []) or [])
    if not faces:
        return card
    index = int(index if index is not None else 0)
    if not 0 <= index < len(faces):
        raise ValueError("Selected card face is unavailable")
    face = faces[index]
    proxy = copy(card)
    for field in ("name", "oracle_text", "mana_cost", "type_line"):
        setattr(proxy, field, str(face.get(field, getattr(card, field, "")) or ""))
    proxy.types = printed_card_types(proxy.type_line)
    proxy.keywords = _infer_keywords(proxy.oracle_text)
    proxy.colors = face.get("colors")
    for field in ("power", "toughness", "loyalty"):
        value = face.get(field)
        setattr(proxy, field, int(value) if value is not None and str(value).lstrip("-").isdigit() else None)
        if field in {'power', 'toughness'}:
            setattr(proxy, f'printed_{field}', str(value) if value is not None else None)
    proxy.image_uri = face.get("image_uri") or getattr(card, "image_uri", None)
    proxy.selected_face_index = index
    from rules_engine.copiable_values import record_form
    record_form(proxy)
    return proxy


def apply_cast_face(card, face):
    if face is card:
        return
    # Reuse the snapshot-safe restoration used by Prototype and zone changes.
    for field in FACE_FIELDS:
        card.printed_characteristics.setdefault(field, copy(getattr(card, field)))
        setattr(card, field, copy(getattr(face, field)))
    from rules_engine.copiable_values import record_form
    record_form(card)


def apply_transform_face(card, index):
    """Apply a battlefield face without changing the card's printed identity."""
    face = select_cast_face(card, index)
    front = select_cast_face(card, 0)
    for field in FACE_FIELDS:
        card.printed_characteristics.setdefault(field, copy(getattr(front, field)))
        setattr(card, field, copy(getattr(face, field)))
    from rules_engine.copiable_values import record_form
    record_form(card)
    from rules_engine.type_effects import rebase_type_effects
    rebase_type_effects(card)


def day_night_entry_face(state, card):
    """Project entry characteristics without transforming a spell on the stack."""
    import re
    from rules_engine.oracle_text import without_reminder_text
    if card.layout != 'transform' or len(card.card_faces) < 2:
        return card
    front, back = card.card_faces[:2]
    if not (re.search(r'\bdaybound\b', without_reminder_text(front.get('oracle_text') or ''), re.I)
            and re.search(r'\bnightbound\b', without_reminder_text(back.get('oracle_text') or ''), re.I)):
        return card
    return select_cast_face(card, 1 if state.day_night == 'night' else 0)


def apply_day_night_entry(state, card):
    face = day_night_entry_face(state, card)
    if face is card:
        return
    apply_transform_face(card, face.selected_face_index)
    if state.day_night == 'none':
        state.day_night = 'day'
        state.log.append('The game becomes day.')


def exile_permission(state, player_id, card_id, face_index=0):
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.EXILE or is_token_card(card):
        return False
    from rules_engine.foretell import cast_permission
    if cast_permission(state, player_id, card) and 'Land' not in select_cast_face(card, face_index).types:
        return True
    return ordinary_exile_permission(state, player_id, card_id, face_index)


def ordinary_exile_permission(state, player_id, card_id, face_index=0):
    from rules_engine.source_linked_exile import permissions
    player = state.players[player_id]
    temporary = card_id in player.exile and player.exile_play_until.get(card_id, 0) >= state.turn
    return temporary or _current_exile_play_duration(state, player_id, card_id) or (state.adventure_permissions.get(card_id) == player_id and face_index == 0) or bool(permissions(state, player_id, card_id))


def grant_exile_play_duration(state, player_id, card_id, duration):
    from rules_engine.source_linked_exile import reference
    if duration not in EXILE_PLAY_DURATIONS:
        raise ValueError('Unsupported exile play duration')
    card = state.cards[card_id]
    if card.zone != Zone.EXILE or card_id not in state.players[player_id].exile:
        raise ValueError('A duration grant requires the actual exiled object')
    state.players[player_id].exile_play_durations[card_id] = {
        'version': 1, 'duration': duration, 'grant_turn': state.turn, 'reference': reference(card)}


def _current_exile_play_duration(state, player_id, card_id):
    from rules_engine.source_linked_exile import reference
    player = state.players[player_id]
    card = state.cards.get(card_id)
    row = player.exile_play_durations.get(card_id)
    return bool(row and card and card.zone == Zone.EXILE and not card.exile_face_down
                and not is_token_card(card) and card_id in player.exile
                and row['grant_turn'] <= state.turn and row['reference'] == reference(card)
                and (row['duration'] != 'this_turn' or row['grant_turn'] == state.turn))


def expire_exile_play_durations(state, boundary='cleanup'):
    # Called only on actual boundary entry, never on priority passes.
    if boundary not in {'cleanup', 'end_step'}:
        raise ValueError('Unknown exile play duration boundary')
    for pid, player in state.players.items():
        for cid, row in list(player.exile_play_durations.items()):
            expires = (boundary == 'cleanup' and (row['duration'] == 'this_turn'
                or row['duration'] == 'controller_next_turn'
                and state.active_player == pid and state.turn > row['grant_turn']))
            expires = expires or (boundary == 'end_step' and row['duration'] == 'next_controller_end_step'
                                  and state.active_player == pid)
            if expires or not _current_exile_play_duration(state, pid, cid):
                player.exile_play_durations.pop(cid)


def restore_exile_play_durations(value, current_turn):
    from copy import deepcopy
    if type(value) is not dict:
        raise ValueError('Invalid exile play duration records')
    for cid, row in value.items():
        if (type(cid) is not str or not cid or type(row) is not dict
                or set(row) != {'version', 'duration', 'grant_turn', 'reference'}
                or type(row['version']) is not int or row['version'] != 1
                or type(row['duration']) is not str or row['duration'] not in EXILE_PLAY_DURATIONS
                or type(row['grant_turn']) is not int or not 1 <= row['grant_turn'] <= current_turn):
            raise ValueError('Invalid exile play duration')
        ref = row['reference']
        if (type(ref) is not dict or set(ref) != {'id', 'incarnation', 'sequence'} or ref['id'] != cid
                or any(type(ref[key]) is not int or ref[key] < 0 for key in ('incarnation', 'sequence'))):
            raise ValueError('Invalid exile play object reference')
    return deepcopy(value)


def exile_candidates(state, player_id):
    from rules_engine.source_linked_exile import candidates
    return list(dict.fromkeys(state.players[player_id].exile + [
        cid for cid, pid in state.adventure_permissions.items()
        if pid == player_id and cid in state.cards and state.cards[cid].zone == Zone.EXILE
    ] + [cid for cid, card in state.cards.items() if card.zone == Zone.EXILE
         and card.foretell_record.get('player_id') == player_id] + candidates(state, player_id)))


def leave_exile(state, card_id):
    for player in state.players.values():
        if card_id in player.exile:
            player.exile.remove(card_id)
        player.exile_play_until.pop(card_id, None)
        player.exile_play_durations.pop(card_id, None)
    state.adventure_permissions.pop(card_id, None)
