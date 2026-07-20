from __future__ import annotations

from game_state.state import MatchState, Zone
from rules_engine.attachments import attached_to, attachment_target_is_legal, is_aura, is_equipment
from rules_engine.events import emit_event, emit_event_batch
from rules_engine.continuous import effective_toughness, has_keyword
from rules_engine.replacement import replace_die_zone, replacement_options

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


def _human_die_choice_required(state: MatchState, card_id: str) -> bool:
    card = state.cards.get(card_id)
    if not card or not getattr(state, "replacement_choice_required", False):
        return False
    players = set(getattr(state, "replacement_choice_players", set()) or set())
    return not players or card.controller in players


def _move_lethal_creature(state: MatchState, card_id: str, replacement_source_id: str | None = None) -> None:
    card = state.cards.get(card_id)
    if not card or card.zone != Zone.BATTLEFIELD:
        return
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if card_id not in battlefield_owner.battlefield:
        return
    emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
    battlefield_owner.battlefield.remove(card_id)
    destination = replace_die_zone(state, card.controller, card_id, replacement_source_id)
    if destination == "exile":
        zone_owner.exile.append(card_id)
        card.zone = Zone.EXILE
        state.log.append(f"State-based action: {card.name} is exiled instead of dying.")
        return
    zone_owner.graveyard.append(card_id)
    card.zone = Zone.GRAVEYARD
    state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def resume_state_based_die_replacement(state: MatchState, card_id: str, replacement_source_id: str) -> None:
    """Resume a paused lethal-creature zone change after a human choice."""
    _move_lethal_creature(state, card_id, replacement_source_id)


def resume_legend_rule_replacement(
    state: MatchState,
    player_id: int,
    card_id: str,
    replacement_source_id: str,
) -> None:
    """Resume the zone change for the legendary permanent the player chose to keep out."""
    card = state.cards.get(card_id)
    if not card or card.zone != Zone.BATTLEFIELD:
        return
    player = state.players[player_id]
    owner = state.players[getattr(card, "owner", card.controller)]
    if card_id in player.battlefield:
        emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
        player.battlefield.remove(card_id)
    destination = replace_die_zone(state, card.controller, card_id, replacement_source_id)
    if destination == "exile":
        owner.exile.append(card_id)
        card.zone = Zone.EXILE
        state.log.append(
            f"State-based action: {state.players[player_id].name} keeps one {card.name}; the other is exiled by a replacement effect (legend rule)."
        )
        return
    owner.graveyard.append(card_id)
    card.zone = Zone.GRAVEYARD
    state.log.append(
        f"State-based action: {state.players[player_id].name} keeps one {card.name}; the other is put into graveyard (legend rule)."
    )
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    if "Creature" in card.types:
        emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def _resolve_lethal_creature_batch(state: MatchState, card_ids: list[str]) -> None:
    """Move simultaneous lethal creatures together before collecting their triggers."""
    valid_ids = [
        cid
        for cid in card_ids
        if cid in state.cards
        and state.cards[cid].zone == Zone.BATTLEFIELD
        and cid in state.players[state.cards[cid].controller].battlefield
    ]
    if not valid_ids:
        return
    leave_events = [
        {"card_id": cid, "controller": state.cards[cid].controller}
        for cid in valid_ids
    ]
    emit_event_batch(state, "leaves_battlefield", leave_events)
    for cid in valid_ids:
        card = state.cards[cid]
        state.players[card.controller].battlefield.remove(cid)

    death_events: list[dict] = []
    creature_death_events: list[dict] = []
    for cid in valid_ids:
        card = state.cards[cid]
        owner = state.players[getattr(card, "owner", card.controller)]
        destination = replace_die_zone(state, card.controller, cid)
        if destination == "exile":
            owner.exile.append(cid)
            card.zone = Zone.EXILE
            state.log.append(f"State-based action: {card.name} is exiled instead of dying.")
            continue
        owner.graveyard.append(cid)
        card.zone = Zone.GRAVEYARD
        state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
        event = {"card_id": cid, "controller": card.controller}
        death_events.append(event)
        creature_death_events.append(event)
    emit_event_batch(state, "permanent_dies", death_events)
    emit_event_batch(state, "creature_dies", creature_death_events)

