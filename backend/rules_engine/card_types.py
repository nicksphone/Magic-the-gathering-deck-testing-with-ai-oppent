from __future__ import annotations

import re
from collections.abc import Mapping


_BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}


def is_land_card(card) -> bool:
    """Use printed types, never a mana ability or a substring in the card name."""
    field = card.get if isinstance(card, Mapping) else lambda name, default=None: getattr(card, name, default)
    types = {str(value).lower() for value in field("types", [])}
    if "land" in types:
        return True
    type_line = str(field("type_line", "") or "").split("//", 1)[0]
    if re.search(r"\bland\b", type_line, re.IGNORECASE):
        return True
    if types or type_line or str(field("mana_cost", "") or "").strip():
        return False
    return str(field("name", "") or "").strip().lower() in _BASIC_LANDS
