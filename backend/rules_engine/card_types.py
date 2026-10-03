from __future__ import annotations

import re
import json
from pathlib import Path
from collections.abc import Mapping


_BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}
CARD_TYPES = frozenset({"Artifact", "Battle", "Creature", "Enchantment", "Instant", "Kindred", "Land", "Planeswalker", "Sorcery"})
CREATURE_SUBTYPES = frozenset(json.loads(Path(__file__).with_name("creature_subtypes.json").read_text())["types"])


def creature_subtype_candidates(plural: str) -> set[str]:
    word = str(plural or "").lower()
    if word.endswith("ves"):
        return {word[:-3] + "f"}
    if word.endswith("ies"):
        return {word[:-3] + "y", word[:-1]}
    return {word[:-1]} if word.endswith("s") else {word}


def printed_card_types(type_line: str) -> list[str]:
    """Read the front face's types, excluding supertypes and subtypes."""
    front = re.split(r'\s[\u2014-]\s', (type_line or "").split("//", 1)[0], maxsplit=1)[0].strip()
    return [part.capitalize() for part in front.split() if part.capitalize() in CARD_TYPES]


def cards_have_distinct_card_types(state, card_ids: list[str]) -> bool:
    """Each selected card must be assignable a different printed card type."""
    assigned: dict[str, str] = {}

    def assign(card_id: str, visited: set[str]) -> bool:
        card = state.cards.get(card_id)
        if card is None:
            return False
        for card_type in sorted(set(card.types) & CARD_TYPES):
            if card_type in visited:
                continue
            visited.add(card_type)
            if card_type not in assigned or assign(assigned[card_type], visited):
                assigned[card_type] = card_id
                return True
        return False

    return len(card_ids) == len(set(card_ids)) and all(assign(card_id, set()) for card_id in card_ids)


def is_token_card(card) -> bool:
    field = card.get if isinstance(card, Mapping) else lambda name, default=None: getattr(card, name, default)
    return bool(field("is_token", False)) or "token" in {str(value).lower() for value in (field("types", []) or [])}


def graveyard_card_types(state, player_ids):
    """Normal card types, not supertypes/subtypes or transient graveyard tokens."""
    return {kind for pid in player_ids for cid in state.players[pid].graveyard
            for card in [state.cards.get(cid)] if card is not None and not is_token_card(card)
            for kind in card.types if kind in CARD_TYPES}


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
