from __future__ import annotations

import re


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
}


def compute_max_land_plays_this_turn(state, player_id: int) -> int:
    player = state.players[player_id]
    extra = 0
    for cid in player.battlefield:
        card = state.cards.get(cid)
        if not card:
            continue
        text = f"{getattr(card, 'name', '')}\n{getattr(card, 'oracle_text', '')}".lower()
        # Common wording patterns:
        # - "You may play an additional land on each of your turns."
        # - "You may play two additional lands on each of your turns."
        # Keep this parser strict and additive.
        if "play an additional land" in text:
            extra += 1
            continue
        m = re.search(r"play (one|two|three|\d+) additional lands?", text)
        if m:
            token = m.group(1)
            if token.isdigit():
                extra += int(token)
            else:
                extra += _NUMBER_WORDS.get(token, 0)
    return max(1, 1 + extra)

