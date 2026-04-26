from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.continuous import effective_toughness

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"

def apply_state_based_actions(state: MatchState) -> None:
    for pid, player in state.players.items():
        if player.life <= 0:
            state.winner = 1 if pid == 2 else 2
            state.log.append(f"{player.name} has 0 or less life and loses.")

    for cid, card in list(state.cards.items()):
        if (
            "Creature" in card.types
            and card.zone == Zone.BATTLEFIELD
            and card.toughness is not None
            and (
                effective_toughness(state, cid) <= 0
                or int(card.counters.get(DMG_MARK_KEY, 0)) >= int(effective_toughness(state, cid))
                or int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0
            )
        ):
            pstate = state.players[card.controller]
            if cid in pstate.battlefield:
                pstate.battlefield.remove(cid)
                pstate.graveyard.append(cid)
                card.zone = Zone.GRAVEYARD
                state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
        if "Planeswalker" in card.types and card.zone == Zone.BATTLEFIELD and card.loyalty is not None and card.loyalty <= 0:
            pstate = state.players[card.controller]
            if cid in pstate.battlefield:
                pstate.battlefield.remove(cid)
                pstate.graveyard.append(cid)
                card.zone = Zone.GRAVEYARD
                state.log.append(f"State-based action: {card.name} is put into graveyard due to 0 loyalty.")

    _apply_legend_rule(state)


def _apply_legend_rule(state: MatchState) -> None:
    # If a player controls two or more legendary permanents with the same name, keep one and move the rest to graveyard.
    for pid, player in state.players.items():
        legendary_by_name: dict[str, list[str]] = {}
        for cid in player.battlefield:
            card = state.cards[cid]
            if card.zone != Zone.BATTLEFIELD:
                continue
            if not _is_legendary(card):
                continue
            legendary_by_name.setdefault(card.name.lower(), []).append(cid)

        for same_name_ids in legendary_by_name.values():
            if len(same_name_ids) <= 1:
                continue
            keep = same_name_ids[0]
            for cid in same_name_ids:
                if cid == keep:
                    continue
                card = state.cards[cid]
                if cid in player.battlefield:
                    player.battlefield.remove(cid)
                player.graveyard.append(cid)
                card.zone = Zone.GRAVEYARD
                state.log.append(
                    f"State-based action: {state.players[pid].name} keeps one {card.name}; the other is put into graveyard (legend rule)."
                )


def _is_legendary(card) -> bool:
    if any(str(t).lower() == "legendary" for t in getattr(card, "types", [])):
        return True
    if "legendary" in (getattr(card, "type_line", "") or "").lower():
        return True
    # Offline/cache-miss fallback: many legendary permanents in real card names include commas.
    # Restrict heuristic to permanents only to avoid misclassifying instants/sorceries.
    if "," in (getattr(card, "name", "") or "") and any(
        t in getattr(card, "types", [])
        for t in ["Creature", "Planeswalker", "Artifact", "Enchantment", "Land"]
    ):
        return True
    return False