def apply_state_based_actions(state: MatchState) -> None:
    for pid, player in state.players.items():
        if player.life <= 0:
            state.winner = 1 if pid == 2 else 2
            state.log.append(f"{player.name} has 0 or less life and loses.")

    lethal_ids: list[str] = []
    for cid, card in list(state.cards.items()):
        if "Creature" in card.types and card.zone == Zone.BATTLEFIELD and card.toughness is not None:
            lethal_from_zero_toughness = effective_toughness(state, cid) <= 0
            indestructible = has_keyword(state, cid, "indestructible")
            lethal_from_damage = int(card.counters.get(DMG_MARK_KEY, 0)) >= int(effective_toughness(state, cid))
            lethal_from_deathtouch = int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0
            if lethal_from_zero_toughness or (not indestructible and (lethal_from_damage or lethal_from_deathtouch)):
                options = replacement_options(state, "die_zone", target_card_id=cid)
                if _human_die_choice_required(state, cid) and len(options) > 1:
                    state.pending_replacement_choice = {
                        "resume_kind": "state_based_die",
                        "player_id": card.controller,
                        "event": "die_zone",
                        "target_card_id": cid,
                        "options": options,
                    }
                    state.priority_player = card.controller
                    state.passed_priority = set()
                    state.log.append(
                        f"Replacement choice required for lethal state-based action; {state.players[card.controller].name} must choose one of {len(options)} effects."
                    )
                    return
                lethal_ids.append(cid)
    if lethal_ids:
        _resolve_lethal_creature_batch(state, lethal_ids)

    for cid, card in list(state.cards.items()):
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
    _apply_saga_state_actions(state)
    _apply_attachment_state_checks(state)


def _apply_saga_state_actions(state: MatchState) -> None:
    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD or "Saga" not in (card.type_line or ""):
            continue
        chapters = [int(item) for item in _saga_chapter_numbers(card.oracle_text)]
        if not chapters or int(card.counters.get("__lore", 0) or 0) < max(chapters):
            continue
        if any(item.source_card_id == cid for item in state.stack):
            continue
        battlefield = state.players[card.controller]
        owner = state.players[getattr(card, "owner", card.controller)]
        if cid not in battlefield.battlefield:
            continue
        emit_event(state, "leaves_battlefield", {"card_id": cid, "controller": card.controller})
        battlefield.battlefield.remove(cid)
        owner.graveyard.append(cid)
        card.zone = Zone.GRAVEYARD
        state.log.append(f"State-based action: {card.name} is sacrificed after its final chapter.")


def _saga_chapter_numbers(oracle_text: str) -> list[int]:
    from rules_engine.oracle_effects import extract_saga_chapters

    return [int(item["number"]) for item in extract_saga_chapters(oracle_text)]


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
                options = replacement_options(state, "die_zone", target_card_id=cid)
                choice_players = set(getattr(state, "replacement_choice_players", set()) or set())
                human_choice = getattr(state, "replacement_choice_required", False) and (
                    not choice_players or card.controller in choice_players
                )
                if human_choice and len(options) > 1:
                    state.pending_replacement_choice = {
                        "resume_kind": "legend_die",
                        "player_id": card.controller,
                        "event": "die_zone",
                        "target_card_id": cid,
                        "legend_player_id": pid,
                        "options": options,
                    }
                    state.priority_player = card.controller
                    state.passed_priority = set()
                    state.log.append(
                        f"Replacement choice required for legend rule; {state.players[card.controller].name} must choose one of {len(options)} effects."
                    )
                    return
                resume_legend_rule_replacement(state, pid, cid, "")


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
