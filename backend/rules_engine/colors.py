from __future__ import annotations

import re


_MANA_COLOR_MAP = {
    "W": "white",
    "U": "blue",
    "B": "black",
    "R": "red",
    "G": "green",
}


def card_color_symbols(card) -> set[str]:
    faces = getattr(card, "card_faces", None) or []
    if faces:
        index = getattr(card, "selected_face_index", None)
        if getattr(card, "layout", "") == "split" and index is None:
            explicit = getattr(card, "colors", None)
            if isinstance(explicit, (list, tuple)):
                return _printed_color_symbols(explicit, "", "")
            return set().union(*(
                _printed_color_symbols(face.get("colors"), face.get("mana_cost"), face.get("oracle_text"))
                for face in faces if isinstance(face, dict)
            ))
        face = faces[index if isinstance(index, int) and 0 <= index < len(faces) else 0]
        if isinstance(face, dict) and isinstance(face.get("colors"), list):
            return {str(color).upper() for color in face["colors"] if str(color).upper() in _MANA_COLOR_MAP}
    return _printed_color_symbols(getattr(card, "colors", None), getattr(card, "mana_cost", ""), getattr(card, "oracle_text", ""))


def _printed_color_symbols(explicit, mana_cost, oracle_text) -> set[str]:
    if isinstance(explicit, (list, tuple)):
        return {str(color).upper() for color in explicit if str(color).upper() in _MANA_COLOR_MAP}
    if "devoid" in str(oracle_text or "").lower():
        return set()
    mana_cost = str(mana_cost or "").upper()
    return {symbol for cost in re.findall(r"\{([^}]+)\}", mana_cost) for symbol in cost if symbol in _MANA_COLOR_MAP}


def card_color_names(card) -> set[str]:
    return {_MANA_COLOR_MAP[symbol] for symbol in card_color_symbols(card)}
