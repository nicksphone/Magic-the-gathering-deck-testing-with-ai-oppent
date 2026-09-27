"""Selected spell characteristics, separate from the card's printed identity."""
from copy import copy

from game_state.state import _infer_keywords

CARD_TYPES = {"Artifact", "Battle", "Creature", "Enchantment", "Instant", "Land", "Planeswalker", "Sorcery", "Kindred"}
FACE_FIELDS = ("name", "oracle_text", "mana_cost", "type_line", "types", "power", "toughness", "loyalty", "keywords", "image_uri", "selected_face_index")


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
    proxy.types = [value for value in proxy.type_line.replace("—", " ").split() if value in CARD_TYPES]
    proxy.keywords = _infer_keywords(proxy.oracle_text)
    for field in ("power", "toughness", "loyalty"):
        value = face.get(field)
        setattr(proxy, field, int(value) if value is not None and str(value).lstrip("-").isdigit() else None)
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
