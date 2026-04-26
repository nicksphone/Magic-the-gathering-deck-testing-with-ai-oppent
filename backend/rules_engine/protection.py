from __future__ import annotations

import re

from rules_engine.colors import card_color_names
from rules_engine.continuous import effective_keywords


_TYPE_PROTECTION_MAP = {
    "artifact": "Artifact",
    "artifacts": "Artifact",
    "creature": "Creature",
    "creatures": "Creature",
    "enchantment": "Enchantment",
    "enchantments": "Enchantment",
    "instant": "Instant",
    "instants": "Instant",
    "sorcery": "Sorcery",
    "sorceries": "Sorcery",
    "planeswalker": "Planeswalker",
    "planeswalkers": "Planeswalker",
}
_COLOR_TOKENS = {"white", "blue", "black", "red", "green"}


def protected_from_source(state, target_id: str, source_card) -> bool:
    return protection_match_reason(state, target_id, source_card) is not None


def protection_match_reason(state, target_id: str, source_card) -> str | None:
    protections = _protection_tokens(state, target_id)
    if not protections:
        return None
    if "everything" in protections:
        return "everything"

    source_colors = card_color_names(source_card)
    color_hits = source_colors & protections
    if color_hits:
        return sorted(color_hits)[0]

    if "multicolored" in protections and len(source_colors) >= 2:
        return "multicolored"
    if "monocolored" in protections and len(source_colors) == 1:
        return "monocolored"

    source_types = set(getattr(source_card, "types", []) or [])
    for token, canonical in _TYPE_PROTECTION_MAP.items():
        if token in protections and canonical in source_types:
            return token
    return None


def extract_protection_keywords(oracle_text: str) -> list[str]:
    text = (oracle_text or "").lower()
    out: set[str] = set()
    for clause in re.findall(r"protection from ([^.;,\n]+)", text):
        for raw in re.split(r"\s*(?:,|and|or)\s*", clause):
            token = raw.strip()
            token = token.removeprefix("from ").strip()
            if token in _COLOR_TOKENS or token in _TYPE_PROTECTION_MAP or token in {"monocolored", "multicolored", "everything"}:
                out.add(f"protection from {token}")
    return sorted(out)


def _protection_tokens(state, target_id: str) -> set[str]:
    out: set[str] = set()
    for kw in effective_keywords(state, target_id):
        low = str(kw).lower().strip()
        if not low.startswith("protection from "):
            continue
        token = low.replace("protection from ", "", 1).strip()
        if token:
            out.add(token)
    return out
