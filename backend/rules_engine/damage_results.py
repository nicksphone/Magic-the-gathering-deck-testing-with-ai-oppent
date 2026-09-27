from __future__ import annotations

import re

from rules_engine.continuous import has_keyword


def apply_player_damage(state, player_id: int, amount: int, source_id: str | None, *, combat: bool = False) -> None:
    """Apply consequences of damage after replacements and prevention."""
    if amount <= 0:
        return
    player = state.players[player_id]
    if source_id in state.cards and has_keyword(state, source_id, "infect"):
        player.poison += amount
        state.log.append(f"{player.name} gets {amount} poison counters from infect.")
    else:
        player.life -= amount
    if combat and source_id in state.cards:
        toxic = sum(int(value) for value in re.findall(r"\btoxic\s+(\d+)", state.cards[source_id].oracle_text, re.IGNORECASE))
        if toxic:
            player.poison += toxic
            state.log.append(f"{player.name} gets {toxic} poison counters from toxic.")


def apply_creature_damage(state, card_id: str, amount: int, source_id: str | None) -> None:
    if amount <= 0:
        return
    card = state.cards[card_id]
    counter_damage = source_id in state.cards and any(has_keyword(state, source_id, keyword) for keyword in ("infect", "wither"))
    key = "-1/-1" if counter_damage else "__damage_marked"
    card.counters[key] = int(card.counters.get(key, 0)) + amount
