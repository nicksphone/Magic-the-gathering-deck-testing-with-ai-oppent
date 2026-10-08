from __future__ import annotations

import re


_MANA_COLOR_MAP = {
    "W": "white",
    "U": "blue",
    "B": "black",
    "R": "red",
    "G": "green",
}


def card_color_symbols(card, state=None) -> set[str]:
    from rules_engine.type_effects import active_type_effects
    overlays = [effect for effect in active_type_effects(card) if 'colors' in effect]
    overlay = max(overlays, key=lambda effect: effect['timestamp']) if overlays else None
    attached_color = None
    if state is not None:
        from game_state.state import Zone
        from rules_engine.basic_land_layer import layer_four_view
        from rules_engine.attached_characteristics import effects_on
        compounds = effects_on(state, card.id)
        attached_color = max(compounds, key=lambda effect: (effect.timestamp, effect.source_ref[0])) if compounds else None
        if getattr(card, 'zone', None) == Zone.BATTLEFIELD and card.id in layer_four_view(state)[3]:
            from rules_engine.basic_land_layer import permanent_land_replacement
            replacements = [source for source in state.cards.values()
                            if source.zone == Zone.BATTLEFIELD and source.attached_to == card.id
                            and permanent_land_replacement(source.oracle_text)]
            stamp = max((int(source.effect_timestamp or source.static_order or 0)
                         for source in replacements), default=0)
            if (overlay is None or overlay['timestamp'] <= stamp) and (
                    attached_color is None or attached_color.timestamp <= stamp):
                return set()
    if attached_color is not None and (overlay is None or overlay['timestamp'] <= attached_color.timestamp):
        return set(attached_color.compound.colors)
    if overlay is not None:
        return set(overlay['colors'])
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


def card_color_names(card, state=None) -> set[str]:
    return {_MANA_COLOR_MAP[symbol] for symbol in card_color_symbols(card, state)}
