from __future__ import annotations

import re

from rules_engine.continuous import has_keyword
from rules_engine.counter_placement import put_counters
from rules_engine.replacement import player_cant_lose_life


def source_has_keyword(state, source_id: str | None, keyword: str, source_lki: dict | None = None) -> bool:
    if source_lki is not None:
        return keyword in {str(value).lower() for value in source_lki.get("keywords", [])}
    return source_id in state.cards and has_keyword(state, source_id, keyword)


def apply_player_damage(state, player_id: int, amount: int, source_id: str | None, *, combat: bool = False,
                        source_lki: dict | None = None) -> None:
    """Apply consequences of damage after replacements and prevention."""
    if amount <= 0:
        return
    player = state.players[player_id]
    if source_has_keyword(state, source_id, "infect", source_lki):
        placed = put_counters(state, 'poison', amount, target_player=player_id)
        if placed:
            state.log.append(f"{player.name} gets {placed} poison counters from infect.")
    elif not player_cant_lose_life(state, player_id):
        player.life -= amount
    if combat and source_id in state.cards:
        toxic = sum(int(value) for value in re.findall(r"\btoxic\s+(\d+)", state.cards[source_id].oracle_text, re.IGNORECASE))
        if toxic:
            placed = put_counters(state, 'poison', toxic, target_player=player_id)
            if placed:
                state.log.append(f"{player.name} gets {placed} poison counters from toxic.")


def apply_creature_damage(state, card_id: str, amount: int, source_id: str | None,
                          *, source_lki: dict | None = None) -> None:
    if amount <= 0:
        return
    card = state.cards[card_id]
    counter_damage = any(source_has_keyword(state, source_id, keyword, source_lki) for keyword in ("infect", "wither"))
    if counter_damage:
        put_counters(state, '-1/-1', amount, target_card_id=card_id)
    else:
        card.counters['__damage_marked'] = int(card.counters.get('__damage_marked', 0)) + amount
