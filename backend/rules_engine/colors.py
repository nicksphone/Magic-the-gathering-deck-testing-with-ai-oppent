from __future__ import annotations

import re


_MANA_COLOR_MAP = {
    "W": "white",
    "U": "blue",
    "B": "black",
    "R": "red",
    "G": "green",
}


def card_color_names(card) -> set[str]:
    # Prefer explicit color hints when available from card cache.
    explicit = getattr(card, "colors", None)
    if isinstance(explicit, (list, tuple)) and explicit:
        out = set()
        for c in explicit:
            name = _MANA_COLOR_MAP.get(str(c).upper())
            if name:
                out.add(name)
        if out:
            return out

    mana_cost = str(getattr(card, "mana_cost", "") or "").upper()
    out: set[str] = set()
    for sym in re.findall(r"\{([WUBRG])\}", mana_cost):
        name = _MANA_COLOR_MAP.get(sym)
        if name:
            out.add(name)
    return out

