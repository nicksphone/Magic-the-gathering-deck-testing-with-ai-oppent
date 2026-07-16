from __future__ import annotations

import re


# This intentionally handles ordinary fixed-cost cycling. Variable cycling
# costs need an explicit X choice and card-specific cycling triggers.
_CYCLING_RE = re.compile(r"\bcycling\s+((?:\{[^}]+\})+)", re.IGNORECASE)


def cycling_cost(oracle_text: str, *, allow_variable: bool = False) -> str | None:
    """Return a cycling cost, optionally including a validated X/Y symbol."""
    match = _CYCLING_RE.search(oracle_text or "")
    if not match:
        return None
    cost = match.group(1).upper()
    if not allow_variable and any(symbol in cost for symbol in ("{X}", "{Y}")):
        return None
    return cost


def cycling_is_variable(cost: str) -> bool:
    return any(symbol in (cost or "").upper() for symbol in ("{X}", "{Y}"))
