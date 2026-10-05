from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from game_state.state import MatchState, Zone


BASIC_LAND_TYPES = frozenset({"Plains", "Island", "Swamp", "Mountain", "Forest"})


def basic_land_type_count(state: MatchState, player_id: int) -> int:
    from rules_engine.land_types import effective_type_line
    types: set[str] = set()
    for card_id in state.players[player_id].battlefield:
        card = state.cards[card_id]
        if card.zone != Zone.BATTLEFIELD or card.controller != player_id or "Land" not in effective_types(state, card):
            continue
        subtype_line = re.split(r"\s+[—–-]\s+", effective_type_line(state, card), maxsplit=1)
        if len(subtype_line) == 2:
            types.update(BASIC_LAND_TYPES.intersection(subtype_line[1].split()))
    return len(types)
