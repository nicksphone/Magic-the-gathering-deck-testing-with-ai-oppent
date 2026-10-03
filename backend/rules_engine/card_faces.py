"""Selected spell characteristics, separate from the card's printed identity."""
from copy import copy

from game_state.state import _infer_keywords
from game_state.state import Zone
from rules_engine.card_types import is_token_card, printed_card_types

FACE_FIELDS = ("name", "oracle_text", "mana_cost", "type_line", "types", "power", "toughness", "printed_power", "printed_toughness", "loyalty", "keywords", "image_uri", "selected_face_index", "colors")


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
    return proxy


def apply_cast_face(card, face):
    if face is card:
        return
    # Reuse the snapshot-safe restoration used by Prototype and zone changes.
    for field in FACE_FIELDS:
        card.printed_characteristics.setdefault(field, copy(getattr(card, field)))
        setattr(card, field, copy(getattr(face, field)))


def apply_transform_face(card, index):
    """Apply a battlefield face without changing the card's printed identity."""
    face = select_cast_face(card, index)
    front = select_cast_face(card, 0)
    for field in FACE_FIELDS:
        card.printed_characteristics.setdefault(field, copy(getattr(front, field)))
        setattr(card, field, copy(getattr(face, field)))


def exile_permission(state, player_id, card_id, face_index=0):
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.EXILE or is_token_card(card):
        return False
    player = state.players[player_id]
    temporary = card_id in player.exile and player.exile_play_until.get(card_id, 0) >= state.turn
    return temporary or (state.adventure_permissions.get(card_id) == player_id and face_index == 0)


def exile_candidates(state, player_id):
    return list(dict.fromkeys(state.players[player_id].exile + [
        cid for cid, pid in state.adventure_permissions.items()
        if pid == player_id and cid in state.cards and state.cards[cid].zone == Zone.EXILE
    ]))


def leave_exile(state, card_id):
    for player in state.players.values():
        if card_id in player.exile:
            player.exile.remove(card_id)
        player.exile_play_until.pop(card_id, None)
    state.adventure_permissions.pop(card_id, None)
