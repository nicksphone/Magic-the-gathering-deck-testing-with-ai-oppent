from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.attachments import attached_to, attachment_target_is_legal, is_aura, is_equipment
from rules_engine.events import emit_event
from rules_engine.continuous import effective_toughness, has_keyword
from rules_engine.replacement import replace_die_zone

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"

def apply_state_based_actions(state: MatchState) -> None:
    for pid, player in state.players.items():
        if player.life <= 0:
            state.winner = 1 if pid == 2 else 2
            state.log.append(f"{player.name} has 0 or less life and loses.")

    for cid, card in list(state.cards.items()):
        if "Creature" in card.types and card.zone == Zone.BATTLEFIELD and card.toughness is not None:
            lethal_from_zero_toughness = effective_toughness(state, cid) <= 0
            indestructible = has_keyword(state, cid, "indestructible")
            lethal_from_damage = int(card.counters.get(DMG_MARK_KEY, 0)) >= int(effective_toughness(state, cid))
            lethal_from_deathtouch = int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0
            if lethal_from_zero_toughness or (not indestructible and (lethal_from_damage or lethal_from_deathtouch)):
                battlefield_owner = state.players[card.controller]
                zone_owner = state.players[getattr(card, "owner", card.controller)]
                if cid in battlefield_owner.battlefield:
                    emit_event(state, "leaves_battlefield", {"card_id": cid, "controller": card.controller})
                    battlefield_owner.battlefield.remove(cid)
                    destination = replace_die_zone(state, card.controller, cid)
                    if destination == "exile":
                        zone_owner.exile.append(cid)
                        card.zone = Zone.EXILE
                        state.log.append(f"State-based action: {card.name} is exiled instead of dying.")
                    else:
                        zone_owner.graveyard.append(cid)
                        card.zone = Zone.GRAVEYARD
                        state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
                        emit_event(state, "permanent_dies", {"card_id": cid, "controller": card.controller})
                        emit_event(state, "creature_dies", {"card_id": cid, "controller": card.controller})
        if "Planeswalker" in card.types and card.zone == Zone.BATTLEFIELD and card.loyalty is not None and card.loyalty <= 0:
            battlefield_owner = state.players[card.controller]
            zone_owner = state.players[getattr(card, "owner", card.controller)]
            if cid in battlefield_owner.battlefield:
                emit_event(state, "leaves_battlefield", {"card_id": cid, "controller": card.controller})
                battlefield_owner.battlefield.remove(cid)
                zone_owner.graveyard.append(cid)
                card.zone = Zone.GRAVEYARD
                state.log.append(f"State-based action: {card.name} is put into graveyard due to 0 loyalty.")
                emit_event(state, "permanent_dies", {"card_id": cid, "controller": card.controller})

    _apply_legend_rule(state)
    _apply_attachment_state_checks(state)


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
                zone_owner = state.players[getattr(card, "owner", card.controller)]
                if cid in player.battlefield:
                    player.battlefield.remove(cid)
                zone_owner.graveyard.append(cid)
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


def _apply_attachment_state_checks(state: MatchState) -> None:
    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD:
            continue
        if not (is_aura(card) or is_equipment(card)):
            continue
        target_id = attached_to(card)
        if not target_id:
            if is_aura(card):
                owner = state.players[card.controller]
                if cid in owner.battlefield:
                    owner.battlefield.remove(cid)
                    owner.graveyard.append(cid)
                    card.zone = Zone.GRAVEYARD
                    state.log.append(f"State-based action: {card.name} has no legal attachment and is put into graveyard.")
            continue
        target = state.cards.get(target_id)
        if not attachment_target_is_legal(state, card, target_id):
            if is_aura(card):
                owner = state.players[card.controller]
                if cid in owner.battlefield:
                    owner.battlefield.remove(cid)
                    owner.graveyard.append(cid)
                    card.zone = Zone.GRAVEYARD
                    state.log.append(f"State-based action: {card.name} loses attachment and is put into graveyard.")
            elif is_equipment(card):
                card.attached_to = None
                state.log.append(f"State-based action: {card.name} becomes unattached.")
