from __future__ import annotations

import re

from rules_engine.colors import card_color_names
from rules_engine.continuous import effective_keywords


_TYPE_PROTECTION_MAP = {
    "artifact": "Artifact",
    "artifacts": "Artifact",
    "nonartifact": "!Artifact",
    "non-artifact": "!Artifact",
    "creature": "Creature",
    "creatures": "Creature",
    "noncreature": "!Creature",
    "non-creature": "!Creature",
    "enchantment": "Enchantment",
    "enchantments": "Enchantment",
    "nonenchantment": "!Enchantment",
    "non-enchantment": "!Enchantment",
    "instant": "Instant",
    "instants": "Instant",
    "sorcery": "Sorcery",
    "sorceries": "Sorcery",
    "planeswalker": "Planeswalker",
    "planeswalkers": "Planeswalker",
    "land": "Land",
    "lands": "Land",
    "nonland": "!Land",
    "non-land": "!Land",
}
_COLOR_TOKENS = {"white", "blue", "black", "red", "green", "colorless", "multicolored", "monocolored", "everything"}
_HEXPROOF_QUALITY = '(?:' + '|'.join(re.escape(value) for value in sorted(_COLOR_TOKENS | set(_TYPE_PROTECTION_MAP),key=len,reverse=True)) + ')'
HEXPROOF_VARIANT_RE = re.compile(r'\bhexproof from ' + _HEXPROOF_QUALITY + r'(?: and from ' + _HEXPROOF_QUALITY + r')*\b',re.I)


def source_matches_quality(source_card, quality: str) -> bool:
    """Shared supported color/type qualities, not an arbitrary Oracle predicate."""
    if source_card is None:
        return False
    colors = card_color_names(source_card)
    if quality == 'everything' or quality in colors:
        return True
    if quality == 'colorless':
        return not colors
    if quality in {'multicolored', 'monocolored'}:
        return len(colors) >= 2 if quality == 'multicolored' else len(colors) == 1
    kind = _TYPE_PROTECTION_MAP.get(quality)
    types = set(getattr(source_card, 'types', []) or [])
    return (kind[1:] not in types if kind.startswith('!') else kind in types) if kind else False


def hexproof_variants(text: str) -> list[str]:
    """A complete supported variant phrase; never promote a conditional clause."""
    text = text.strip().lower().rstrip('.')
    if not text.startswith('hexproof from '):
        return []
    qualities = text.removeprefix('hexproof from ').split(' and from ')
    if any(quality not in _COLOR_TOKENS and quality not in _TYPE_PROTECTION_MAP for quality in qualities):
        return []
    return [f'hexproof from {quality}' for quality in qualities]


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
        if token in protections:
            if canonical.startswith("!"):
                blocked = canonical[1:]
                if blocked not in source_types:
                    return token
            elif canonical in source_types:
                return token
    if "colorless" in protections and not source_colors:
        return "colorless"
    return None


def extract_protection_keywords(oracle_text: str) -> list[str]:
    text = (oracle_text or "").lower()
    out: set[str] = set()
    for clause in re.findall(r"protection from ([^.;,\n]+)", text):
        for raw in re.split(r"\s*(?:,|and|or)\s*", clause):
            token = raw.strip()
            token = token.removeprefix("from ").strip()
            if token in _COLOR_TOKENS or token in _TYPE_PROTECTION_MAP:
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
