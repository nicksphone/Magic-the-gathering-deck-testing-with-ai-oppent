from __future__ import annotations

import re


# This intentionally handles ordinary fixed-cost cycling. Variable cycling
# costs need an explicit X choice and card-specific cycling triggers.
_CYCLING_RE = re.compile(r"\bcycling\s+((?:\{[^}]+\})+)", re.IGNORECASE)


def cycling_cost(oracle_text: str) -> str | None:
    """Return a fixed cycling cost, or None for unsupported variants."""
    match = _CYCLING_RE.search(oracle_text or "")
    if not match:
        return None
    cost = match.group(1).upper()
    if any(symbol in cost for symbol in ("{X}", "{Y}")):
        return None
    return cost
