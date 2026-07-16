from __future__ import annotations

import re


# Covers ordinary cycling plus keyword variants such as landcycling and
# basic landcycling. Variant cards use the same activation timing but search
# for a card instead of drawing one.
_CYCLING_RE = re.compile(r"\bcycling\s+((?:\{[^}]+\})+)", re.IGNORECASE)
_VARIANT_CYCLING_RE = re.compile(
    r"\b(?P<variant>[a-z][a-z-]*)cycling\s+(?P<cost>(?:\{[^}]+\})+)", re.IGNORECASE
)


def cycling_cost(oracle_text: str, *, allow_variable: bool = False) -> str | None:
    """Return a cycling cost, optionally including a validated X/Y symbol."""
    match = _VARIANT_CYCLING_RE.search(oracle_text or "") or _CYCLING_RE.search(oracle_text or "")
    if not match:
        return None
    cost = (match.group("cost") if "cost" in match.groupdict() else match.group(1)).upper()
    if not allow_variable and any(symbol in cost for symbol in ("{X}", "{Y}")):
        return None
    return cost


def cycling_is_variable(cost: str) -> bool:
    return any(symbol in (cost or "").upper() for symbol in ("{X}", "{Y}"))


def cycling_variant(oracle_text: str) -> str | None:
    """Return a normalized search kind for alternate cycling, if present."""
    text = oracle_text or ""
    match = _VARIANT_CYCLING_RE.search(text)
    if not match:
        return None
    variant = match.group("variant").lower()
    prefix = text[: match.start()].lower()
    if variant == "land":
        return "basic_land" if re.search(r"basic\s+$", prefix) else "land"
    if variant in {"basic-land", "basicland"}:
        return "basic_land"
    return variant
