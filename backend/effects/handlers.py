from __future__ import annotations

import copy
import re

from game_state.state import MatchState, Zone, assign_static_order_on_battlefield_entry, draw_card
from card_data.token_images import resolve_token_image_uri
from rules_engine.continuous import effective_keywords, effective_toughness, has_keyword
from rules_engine.entry import apply_entry_choice, pause_for_land_entries
from rules_engine.colors import card_color_names
from rules_engine.hooks import apply_replacement_effects
from rules_engine.events import capture_last_known_battlefield, emit_event, emit_event_batch, was_creature_on_battlefield
from rules_engine.mana import mana_value, parse_mana_cost
from rules_engine.prevention import (
    add_card_prevention_shield,
    add_player_prevention_shield,
    consume_card_prevention_shield,
    consume_player_prevention_shield,
)
from rules_engine.replacement import (
    apply_damage_replacements,
    apply_permanent_damage_replacements,
    damage_cant_be_prevented,
    player_cant_gain_life,
    player_cant_lose_life,
    replacement_options,
    replacement_source_used,
    replace_die_zone,
    replace_draw_cards,
    replace_gain_life,
    replace_noncombat_damage_to_creature,
)
from rules_engine.zone_actions import exile_flashback_spell, is_departed_token, put_into_graveyard


def _queue_human_damage_replacement_choice(
    state: MatchState,
    controller: int,
    payload: dict,
    remaining_amount: int,
    selected_source_id: str | None,
) -> bool:
    """Pause a human damage chain when the modified event remains replaceable."""
    if remaining_amount <= 0 or not selected_source_id:
        return False
    if not getattr(state, "replacement_choice_required", False):
        return False
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    affected_player = int(target_player) if target_player is not None else None
    if target_card_id in state.cards:
        affected_player = int(state.cards[target_card_id].controller)
    human_players = set(getattr(state, "replacement_choice_players", set()) or set())
    if affected_player is None or (human_players and affected_player not in human_players):
        return False
    event = "damage_to_player" if target_player is not None else "damage_to_permanent"
    options = replacement_options(
        state,
        event,
        target_player=affected_player if target_player is not None else None,
        target_card_id=str(target_card_id) if target_card_id else None,
    )
    used_source_ids = [str(value) for value in (payload.get("__used_replacement_source_ids") or [])]
    if str(selected_source_id) not in used_source_ids:
        used_source_ids.append(str(selected_source_id))
    options = [option for option in options if str(option.get("source_id")) not in set(used_source_ids)]
    if not options:
        return False
    state.pending_replacement_choice = {
        "resume_kind": "damage_chain",
        "player_id": affected_player,
        "event": event,
        "target_player": int(target_player) if target_player is not None else None,
        "target_card_id": str(target_card_id) if target_card_id else None,
        "amount": int(remaining_amount),
        "controller": int(controller),
        "source_card_id": payload.get("__source_card_id"),
        "source_lki": payload.get("__source_lki"),
        "selected_source_ids": used_source_ids,
        "batch_damage": bool(payload.get("__batch_damage")),
        "options": options,
    }
    state.priority_player = affected_player
    state.passed_priority = set()
    state.log.append(
        f"Replacement choice required for remaining {event}; {state.players[affected_player].name} must choose one of {len(options)} effects."
    )
    return True

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


def noop(state: MatchState, controller: int, payload: dict) -> None:
    del state, controller, payload


def set_turn_restriction(state: MatchState, controller: int, payload: dict) -> None:
    """Apply a spell-created restriction until the active turn's cleanup."""
    kind = str(payload.get("kind", "") or "").lower()
    if kind == "cant_gain_life":
        if payload.get("all_players"):
            state.turn_cant_gain_life.update(state.players.keys())
        else:
            players = payload.get("players") or [controller]
            state.turn_cant_gain_life.update(int(pid) for pid in players if int(pid) in state.players)
        state.log.append("Players cannot gain life for the rest of this turn." if payload.get("all_players") else "Life gain is prohibited for the affected players this turn.")
    elif kind == "damage_cant_be_prevented":
        state.turn_damage_cant_be_prevented = True
        state.log.append("Damage cannot be prevented for the rest of this turn.")


def _creature_is_lethally_damaged(state: MatchState, card_id: str) -> bool:
    card = state.cards[card_id]
    if card.toughness is None:
        return False
    if has_keyword(state, card_id, "indestructible"):
        return False
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    if marked >= int(effective_toughness(state, card_id)):
        return True
    if int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0:
        return True
    return False


def _move_creature_to_graveyard(state: MatchState, card_id: str) -> None:
    card = state.cards[card_id]
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if card_id in battlefield_owner.battlefield:
        destination = replace_die_zone(state, card.controller, card_id)
        emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
        battlefield_owner.battlefield.remove(card_id)
        if destination == "exile":
            zone_owner.exile.append(card_id)
            card.move_to_zone(Zone.EXILE)
            state.log.append(f"{card.name} is exiled instead of dying.")
        else:
            zone_owner.graveyard.append(card_id)
            card.zone = Zone.GRAVEYARD
            state.log.append(f"{card.name} dies.")
            emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
            emit_event(state, "creature_dies", {"card_id": card_id, "controller": card.controller})


def deal_damage(state: MatchState, controller: int, payload: dict) -> int:
    payload = apply_replacement_effects("damage", dict(payload))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    amount = int(payload.get("amount", 0))
    source_card_id = payload.get("__source_card_id")
    source_lki = payload.get("__source_lki")
    selected_source_id = payload.get("__replacement_source_id")
    human_chain = bool(selected_source_id and getattr(state, "replacement_choice_required", False))
    prevention_locked = damage_cant_be_prevented(
        state,
        source_card_id=source_card_id,
        target_player=int(target_player) if target_player is not None else None,
        target_card_id=target_card_id,
    )
    source_colors: set[str] = set()
    if source_lki is not None:
        source_colors = set(source_lki.get("color_names", []))
    elif source_card_id in state.cards:
        source_colors = card_color_names(state.cards[source_card_id])
    if target_card_id is not None and target_card_id in state.cards:
        card = state.cards[target_card_id]
        kws = effective_keywords(state, target_card_id)
        for color in source_colors:
            if f"protection from {color}" in kws:
                state.log.append(f"{card.name} prevents damage from {color} source due to protection.")
                return 0
        if (card.toughness is not None or "Planeswalker" in card.types) and amount > 0:
            if replace_noncombat_damage_to_creature(state, source_card_id, target_card_id, amount) is not None:
                if not payload.get("__defer_lethal") and "Creature" in card.types and _creature_is_lethally_damaged(state, target_card_id):
                    _move_creature_to_graveyard(state, target_card_id)
                return 0
            replaced_amount = amount if prevention_locked else apply_permanent_damage_replacements(
                state,
                target_card_id,
                amount,
                replacement_source_id=selected_source_id,
                max_replacements=1 if human_chain else None,
            )
            if not prevention_locked and human_chain and _queue_human_damage_replacement_choice(state, controller, payload, replaced_amount, selected_source_id):
                return 0
            post, prevented = (replaced_amount, 0) if prevention_locked else consume_card_prevention_shield(card, replaced_amount)
            if prevented > 0:
                state.log.append(f"{card.name} prevents {prevented} damage.")
            if post <= 0:
                return 0
            from rules_engine.damage_results import apply_creature_damage
            if card.toughness is not None:
                apply_creature_damage(state, target_card_id, int(post), source_card_id, source_lki=source_lki)
                state.log.append(f"{card.name} takes {post} damage.")
            if "Planeswalker" in card.types and card.loyalty is not None:
                card.loyalty -= int(post)
                state.log.append(f"{card.name} loses {post} loyalty.")
            if not payload.get("__batch_damage"):
                _gain_lifelink_from_damage(state, source_card_id, int(post), source_lki)
            # Check for lethal damage — creatures die state-based, not just at combat cleanup.
            if not payload.get("__defer_lethal") and "Creature" in card.types and _creature_is_lethally_damaged(state, target_card_id):
                _move_creature_to_graveyard(state, target_card_id)
            return int(post)
    if target_player is not None:
        replaced_amount = amount if prevention_locked else apply_damage_replacements(
            state,
            int(target_player),
            amount,
            replacement_source_id=selected_source_id,
            max_replacements=1 if human_chain else None,
        )
        if not prevention_locked and human_chain and _queue_human_damage_replacement_choice(state, controller, payload, replaced_amount, selected_source_id):
            return 0
        post, prevented = (replaced_amount, 0) if prevention_locked else consume_player_prevention_shield(state, int(target_player), replaced_amount)
        if prevented > 0:
            state.log.append(f"{state.players[target_player].name} prevents {prevented} damage.")
        if post <= 0:
            return 0
        from rules_engine.damage_results import apply_player_damage
        apply_player_damage(state, int(target_player), int(post), source_card_id, source_lki=source_lki)
        state.log.append(f"{state.players[target_player].name} takes {post} damage.")
        if not payload.get("__batch_damage"):
            _gain_lifelink_from_damage(state, source_card_id, int(post), source_lki)
        return int(post)
    return 0


def _gain_lifelink_from_damage(state: MatchState, source_id: str | None, amount: int,
                               source_lki: dict | None = None) -> None:
    from rules_engine.damage_results import source_has_keyword
    if amount > 0 and source_has_keyword(state, source_id, "lifelink", source_lki):
        source_controller = int(source_lki["controller"]) if source_lki is not None else state.cards[source_id].controller
        gain_life(state, source_controller, {
            "target_player": source_controller, "amount": amount, "__source_card_id": source_id,
        })


def draw_cards(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import draw_card
    from rules_engine.draw_restrictions import can_draw_card

    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("amount", 1))
    if amount <= 0:
        return
    if amount > 1:
        for index in range(amount):
            single = {**payload, "amount": 1}
            if index:
                single.pop("__replacement_source_id", None)
                single.pop("__skip_dredge_choice", None)
            draw_cards(state, controller, single)
            if target_player in state.failed_draw_players:
                return
            pending = state.pending_mechanic_choice or state.pending_replacement_choice
            if pending:
                remaining = amount - index - 1
                if remaining:
                    rest = {**payload, "amount": remaining}
                    rest.pop("__replacement_source_id", None)
                    rest.pop("__skip_dredge_choice", None)
                    pending.setdefault("draw_continuation_queue", []).append(rest)
                return
            if state.winner is not None:
                return
        return
    if not can_draw_card(state, target_player):
        state.log.append(f"{state.players[target_player].name} cannot draw another card this turn.")
        return
    selected_source_id = payload.get("__replacement_source_id")
    if (not selected_source_id and state.replacement_choice_required
            and target_player in state.replacement_choice_players):
        options = replacement_options(state, "card_draw", target_player=target_player)
        used = {str(value) for value in (payload.get("__used_replacement_source_ids") or [])}
        options = [
            option for option in options
            if not replacement_source_used(used, "card_draw", str(option["source_id"]))
        ]
        if len(options) > 1:
            state.pending_replacement_choice = {
                "resume_kind": "draw_event", "player_id": target_player,
                "controller": controller, "draw_payload": dict(payload),
                "options": options, "event": "card_draw",
            }
            state.priority_player = target_player
            state.passed_priority = set()
            return
    from rules_engine.dredge import offer_dredge_choice
    if offer_dredge_choice(state, controller, payload):
        return
    used_source_ids = [str(value) for value in (payload.get("__used_replacement_source_ids") or [])]
    replaced = replace_draw_cards(
        state,
        target_player,
        amount,
        replacement_source_id=selected_source_id,
        used_source_ids=used_source_ids,
    )
    if replaced is not None:
        key, repl_payload = replaced
        source = repl_payload.pop("__replacement_source", None)
        state.log.append(
            f"Replacement effect applied: draw_cards -> {key} for {state.players[target_player].name}."
            + (f" Source: {source}." if source else "")
        )
        from effects.registry import resolve_effect
        resolve_effect(state, controller, key, repl_payload)
        return
    before = len(state.players[target_player].hand)
    draw_card(state, target_player, amount)
    drawn = len(state.players[target_player].hand) - before
    if drawn:
        state.log.append(f"{state.players[target_player].name} draws {drawn}.")


def cycle_draw(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve the draw portion of a fixed-cost cycling ability."""
    # Cycling's draw is still a normal draw event, so replacement effects and
    # draw triggers must use the same path as every other draw effect.
    draw_cards(state, controller, {"target_player": controller, "amount": int(payload.get("amount", 1) or 1)})


def cycle_search(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve an alternate-cycling search and shuffle the remaining library."""
    search_library(state, controller, {**payload, "destination": "hand"})
    state.rng.shuffle(state.players[controller].library)


def gain_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    amount = int(payload.get("snow_mana_spent", 0) if payload.get("amount_source") == "snow_mana_spent" else payload.get("amount", 0))
    if amount <= 0:
        return
    if player_cant_gain_life(state, target_player):
        state.log.append(f"{state.players[target_player].name} can't gain life.")
        return
    used_source_ids = [str(value) for value in (payload.get("__used_replacement_source_ids") or [])]
    selected_source_id = payload.get("__replacement_source_id")
    if not selected_source_id and state.replacement_choice_required and target_player in state.replacement_choice_players:
        used = set(used_source_ids)
        options = [
            option for option in replacement_options(state, "life_gain", target_player=target_player)
            if not replacement_source_used(used, "life_gain", str(option["source_id"]))
        ]
        if len(options) > 1:
            state.pending_replacement_choice = {
                "resume_kind": "gain_event", "player_id": target_player,
                "controller": controller, "gain_payload": dict(payload),
                "options": options, "event": "life_gain",
            }
            state.priority_player = target_player
            state.passed_priority = set()
            return
    replaced = replace_gain_life(
        state,
        target_player,
        amount,
        replacement_source_id=selected_source_id,
        used_source_ids=used_source_ids,
    )
    if replaced is not None:
        key, repl_payload = replaced
        if payload.get("__source_card_id"):
            repl_payload["__source_card_id"] = payload["__source_card_id"]
        source = repl_payload.pop("__replacement_source", None)
        state.log.append(
            f"Replacement effect applied: gain_life -> {key} for {state.players[target_player].name}."
            + (f" Source: {source}." if source else "")
        )
        from effects.registry import resolve_effect
        resolve_effect(state, controller, key, repl_payload)
        return
    state.players[target_player].life += amount
    state.log.append(f"{state.players[target_player].name} gains {amount} life.")
    if amount > 0:
        emit_event(state, "life_gain", {"player_id": target_player, "amount": amount, "source_card_id": payload.get("__source_card_id")})


def lose_life(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", controller))
    if payload.get("count_type"):
        amount = _count_controlled_type(state, int(payload.get("count_controller", controller)), str(payload["count_type"]))
    else:
        amount = int(payload.get("amount", 0))
    if amount <= 0:
        return
    if player_cant_lose_life(state, target_player):
        state.log.append(f"{state.players[target_player].name} can't lose life.")
        return
    state.players[target_player].life -= amount
    state.log.append(f"{state.players[target_player].name} loses {amount} life.")


def _count_controlled_type(state: MatchState, controller: int, type_name: str) -> int:
    needle = str(type_name or "").lower()
    if needle.endswith("ves"):
        needle = needle[:-3] + "f"
    elif needle.endswith("ies"):
        needle = needle[:-3] + "y"
    else:
        needle = needle.rstrip("s")
    count = 0
    for cid in state.players[controller].battlefield:
        card = state.cards[cid]
        types = {str(value).lower().rstrip("s") for value in (getattr(card, "types", []) or [])}
        type_line = str(getattr(card, "type_line", "") or "").lower()
        if needle in types or needle in type_line.split():
            count += 1
    return count


def destroy_permanent(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if target in battlefield_owner.battlefield:
        destination = replace_die_zone(state, card.controller, target, payload.get("__replacement_source_id"))
        emit_event(state, "leaves_battlefield", {"card_id": target, "controller": card.controller})
        battlefield_owner.battlefield.remove(target)
        if destination == "exile":
            zone_owner.exile.append(target)
            card.move_to_zone(Zone.EXILE)
            state.log.append(f"{card.name} is exiled instead of dying.")
            return
        zone_owner.graveyard.append(target)
        card.zone = Zone.GRAVEYARD
        state.log.append(f"{card.name} is destroyed.")
        emit_event(state, "permanent_dies", {"card_id": target, "controller": card.controller})
        if was_creature_on_battlefield(card):
            emit_event(state, "creature_dies", {"card_id": target, "controller": card.controller})


def change_control(state: MatchState, controller: int, payload: dict) -> None:
    target_id = payload.get("target_card_id")
    card = state.cards.get(target_id) if target_id else None
    if card is None or card.zone != Zone.BATTLEFIELD:
        return
    new_controller = int(payload.get("new_controller", controller) or controller)
    if new_controller not in state.players:
        return
    old_controller = int(card.controller)
    if old_controller != new_controller:
        old_battlefield = state.players[old_controller].battlefield
        if target_id in old_battlefield:
            old_battlefield.remove(target_id)
        state.players[new_controller].battlefield.append(target_id)
        card.controller = new_controller
    if payload.get("until_end_of_turn"):
        state.temporary_control_changes[target_id] = {
            "controller": old_controller,
            "expires_turn": int(state.turn),
        }
    state.log.append(f"{state.players[new_controller].name} gains control of {card.name}.")
def destroy_all_creatures(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    destroyed = False
    leaves: list[dict] = []
    permanent_deaths: list[dict] = []
    creature_deaths: list[dict] = []
    destinations = {
        cid: replace_die_zone(state, card.controller, cid)
        for cid, card in state.cards.items()
        if "Creature" in card.types and cid in state.players[card.controller].battlefield
    }
    for cid in destinations:
        capture_last_known_battlefield(state, cid)
    for cid, card in list(state.cards.items()):
        if "Creature" not in card.types:
            continue
        battlefield_owner = state.players[card.controller]
        zone_owner = state.players[getattr(card, "owner", card.controller)]
        if cid in battlefield_owner.battlefield:
            event_payload = {"card_id": cid, "controller": card.controller}
            leaves.append(event_payload)
            battlefield_owner.battlefield.remove(cid)
            destination = destinations[cid]
            if destination == "exile":
                zone_owner.exile.append(cid)
                card.zone = Zone.EXILE
                state.log.append(f"{card.name} is exiled instead of dying.")
                destroyed = True
                continue
            zone_owner.graveyard.append(cid)
            card.zone = Zone.GRAVEYARD
            destroyed = True
            state.log.append(f"{card.name} is destroyed.")
            permanent_deaths.append(event_payload)
            creature_deaths.append(event_payload)
    emit_event_batch(state, "leaves_battlefield", leaves)
    emit_event_batch(state, "permanent_dies", permanent_deaths)
    emit_event_batch(state, "creature_dies", creature_deaths)
    if destroyed:
        state.log.append("All creatures are destroyed.")


def _destroy_all_permanents_of_types(state: MatchState, allowed_types: set[str], log_label: str) -> None:
    destroyed = False
    leaves: list[dict] = []
    permanent_deaths: list[dict] = []
    creature_deaths: list[dict] = []
    destinations = {
        cid: replace_die_zone(state, card.controller, cid)
        for cid, card in state.cards.items()
        if allowed_types.intersection(set(card.types or [])) and cid in state.players[card.controller].battlefield
    }
    for cid in destinations:
        capture_last_known_battlefield(state, cid)
    for cid, card in list(state.cards.items()):
        if not allowed_types.intersection(set(card.types or [])):
            continue
        battlefield_owner = state.players[card.controller]
        zone_owner = state.players[getattr(card, "owner", card.controller)]
        if cid in battlefield_owner.battlefield:
            event_payload = {"card_id": cid, "controller": card.controller}
            leaves.append(event_payload)
            battlefield_owner.battlefield.remove(cid)
            destination = destinations[cid]
            if destination == "exile":
                zone_owner.exile.append(cid)
                card.zone = Zone.EXILE
                destroyed = True
                state.log.append(f"{card.name} is exiled instead of dying.")
                continue
            zone_owner.graveyard.append(cid)
            card.zone = Zone.GRAVEYARD
            destroyed = True
            state.log.append(f"{card.name} is destroyed.")
            permanent_deaths.append(event_payload)
            if "Creature" in card.types:
                creature_deaths.append(event_payload)
    emit_event_batch(state, "leaves_battlefield", leaves)
    emit_event_batch(state, "permanent_dies", permanent_deaths)
    emit_event_batch(state, "creature_dies", creature_deaths)
    if destroyed:
        state.log.append(log_label)


def exile_all_graveyards(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    for player in state.players.values():
        for cid in list(player.graveyard):
            if is_departed_token(state.cards[cid]):
                continue
            player.graveyard.remove(cid)
            state.players[state.cards[cid].owner].exile.append(cid)
            state.cards[cid].move_to_zone(Zone.EXILE)
    state.log.append("All graveyards are exiled.")


def exile_all_creatures(state: MatchState, controller: int, payload: dict) -> int:
    """Exile every creature, preserving ownership and leave events."""
    moved = 0
    leaves: list[dict] = []
    for player in state.players.values():
        for cid in player.battlefield:
            if "Creature" in state.cards[cid].types:
                capture_last_known_battlefield(state, cid)
    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD or "Creature" not in card.types:
            continue
        battlefield = state.players[card.controller]
        owner = state.players[getattr(card, "owner", card.controller)]
        if cid not in battlefield.battlefield:
            continue
        leaves.append({"card_id": cid, "controller": card.controller})
        battlefield.battlefield.remove(cid)
        owner.exile.append(cid)
        card.zone = Zone.EXILE
        moved += 1
    emit_event_batch(state, "leaves_battlefield", leaves)
    state.log.append(f"Exile all creatures resolves: {moved} creature(s) exiled.")
    return moved


def exile_nonland_until_source_leaves(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.card_types import is_land_card, is_token_card
    from rules_engine.linked_exile import record_linked_exile, source_still_present

    source_id = payload.get("source_card_id")
    timestamp = int(payload.get("source_timestamp", -1))
    if not source_still_present(state, source_id, timestamp):
        return
    mv_max = int(payload["mv_max"])
    affected = [cid for player in state.players.values() for cid in player.battlefield
                if not is_land_card(state.cards[cid]) and mana_value(state.cards[cid].mana_cost or "") <= mv_max]
    for cid in affected:
        capture_last_known_battlefield(state, cid)
    leaves = []
    returning = []
    for cid in affected:
        card = state.cards[cid]
        leaves.append({"card_id": cid, "controller": card.controller})
        state.players[card.controller].battlefield.remove(cid)
        state.players[card.owner].exile.append(cid)
        card.move_to_zone(Zone.EXILE)
        if not is_token_card(card):
            returning.append(cid)
    record_linked_exile(state, source_id, timestamp, returning)
    emit_event_batch(state, "leaves_battlefield", leaves)
    state.log.append(f"Exile nonland permanents with mana value {mv_max} or less until the source leaves: {len(affected)} exiled.")


def copy_linked_exiled_card(state: MatchState, controller: int, payload: dict) -> None:
    from copy import copy
    from rules_engine.card_faces import select_cast_face
    from rules_engine.linked_exile import linked_exiled_creatures, source_still_present

    source_id = payload["source_card_id"]
    timestamp = int(payload["source_timestamp"])
    if not source_still_present(state, source_id, timestamp):
        return
    x_value = int(payload["x_value"])
    options = [cid for cid in linked_exiled_creatures(state, source_id, timestamp)
               if mana_value(state.cards[cid].mana_cost or "") == x_value]
    if not options:
        return
    chosen = payload.get("selected_card_id")
    if chosen is None and controller in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            "kind": "linked_exile_copy", "player_id": controller, "options": options,
            "count": 1, "effect_key": "copy_linked_exiled_card", "effect_payload": payload,
            "label": "Choose an exiled creature card to copy",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    if chosen is None:
        chosen = max(options, key=lambda cid: (int(state.cards[cid].power or 0) + int(state.cards[cid].toughness or 0), cid))
    if chosen not in options:
        raise ValueError("Chosen card is no longer exiled with this permanent at the announced X")
    source = state.cards[source_id]
    previous_name = source.name
    selected = select_cast_face(state.cards[chosen], 0)
    for field in ("name", "mana_cost", "type_line", "types", "power", "toughness", "loyalty", "oracle_text", "keywords", "colors"):
        source.printed_characteristics.setdefault(field, copy(getattr(source, field)))
        setattr(source, field, copy(getattr(selected, field)))
    state.log.append(f"{previous_name} becomes a copy of {selected.name}.")


def exile_all_creatures_incubate(state: MatchState, controller: int, payload: dict) -> None:
    moved = exile_all_creatures(state, controller, payload)
    incubate(state, controller, {"counters": moved})


def exile_colored_permanents_mana_value_at_most(state: MatchState, controller: int, payload: dict) -> None:
    del controller
    mv_max = int(payload["mv_max"])
    affected = [
        cid for player in state.players.values() for cid in player.battlefield
        if card_color_names(state.cards[cid]) and mana_value(state.cards[cid].mana_cost or "") <= mv_max
    ]
    for cid in affected:
        capture_last_known_battlefield(state, cid)
    leaves = []
    for cid in affected:
        card = state.cards[cid]
        state.players[card.controller].battlefield.remove(cid)
        state.players[card.owner].exile.append(cid)
        card.zone = Zone.EXILE
        leaves.append({"card_id": cid, "controller": card.controller})
    emit_event_batch(state, "leaves_battlefield", leaves)
    state.log.append(f"Exile colored permanents with mana value {mv_max} or less: {len(affected)} exiled.")


def destroy_all_artifacts(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    _destroy_all_permanents_of_types(state, {"Artifact"}, "All artifacts are destroyed.")


def destroy_all_enchantments(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    _destroy_all_permanents_of_types(state, {"Enchantment"}, "All enchantments are destroyed.")


def destroy_all_artifacts_and_enchantments(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    _destroy_all_permanents_of_types(state, {"Artifact", "Enchantment"}, "All artifacts and enchantments are destroyed.")


def counter_spell(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.targeting import stack_object_kind
    target_stack_id = payload.get("target_stack_id")
    for i, item in enumerate(state.stack):
        if item.id == target_stack_id:
            if stack_object_kind(state, item) != "spell":
                return
            source = state.cards.get(item.source_card_id)
            if payload.get("target_kind") == "noncreature" and source and "Creature" in (source.types or []):
                return
            restrictions = payload.get("target_restrictions") or {}
            if restrictions:
                from rules_engine.oracle_effects import _target_id_matches_restrictions
                if not _target_id_matches_restrictions(
                    state, item.source_card_id, restrictions, controller,
                    x_value=int((item.payload or {}).get("x_value", 0) or 0),
                ):
                    return
            source_text = (getattr(source, "oracle_text", "") or "").lower() if source else ""
            if payload.get("uncounterable") or "can't be countered" in source_text or "cannot be countered" in source_text:
                state.log.append(f"{item.label} can't be countered.")
                return
            popped = state.stack.pop(i)
            card = state.cards.get(popped.source_card_id)
            if card and not (popped.payload or {}).get("__stack_copy_kind"):
                if (popped.payload or {}).get("__flashback"):
                    exile_flashback_spell(state, card.id)
                else:
                    put_into_graveyard(state, card.id)
            state.log.append(f"{item.label} was countered.")
            return


def counter_spell_unless_pay(state: MatchState, controller: int, payload: dict) -> None:
    """Counter a spell unless its controller chooses and can pay the tax.

    Automated games use the conservative default of paying when legal. API
    callers can provide ``pay_unless_counter`` to model the target player's
    actual choice; the spell still cannot be countered if its target is
    uncounterable.
    """
    target_stack_id = payload.get("target_stack_id")
    item = next((entry for entry in state.stack if entry.id == target_stack_id), None)
    if item is None:
        return
    from rules_engine.targeting import stack_object_kind
    if stack_object_kind(state, item) != "spell":
        return
    source = state.cards.get(item.source_card_id)
    if payload.get("target_kind") == "noncreature" and source and "Creature" in (source.types or []):
        return
    source_text = (getattr(source, "oracle_text", "") or "").lower() if source else ""
    if payload.get("uncounterable") or "can't be countered" in source_text or "cannot be countered" in source_text:
        state.log.append(f"{item.label} can't be countered.")
        return

    pay_choice = payload.get("pay_unless_counter")
    if pay_choice is None:
        pay_choice = True
    if bool(pay_choice):
        from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands

        cost = str(payload.get("unless_cost") or "{2}")
        if can_pay_with_pool_and_lands(state, item.controller, cost, card_name=item.label) and auto_pay_cost(
            state, item.controller, cost, card_name=item.label
        ):
            state.log.append(f"{state.players[item.controller].name} pays {cost} for {item.label}.")
            return
        state.log.append(f"{state.players[item.controller].name} cannot pay {cost} for {item.label}.")
    counter_spell(state, controller, {"target_stack_id": target_stack_id})


def counter_ability(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.targeting import stack_object_kind
    del controller
    target_stack_id = payload.get("target_stack_id")
    for i, item in enumerate(state.stack):
        if item.id == target_stack_id:
            kind = stack_object_kind(state, item)
            if kind == "spell" or (payload.get("target_kind") in {"activated", "triggered"} and payload["target_kind"] != kind):
                return
            source = state.cards.get(item.source_card_id)
            source_text = (getattr(source, "oracle_text", "") or "").lower() if source else ""
            if payload.get("uncounterable") or "can't be countered" in source_text or "cannot be countered" in source_text:
                state.log.append(f"{item.label} can't be countered.")
                return
            state.stack.pop(i)
            state.log.append(f"{item.label} was countered.")
            return


def _copy_stack_object(state: MatchState, controller: int, payload: dict, effect_label: str):
    target_stack_id = payload.get("target_stack_id")
    if not target_stack_id:
        return
    item = next((x for x in state.stack if x.id == target_stack_id), None)
    if item is None:
        return
    copied_payload = copy.deepcopy(item.payload or {})
    from game_state.state import StackItem
    from rules_engine.targeting import stack_object_kind
    import uuid

    kind = stack_object_kind(state, item)
    if (effect_label == "spell") != (kind == "spell"):
        return
    if effect_label == "spell":
        copied_payload["snow_mana_spent"] = 0
        copied_payload["snow_mana_colors"] = {}
        if "mana_spent_to_cast" in copied_payload:
            copied_payload["mana_spent_to_cast"] = 0
        if "__copied_card" not in copied_payload:
            source = state.cards.get(item.source_card_id)
            if source is None:
                return
            copied_payload["__copied_card"] = {
                key: copy.deepcopy(getattr(source, key))
                for key in ("name", "types", "type_line", "mana_cost", "oracle_text", "power",
                            "toughness", "loyalty", "keywords", "colors", "image_uri",
                            "layout", "card_faces", "selected_face_index")
            }
    copied_payload["__stack_copy_kind"] = kind
    copied_payload["__source_card_id"] = item.source_card_id
    copied_payload["__copied_from_stack_id"] = item.id
    copied_payload["__copied_targets"] = list(getattr(item, "targets", []) or [])
    copied_item = StackItem(
        id=str(uuid.uuid4()), source_card_id=item.source_card_id,
        controller=controller, label=f"{item.label} (copy)",
        effect_key=item.effect_key, payload=copied_payload,
        targets=list(getattr(item, "targets", []) or []),
    )
    state.stack.append(copied_item)
    state.priority_player = controller
    state.passed_priority = set()
    state.log.append(f"{state.players[controller].name} copies {effect_label} {item.label}.")
    if payload.get("may_choose_new_targets"):
        _offer_copy_target_choice(state, controller, copied_item)
    return copied_item


def _offer_copy_target_choice(state: MatchState, controller: int, copied_item) -> None:
    from rules_engine.cast_choice import build_cast_hints
    from rules_engine.targeting import validate_cast_targets

    copied_payload = copied_item.payload
    trigger_clause = copied_payload.get("__trigger_target_clause") if copied_payload.get("__trigger_target_choice") else None
    ability_text = copied_payload.get("__ability_target_text")
    is_spell = copied_payload.get("__stack_copy_kind") == "spell"
    if not is_spell and not (trigger_clause or ability_text):
        return
    announced = copied_payload.get("__announced_targets") or {
        key: copied_payload[key]
        for key in ("target_player", "target_card_id", "target_stack_id")
        if copied_payload.get(key) is not None
    }
    if is_spell and copied_item.effect_key == "deal_damage_multi" and announced.get("target_distribution"):
        _offer_divided_copy_target_choice(state, controller, copied_item)
        return
    if is_spell and copied_item.effect_key == "effect_sequence" and announced.get("mode_texts"):
        if not announced.get("mode_targets"):
            keys = ("target_player", "target_card_id", "target_stack_id")
            shared = {key: announced[key] for key in keys if announced.get(key) is not None}
            modes = list(announced["mode_texts"])
            effects = copied_payload.get("effects") or []
            per_mode = {}
            if shared and len(effects) == len(modes):
                for mode in modes:
                    matching = [effect for effect in effects if effect.get("mode_text") == mode]
                    if len(matching) != 1:
                        break
                    selected = {key: matching[0].get("payload", {}).get(key) for key in keys
                                if matching[0].get("payload", {}).get(key) is not None}
                    if len(selected) > 1:
                        break
                    per_mode[mode] = selected
            if len(per_mode) == len(modes) and shared == {
                key: value for selected in per_mode.values() for key, value in selected.items()
            }:
                for key in keys:
                    announced.pop(key, None)
                announced["mode_targets"] = per_mode
                copied_item.targets = [str(value) for selected in per_mode.values() for value in selected.values()]
        if announced.get("mode_targets"):
            _offer_modal_copy_target_choice(state, controller, copied_item)
        return
    target_keys = [key for key in ("target_player", "target_card_id", "target_stack_id") if announced.get(key) is not None]
    if (len(target_keys) != 1 or any(key in announced for key in ("mode_targets", "target_card_ids", "target_distribution"))
            or copied_item.effect_key == "effect_sequence"):
        return
    source = state.cards.get(copied_item.source_card_id)
    if source is None:
        return
    copied_card = copy.copy(source)
    for key, value in (copied_payload.get("__copied_card") or {}).items():
        setattr(copied_card, key, copy.deepcopy(value))
    if not is_spell:
        copied_card.oracle_text = trigger_clause or ability_text
    hints = build_cast_hints(state, copied_card, controller, announced) if is_spell else None
    if not is_spell and not trigger_clause:
        from rules_engine.oracle_effects import inspect_target_hints
        hints = inspect_target_hints(state, copied_card, controller, announced)
    options = ["keep"]
    labels = {"keep": "Keep original target"}
    candidate_keys = {
        "player_targets": "target_player", "creature_targets": "target_card_id",
        "planeswalker_targets": "target_card_id", "permanent_targets": "target_card_id",
        "land_targets": "target_card_id", "artifact_targets": "target_card_id",
        "enchantment_targets": "target_card_id", "noncreature_permanent_targets": "target_card_id",
        "graveyard_creature_targets": "target_card_id", "graveyard_permanent_targets": "target_card_id",
        "stack_targets": "target_stack_id",
    }
    if trigger_clause:
        from rules_engine.events import trigger_target_options
        candidates = [
            (key, option[key], option.get("target_name", str(option[key])))
            for option in trigger_target_options(state, copied_item)
            for key in ("target_player", "target_card_id") if key in option
        ]
    else:
        candidates = [
            (target_key, candidate["id"], candidate.get("name") or candidate.get("label") or str(candidate["id"]))
            for surface, target_key in candidate_keys.items()
            for candidate in hints.get(surface, [])
        ]
    for target_key, value, label in candidates:
        if target_key == "target_stack_id" and value == copied_item.id:
            continue
        option = f"{target_key}:{value}"
        if option in options or (target_key == target_keys[0] and str(value) == str(announced[target_keys[0]])):
            continue
        proposed = {key: value for key, value in announced.items() if key not in target_keys}
        proposed[target_key] = value
        if hints is not None and not validate_cast_targets(hints, proposed)[0]:
            continue
        options.append(option)
        labels[option] = label
    if len(options) > 1:
        state.pending_mechanic_choice = {
            "kind": "copy_target", "player_id": controller, "count": 1,
            "options": options, "option_labels": labels,
            "label": f"Choose a new target for {copied_item.label} or keep its target",
            "stack_id": copied_item.id,
        }


def _offer_divided_copy_target_choice(
    state: MatchState, controller: int, copied_item,
    remaining_targets: list[str] | None = None, slot_number: int = 1, slot_total: int | None = None,
) -> None:
    from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
    from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets

    announced = copied_item.payload["__announced_targets"]
    distribution = copied_item.payload["target_distribution"]
    remaining = list(remaining_targets) if remaining_targets is not None else list(distribution)
    total = slot_total or len(remaining)
    source = state.cards.get(copied_item.source_card_id)
    if source is None:
        return
    copied_card = copy.copy(source)
    for key, value in (copied_item.payload.get("__copied_card") or {}).items():
        setattr(copied_card, key, copy.deepcopy(value))
    hints = build_cast_hints(state, copied_card, controller, announced)
    candidates = [
        ("target_player" if surface == "player_targets" else "target_card_id",
         str(candidate["id"]), candidate.get("name") or str(candidate["id"]))
        for surface in ("player_targets", "creature_targets", "planeswalker_targets")
        for candidate in hints.get(surface, [])
    ]
    for offset, old_id in enumerate(remaining):
        if old_id not in distribution:
            continue
        amount = int(distribution[old_id])
        options = ["keep"]
        target_name = (state.cards[old_id].name if old_id in state.cards
                       else state.players[int(old_id)].name if str(old_id) in {"1", "2"} else str(old_id))
        labels = {"keep": f"Keep {amount} damage on {target_name}"}
        for key, new_id, label in candidates:
            option = f"{key}:{new_id}"
            if new_id in distribution or option in options:
                continue
            proposed = {**announced, "target_distribution": {new_id: amount}, "divide_total": amount}
            if not (validate_cast_choice(hints, proposed)[0]
                    and validate_protection_targets(state, copied_card, proposed)[0]
                    and validate_hexproof_shroud_targets(state, controller, proposed)[0]):
                continue
            options.append(option)
            labels[option] = label
        if len(options) > 1:
            number = slot_number + offset
            state.pending_mechanic_choice = {
                "kind": "copy_target", "player_id": controller, "count": 1,
                "options": options, "option_labels": labels, "stack_id": copied_item.id,
                "label": f"Choose target {number}/{total} for {amount} damage from {copied_item.label}",
                "distribution_target": old_id,
                "remaining_distribution_targets": remaining[offset + 1:],
                "target_slot_number": number, "target_slot_total": total,
            }
            return


def _offer_modal_copy_target_choice(
    state: MatchState, controller: int, copied_item,
    remaining_modes: list[str] | None = None, slot_number: int = 1,
) -> None:
    from rules_engine.oracle_effects import inspect_target_hints
    from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

    announced = copied_item.payload["__announced_targets"]
    modes = list(remaining_modes) if remaining_modes is not None else list(announced.get("mode_texts") or [])
    source = state.cards.get(copied_item.source_card_id)
    if source is None:
        return
    copied_card = copy.copy(source)
    for key, value in (copied_item.payload.get("__copied_card") or {}).items():
        setattr(copied_card, key, copy.deepcopy(value))
    surfaces = {
        "player_targets": "target_player", "creature_targets": "target_card_id",
        "planeswalker_targets": "target_card_id", "permanent_targets": "target_card_id",
        "land_targets": "target_card_id", "artifact_targets": "target_card_id",
        "enchantment_targets": "target_card_id", "noncreature_permanent_targets": "target_card_id",
        "graveyard_creature_targets": "target_card_id", "graveyard_permanent_targets": "target_card_id",
        "stack_targets": "target_stack_id",
    }
    for offset, mode in enumerate(modes):
        selected = (announced.get("mode_targets") or {}).get(mode) or {}
        target_keys = [key for key in ("target_player", "target_card_id", "target_stack_id") if selected.get(key) is not None]
        effects = [effect for effect in copied_item.payload.get("effects", []) if effect.get("mode_text") == mode]
        if len(target_keys) != 1 or len(effects) != 1:
            continue
        key = target_keys[0]
        if str(effects[0].get("payload", {}).get(key)) != str(selected[key]):
            continue
        hints = inspect_target_hints(state, copied_card, controller, {"mode_text": mode})
        options = ["keep"]
        labels = {"keep": f"Keep {mode} on {selected[key]}"}
        for surface, target_key in surfaces.items():
            for candidate in hints.get(surface, []):
                value = candidate["id"]
                if (target_key == key and str(value) == str(selected[key])) or value == copied_item.id:
                    continue
                proposed = {"mode_text": mode, target_key: value}
                if not (validate_cast_targets(hints, proposed)[0]
                        and validate_protection_targets(state, copied_card, proposed)[0]
                        and validate_hexproof_shroud_targets(state, controller, proposed)[0]):
                    continue
                option = f"{target_key}:{value}"
                if option not in options:
                    options.append(option)
                    labels[option] = candidate.get("name") or candidate.get("label") or str(value)
        if len(options) > 1:
            state.pending_mechanic_choice = {
                "kind": "copy_target", "player_id": controller, "count": 1,
                "options": options, "option_labels": labels, "stack_id": copied_item.id,
                "label": f"Choose target for {mode} on {copied_item.label}",
                "mode_target_text": mode, "remaining_modes": modes[offset + 1:],
                "target_slot_number": slot_number + offset,
            }
            return


def copy_spell(state: MatchState, controller: int, payload: dict) -> None:
    copied_item = _copy_stack_object(state, controller, payload, "spell")
    from rules_engine.events import emit_event

    target_stack_id = payload.get("target_stack_id")
    if copied_item and target_stack_id:
        item = next((x for x in state.stack if x.id == target_stack_id), None)
        if item is not None:
            emit_event(
                state,
                "spell_copy",
                {
                    "source_card_id": item.source_card_id,
                    "controller": controller,
                    "label": item.label,
                    "source_stack_id": item.id,
                },
            )


def copy_ability(state: MatchState, controller: int, payload: dict) -> None:
    _copy_stack_object(state, controller, payload, "ability")


def exile_permanent(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    battlefield_owner = state.players[card.controller]
    zone_owner = state.players[getattr(card, "owner", card.controller)]
    if target in battlefield_owner.battlefield:
        emit_event(state, "leaves_battlefield", {"card_id": target, "controller": card.controller})
        battlefield_owner.battlefield.remove(target)
        zone_owner.exile.append(target)
        card.move_to_zone(Zone.EXILE)
        state.log.append(f"{card.name} is exiled.")


def return_permanent_to_hand(state: MatchState, controller: int, payload: dict) -> None:
    """Return a battlefield permanent to its owner's hand without changing ownership."""
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    battlefield_controller = state.players.get(card.controller)
    owner = state.players.get(getattr(card, "owner", card.controller))
    if battlefield_controller is None or owner is None or target not in battlefield_controller.battlefield:
        return
    emit_event(state, "leaves_battlefield", {"card_id": target, "controller": card.controller})
    battlefield_controller.battlefield.remove(target)
    owner.hand.append(target)
    card.move_to_zone(Zone.HAND)
    card.controller = getattr(card, "owner", card.controller)
    card.tapped = False
    card.summoning_sick = False
    state.log.append(f"{card.name} returns to its owner's hand.")


def return_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    requested = payload.get("target_card_id")
    if requested is not None:
        card_id = requested if requested in player.graveyard and not is_departed_token(state.cards[requested]) else None
    else:
        card_id = next((cid for cid in reversed(player.graveyard) if not is_departed_token(state.cards[cid])), None)
    if card_id is None:
        return
    player.graveyard.remove(card_id)
    player.hand.append(card_id)
    state.cards[card_id].move_to_zone(Zone.HAND)
    state.log.append(f"{state.cards[card_id].name} returns from graveyard to hand.")


def put_land_from_hand(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve an effect that puts a land from hand onto the battlefield.

    This is distinct from a normal land play: it does not consume the
    controller's land-play allowance and the effect may enter the land tapped.
    """
    player = state.players[controller]
    eligible = [cid for cid in player.hand if cid in state.cards and "Land" in state.cards[cid].types and not is_departed_token(state.cards[cid])]
    land_id = payload.get("land_id") if payload.get("land_id") in eligible else next(iter(eligible), None)
    if not land_id:
        state.log.append(f"{player.name} has no land in hand for the effect.")
        return
    if pause_for_land_entries(state, controller, [land_id], "put_land_from_hand", {**payload, "land_id": land_id}):
        return
    land = state.cards[land_id]
    apply_entry_choice(state, controller, land, choice=(payload.get("__entry_choices") or {}).get(land_id, "tapped"), effect_tapped=bool(payload.get("tapped", False)))
    player.hand.remove(land_id)
    player.battlefield.append(land_id)
    land.zone = Zone.BATTLEFIELD
    land.controller = controller
    land.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, land_id)
    emit_event(state, "enters_battlefield", {"card_id": land_id, "controller": controller})
    state.log.append(
        f"{player.name} puts {land.name} from hand onto the battlefield"
        f"{' tapped' if land.tapped else ''}."
    )


def cast_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    """Put a qualifying spell from the controller's graveyard onto the stack.

    The effect represents an alternative permission that waives mana payment;
    the spell still resolves through the ordinary stack and returns to its
    owner's graveyard afterward.
    """
    target = payload.get("target_card_id")
    player = state.players[controller]
    if not target or target not in player.graveyard or target not in state.cards or is_departed_token(state.cards[target]):
        return
    card = state.cards[target]
    if not ({"Instant", "Sorcery"} & set(card.types)):
        return
    player.graveyard.remove(target)
    card.zone = Zone.STACK
    from rules_engine.ability_model import build_spell_spec
    from rules_engine.stack_engine import add_to_stack

    ability = build_spell_spec(state, card, controller)
    add_to_stack(
        state,
        source_card_id=target,
        controller=controller,
        label=f"{card.name} (from graveyard)",
        effect_key=ability.effect.key,
        payload=ability.effect.payload,
    )
    state.log.append(f"{player.name} casts {card.name} from the graveyard without paying its mana cost.")


def return_creature_from_graveyard_to_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    source_graveyard = None
    for player in state.players.values():
        if target in player.graveyard:
            source_graveyard = player
            break
    if source_graveyard is None or is_departed_token(card):
        return
    source_graveyard.graveyard.remove(target)
    battlefield_owner = state.players[controller]
    battlefield_owner.battlefield.append(target)
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.tapped = False
    card.summoning_sick = "Creature" in card.types
    card.entered_turn = state.turn
    state.log.append(f"{card.name} returns from graveyard to the battlefield under {state.players[controller].name}'s control.")
    if "Creature" in card.types:
        assign_static_order_on_battlefield_entry(state, target)


def return_permanent_from_graveyard_to_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    source_graveyard = None
    for player in state.players.values():
        if target in player.graveyard:
            source_graveyard = player
            break
    if source_graveyard is None or is_departed_token(card):
        return
    if pause_for_land_entries(state, controller, [target], "return_permanent_from_graveyard_to_battlefield", payload):
        return
    apply_entry_choice(state, controller, card, choice=(payload.get("__entry_choices") or {}).get(target, "tapped"))
    source_graveyard.graveyard.remove(target)
    battlefield_owner = state.players[controller]
    battlefield_owner.battlefield.append(target)
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, target)
    if "Creature" in card.types:
        card.summoning_sick = True
    state.log.append(f"{card.name} returns from graveyard to the battlefield under {state.players[controller].name}'s control.")
    emit_event(state, "enters_battlefield", {"card_id": target, "controller": controller})


def search_library(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.oracle_effects import search_card_matches

    subtype = payload.get("contains")
    destination = str(payload.get("destination", "hand") or "hand").strip().lower()
    limit = int(payload.get("count", 0) or 0)
    mv_max = payload.get("mv_max")
    mv_max = int(mv_max) if mv_max is not None else None
    player = state.players[controller]
    if not subtype:
        return
    if (payload.get("selected_card_ids") is None
            and (controller in state.mechanic_choice_players
                 or (state.replacement_choice_required and controller in state.replacement_choice_players))):
        eligible = [cid for cid in player.library if search_card_matches(state.cards[cid], subtype, mv_max)]
        if eligible:
            state.pending_mechanic_choice = {
                "kind": "search_library", "player_id": controller,
                "options": eligible, "count": min(limit, len(eligible)) if limit else len(eligible),
                "min_count": min(limit, len(eligible)) if subtype == "card" and not payload.get("up_to") else 0,
                "library_ids": list(player.library), "effect_payload": payload,
                "effect_key": "search_library",
                "label": ("Search your library: first selection enters tapped, remaining cards go to hand"
                          if destination == "split_battlefield_hand" else
                          "Search your library: choose the required card" if subtype == "card" and not payload.get("up_to") else
                          "Search your library (you may fail to find a matching card)"),
            }
            state.priority_player = controller
            state.passed_priority = set()
            return
    selected = payload.get("selected_card_ids")
    selected_ids = list(selected) if isinstance(selected, list) else None
    candidates = selected_ids if selected_ids is not None else list(player.library)
    chosen = []
    for cid in candidates:
        if cid not in player.library or cid not in state.cards or cid in chosen:
            continue
        if search_card_matches(state.cards[cid], subtype, mv_max):
            chosen.append(cid)
            if limit and len(chosen) >= limit:
                break
    entering = chosen[:1] if destination == "split_battlefield_hand" else chosen if destination == "battlefield" else []
    if pause_for_land_entries(state, controller, entering, "search_library", {**payload, "selected_card_ids": chosen}):
        return
    found: list[str] = []
    for cid in chosen:
        zone = ("battlefield" if not found else "hand") if destination == "split_battlefield_hand" else destination
        choice = (payload.get("__entry_choices") or {}).get(cid, "tapped")
        player.library.remove(cid)
        _place_searched_card(state, controller, cid, zone, tapped=bool(payload.get("tapped")), entry_choice=choice)
        found.append(state.cards[cid].name)
    if found:
        public_names = bool(payload.get("reveal")) or destination in {"battlefield", "graveyard", "exile"}
        detail = f": {', '.join(found)}" if public_names else ""
        state.log.append(f"{state.players[controller].name} searched library and found {len(found)} card(s){detail}.")
    if payload.get("shuffle"):
        state.rng.shuffle(player.library)
        state.log.append(f"{player.name} shuffles their library.")


def _place_searched_card(
    state: MatchState,
    controller: int,
    card_id: str,
    destination: str,
    *,
    tapped: bool = False,
    entry_choice: str = "tapped",
) -> None:
    card = state.cards[card_id]
    player = state.players[controller]
    if destination == "graveyard":
        put_into_graveyard(state, card_id)
        return
    if destination == "battlefield":
        if "Land" in card.types:
            apply_entry_choice(state, controller, card, choice=entry_choice, effect_tapped=tapped)
        player.battlefield.append(card_id)
        card.zone = Zone.BATTLEFIELD
        card.controller = controller
        if "Land" not in card.types:
            card.tapped = tapped
        card.summoning_sick = True
        card.entered_turn = state.turn
        assign_static_order_on_battlefield_entry(state, card_id)
        emit_event(state, "enters_battlefield", {"card_id": card_id, "controller": controller})
        return
    player.hand.append(card_id)
    card.move_to_zone(Zone.HAND)


def create_token(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import CardInstance
    from rules_engine.domain import basic_land_type_count
    import uuid
    from copy import deepcopy

    name = payload.get("name", "Token")
    p = int(payload.get("power", 1))
    t = int(payload.get("toughness", 1))
    token_controller = int(payload.get("controller", controller))
    amount = (basic_land_type_count(state, token_controller) if payload.get("per_basic_land_type")
              else max(0, int(payload.get("amount", 1))))
    types = list(payload.get("types", ["Creature", "Token"]))
    keywords = list(payload.get("keywords", []))
    sac_next_end = bool(payload.get("sacrifice_next_end_step", False))
    tapped_and_attacking = bool(payload.get("tapped_and_attacking", False))
    attack_target = payload.get("attack_target")
    attack_targets = payload.get("attack_targets")
    if tapped_and_attacking and amount:
        from rules_engine.combat import _valid_defenders, _defender_label

        options = sorted(_valid_defenders(state, 3 - token_controller))
        if attack_targets is not None and (not isinstance(attack_targets, list)
                                           or len(attack_targets) != amount
                                           or any(target not in options for target in attack_targets)):
            state.log.append("Invalid attacking token targets; no tokens created.")
            return
        if attack_targets is None and attack_target is None and len(options) > 1 and token_controller in state.mechanic_choice_players:
            state.pending_mechanic_choice = {
                "kind": "attacking_token_target", "player_id": token_controller,
                "options": options, "option_labels": {key: _defender_label(state, key) for key in options},
                "count": 1, "remaining_amount": amount,
                "effect_payload": {**payload, "per_basic_land_type": False},
                "label": f"Choose where the next {name} token attacks",
            }
            state.priority_player = token_controller
            state.passed_priority = set()
            return
        attack_target = attack_target or f"player:{3 - token_controller}"
    token_image_uri = payload.get("image_uri") or resolve_token_image_uri(name, p, t)
    entry_events = []
    for index in range(amount):
        cid = str(uuid.uuid4())
        token = CardInstance(
            id=cid,
            name=name,
            owner=token_controller,
            controller=token_controller,
            zone=Zone.BATTLEFIELD,
            types=types,
            is_token=True,
            mana_cost=payload.get("mana_cost", ""),
            power=p if "Creature" in types else None,
            toughness=t if "Creature" in types else None,
            type_line=payload.get("type_line") or (f"Token Artifact - {name}" if "Artifact" in types and "Creature" not in types else ""),
            oracle_text=payload.get("oracle_text", ""),
            summoning_sick=True,
            entered_turn=state.turn,
            card_faces=deepcopy(payload.get("card_faces") or []),
            layout=str(payload.get("layout") or ""),
            selected_face_index=payload.get("selected_face_index"),
            keywords=keywords,
            colors=list(payload.get("colors", [])),
            image_uri=token_image_uri,
        )
        state.cards[cid] = token
        state.players[token_controller].battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        if tapped_and_attacking:
            token.tapped = True
            state.attackers.append(cid)
            state.attack_targets[cid] = attack_targets[index] if attack_targets is not None else attack_target
        token.counters.update(payload.get("counters") or {})
        entry_events.append({"card_id": cid, "controller": token_controller})
        if sac_next_end:
            token.counters["__sac_next_end_step"] = 1
    emit_event_batch(state, "enters_battlefield", entry_events)
    token_label = f"{p}/{t}" if "Creature" in types else name
    state.log.append(f"{state.players[token_controller].name} creates {amount} {token_label} token(s).")


def incubate(state: MatchState, controller: int, payload: dict) -> None:
    counters = max(0, int(payload.get("counters", 0)))
    times = max(0, int(payload.get("times", 1)))
    faces = [
        {"name": "Incubator", "type_line": "Token Artifact - Incubator",
         "oracle_text": "{2}: Transform this artifact."},
        {"name": "Phyrexian", "type_line": "Token Artifact Creature - Phyrexian",
         "oracle_text": "", "power": "0", "toughness": "0"},
    ]
    create_token(state, controller, {
        "name": "Incubator", "types": ["Artifact", "Token"],
        "power": 0, "toughness": 0,
        "type_line": faces[0]["type_line"], "oracle_text": faces[0]["oracle_text"],
        "card_faces": faces, "layout": "transform", "selected_face_index": 0,
        "counters": {"+1/+1": counters} if counters else {},
        "amount": times,
    })


def create_token_copy(state: MatchState, controller: int, payload: dict) -> None:
    target_id = payload.get("target_card_id")
    source_id = payload.get("__source_card_id")
    target = state.cards.get(target_id)
    if (target is None or target_id == source_id or target.zone != Zone.BATTLEFIELD
            or target.controller != controller or "Creature" not in target.types
            or "Legendary" in target.types or "legendary" in (target.type_line or "").lower()):
        state.log.append("Copy token ability has no legal target at resolution.")
        return
    keywords = list(target.keywords or [])
    if payload.get("grant_haste") and "haste" not in {value.lower() for value in keywords}:
        keywords.append("haste")
    create_token(state, controller, {
        "name": target.name, "types": list(dict.fromkeys([*target.types, "Token"])),
        "mana_cost": target.mana_cost, "type_line": target.type_line,
        "power": target.power if target.power is not None else 0,
        "toughness": target.toughness if target.toughness is not None else 0,
        "oracle_text": target.oracle_text, "keywords": keywords,
        "colors": target.colors or [], "image_uri": target.image_uri,
        "sacrifice_next_end_step": bool(payload.get("sacrifice_next_end_step")),
    })


def create_shark_token(state: MatchState, controller: int, payload: dict) -> None:
    source_id = payload.get("source_card_id")
    source = state.cards.get(source_id) if source_id else None
    if source is None:
        return
    size = max(0, int(payload.get("x_value", 0) or 0)) if "x_value" in payload else mana_value(getattr(source, "mana_cost", "") or "")
    create_token(
        state,
        controller,
        {"name": "Shark", "power": size, "toughness": size, "amount": 1, "keywords": ["flying"]},
    )


def exile_top_cards_playable(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    amount = max(1, int(payload.get("amount", 2)))
    cards = []
    for _ in range(min(amount, len(player.library))):
        cid = player.library.pop()
        player.exile.append(cid)
        state.cards[cid].move_to_zone(Zone.EXILE)
        player.exile_play_until[cid] = state.turn + 1
        cards.append(state.cards[cid].name)
    if cards:
        state.log.append(f"{player.name} exiles cards playable until the end of turn {state.turn + 1}: {', '.join(cards)}.")


def look_top_select_hand(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    top_n = max(0, int(payload.get("mana_spent_to_cast", 0) or 0))
    top_slice = player.library[-top_n:] if top_n else []
    if not top_slice:
        return
    count = min(len(top_slice), max(0, int(payload.get("hand_count", 0) or 0)))
    if payload.get("selected_card_ids") is None:
        state.pending_mechanic_choice = {
            "kind": "look_top_select_hand", "player_id": controller,
            "options": list(reversed(top_slice)), "count": count,
            "top_ids": top_slice, "effect_payload": payload,
            "effect_key": "look_top_select_hand", "label": f"Choose {count} card(s) for your hand",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return

    explicit = payload.get("selected_card_ids")
    if (isinstance(explicit, list) and len(explicit) == count
            and len(set(explicit)) == count and set(explicit).issubset(top_slice)):
        chosen = list(explicit)
    else:
        chosen = sorted(
            top_slice,
            key=lambda cid: (mana_value(state.cards[cid].mana_cost or ""), state.cards[cid].name),
            reverse=True,
        )[:count]
    player.library = player.library[:-len(top_slice)]
    for cid in chosen:
        state.cards[cid].move_to_zone(Zone.HAND)
        player.hand.append(cid)
    rest = [cid for cid in top_slice if cid not in set(chosen)]
    if payload.get("bottom_random"):
        state.rng.shuffle(rest)
    player.library[:0] = rest
    state.log.append(f"{player.name} looks at {len(top_slice)} cards and puts {len(chosen)} into hand.")


def look_top_distinct_types_to_hand(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.card_types import cards_have_distinct_card_types

    player = state.players[controller]
    top_slice = list(player.library[-max(1, int(payload.get("top_n", 10))):])
    if not top_slice:
        return
    chosen = payload.get("selected_card_ids")
    if chosen is None:
        state.pending_mechanic_choice = {
            "kind": "topdeck_put", "player_id": controller,
            "options": list(reversed(top_slice)), "count": min(9, len(top_slice)),
            "min_count": 0, "top_ids": top_slice,
            "effect_key": "look_top_distinct_types_to_hand", "effect_payload": payload,
            "label": "Choose up to one card for each different card type to put into your hand",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    if (not isinstance(chosen, list) or len(chosen) > 9 or not set(chosen).issubset(top_slice)
            or not cards_have_distinct_card_types(state, chosen)):
        raise ValueError("Selected cards must have assignable distinct card types")
    del player.library[-len(top_slice):]
    for card_id in chosen:
        state.cards[card_id].move_to_zone(Zone.HAND)
        player.hand.append(card_id)
    remaining = [card_id for card_id in top_slice if card_id not in set(chosen)]
    if payload.get("bottom_random"):
        state.rng.shuffle(remaining)
    player.library[:0] = remaining
    state.log.append(f"{player.name} reveals {len(top_slice)} cards and puts {len(chosen)} into hand.")


def look_top_choose(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve a top-card hand/exile/bottom choice, with a legacy AI fallback."""
    player = state.players[controller]
    top_n = max(1, int(payload.get("top_n", 3)))
    top_slice = player.library[-top_n:]
    if not top_slice:
        return
    if (len(top_slice) >= 2 and payload.get("top_choice_hand_id") is None
            and (controller in state.mechanic_choice_players
                 or (state.replacement_choice_required and controller in state.replacement_choice_players))):
        state.pending_mechanic_choice = {
            "kind": "look_top_choose", "player_id": controller,
            "options": list(reversed(top_slice)), "count": len(top_slice),
            "top_ids": top_slice, "effect_payload": payload,
            "label": "Choose hand card, exile card, then bottom order",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return

    explicit_hand = payload.get("top_choice_hand_id")
    explicit_exile = payload.get("top_choice_exile_id")
    explicit_bottom = payload.get("top_choice_bottom_ids")
    top_set = set(top_slice)
    explicit_valid = (
        explicit_hand in top_set
        and explicit_exile in top_set
        and isinstance(explicit_bottom, list)
        and len({explicit_hand, explicit_exile, *explicit_bottom}) == len(top_slice)
        and {explicit_hand, explicit_exile, *explicit_bottom} == top_set
    )

    def card_value(cid: str) -> tuple[int, str]:
        return (mana_value(getattr(state.cards[cid], "mana_cost", "") or ""), state.cards[cid].name)

    if explicit_valid:
        hand_card = explicit_hand
        exile_card = explicit_exile
        ordered = [hand_card, exile_card, *explicit_bottom]
    else:
        ordered = sorted(top_slice, key=card_value, reverse=True)
        hand_card = ordered[0]
        exile_card = ordered[1] if len(ordered) > 1 else None
    player.library = [cid for cid in player.library if cid not in set(top_slice)]

    state.cards[hand_card].move_to_zone(Zone.HAND)
    player.hand.append(hand_card)
    if exile_card is not None:
        player.exile.append(exile_card)
        state.cards[exile_card].move_to_zone(Zone.EXILE)
        player.exile_play_until[exile_card] = int(payload.get("play_exiled_until", state.turn) or state.turn)
    for cid in ordered[2:] if exile_card is not None else ordered[1:]:
        state.cards[cid].move_to_zone(Zone.LIBRARY)
        player.library.insert(0, cid)
    state.log.append(
        f"{player.name} looks at the top {len(top_slice)} cards, puts one card into hand"
        + (f", exiles {state.cards[exile_card].name} with permission to play it" if exile_card else "")
        + ", and puts the rest on the bottom of the library."
    )


def transform_if_top_matches(state: MatchState, controller: int, payload: dict) -> None:
    """Reveal the top card and transform the source when its type condition passes."""
    target_id = payload.get("target_card_id")
    player = state.players[controller]
    if not target_id or target_id not in state.cards or not player.library:
        return
    top_id = player.library[-1]
    top_card = state.cards[top_id]
    required = {str(value).lower() for value in (payload.get("required_types") or [])}
    state.log.append(f"{player.name} reveals {top_card.name} for {state.cards[target_id].name}.")
    if not required.intersection({str(value).lower() for value in (top_card.types or [])}):
        return
    card = state.cards[target_id]
    faces = list(getattr(card, "card_faces", []) or [])
    index = int(payload.get("face_index", 1) or 1)
    if index < 0 or index >= len(faces):
        return
    transform_card(state, controller, {"target_card_id": target_id, "face_index": index})


def transform_card(state: MatchState, controller: int, payload: dict) -> None:
    """Apply a selected face to a battlefield double-faced permanent."""
    target_id = payload.get("target_card_id")
    card = state.cards.get(target_id) if target_id else None
    if card is None or target_id not in state.players[card.controller].battlefield:
        return
    faces = list(getattr(card, "card_faces", []) or [])
    try:
        index = int(payload.get("face_index", 0) or 0)
    except (TypeError, ValueError):
        return
    if index < 0 or index >= len(faces) or index == getattr(card, "selected_face_index", None):
        return
    from rules_engine.card_faces import apply_transform_face
    previous_face = getattr(card, "selected_face_index", None)
    apply_transform_face(card, index)
    state.log.append(f"{card.name} transforms.")
    if not payload.get("__defer_transform_event"):
        emit_event(state, "transformed", {
            "card_id": target_id, "controller": card.controller,
            "from_face_index": previous_face, "to_face_index": index,
        })


def exile_return_transformed(state: MatchState, controller: int, payload: dict) -> None:
    """Exile a transforming Saga and return it as a new back-face permanent."""
    target_id = payload.get("target_card_id")
    card = state.cards.get(target_id) if target_id else None
    if card is None or card.zone != Zone.BATTLEFIELD or target_id not in state.players[card.controller].battlefield:
        return
    exile_permanent(state, controller, {"target_card_id": target_id})
    owner_exile = state.players[card.owner].exile
    if card.zone != Zone.EXILE or target_id not in owner_exile:
        return
    if card.layout != "transform" or len(card.card_faces) < 2 or is_departed_token(card):
        return
    from rules_engine.card_faces import apply_transform_face

    owner_exile.remove(target_id)
    apply_transform_face(card, 1)
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.tapped = False
    card.summoning_sick = "Creature" in card.types
    card.entered_turn = state.turn
    state.players[controller].battlefield.append(target_id)
    assign_static_order_on_battlefield_entry(state, target_id)
    state.log.append(f"{card.name} returns to the battlefield transformed.")
    emit_event(state, "enters_battlefield", {"card_id": target_id, "controller": controller})


def reveal_defending_top_land(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", 1 if controller == 2 else 2))
    player = state.players[target_player]
    if not player.library:
        return
    cid = player.library[-1]
    card = state.cards[cid]
    state.log.append(f"{player.name} reveals {card.name} from the top of their library.")
    if "Land" in card.types:
        player.library.pop()
        player.hand.append(cid)
        card.move_to_zone(Zone.HAND)
        state.log.append(f"{player.name} puts {card.name} into their hand.")


def add_mana(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.mana import add_mana_to_pool
    color = payload.get("color", "C")
    amount = int(payload.get("amount", 1))
    add_mana_to_pool(state, controller, color, amount, source_id=payload.get("__source_card_id"))


def attack_count_reward(state: MatchState, controller: int, payload: dict) -> None:
    if state.declared_attackers_this_turn.get(controller, 0) >= int(payload["minimum_attackers"]):
        draw_cards(state, controller, {"target_player": controller, "amount": 1})
    else:
        create_token(state, controller, dict(payload["token_payload"]))


def transform_if_counters(state: MatchState, controller: int, payload: dict) -> None:
    target_id = payload["target_card_id"]
    card = state.cards.get(target_id)
    if (card is not None and card.zone == Zone.BATTLEFIELD
            and card.effect_timestamp == payload["effect_timestamp"]
            and card.counters.get(payload["counter"], 0) >= int(payload["minimum_counters"])):
        transform_card(state, controller, {"target_card_id": target_id, "face_index": 1})


def add_counters(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    counter = payload.get("counter", "+1/+1")
    amount = int(payload.get("amount", 1))
    if target in state.cards and state.cards[target].zone == Zone.BATTLEFIELD:
        card = state.cards[target]
        if "effect_timestamp" in payload and card.effect_timestamp != payload["effect_timestamp"]:
            return
        card.counters[counter] = card.counters.get(counter, 0) + amount
        if payload.get("animate_land") and "Land" in card.types:
            card.types = list(dict.fromkeys([*card.types, "Creature", "Elemental"]))
            card.power = 0
            card.toughness = 0
            if payload.get("animate_untap"):
                card.tapped = False
            for keyword in payload.get("animate_keywords", []):
                if keyword not in {str(x).lower() for x in card.keywords}:
                    card.keywords.append(keyword)
            state.log.append(f"{card.name} becomes a 0/0 Elemental creature.")
        # PT delta from counters is computed dynamically by effective_power/toughness


def add_counters_each_creature(state: MatchState, controller: int, payload: dict) -> None:
    for card_id in list(state.players[controller].battlefield):
        if card_id in state.cards and "Creature" in state.cards[card_id].types:
            add_counters(state, controller, {**payload, "target_card_id": card_id})


def set_next_creature_entry_counter(state: MatchState, controller: int, payload: dict) -> None:
    """Arm a one-shot counter for the next creature spell cast this turn."""
    amount = max(0, int(payload.get("amount", 1) or 0))
    if amount <= 0:
        return
    state.pending_entry_counters.append(
        {
            "controller": int(controller),
            "counter": str(payload.get("counter", "+1/+1")),
            "amount": amount,
            "expires_turn": int(state.turn),
            "source_card_id": payload.get("__source_card_id"),
        }
    )
    state.log.append(
        f"{state.players[controller].name} will put {amount} +1/+1 counter on the next creature they cast this turn."
    )


def put_green_creature_from_hand(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    target = next(
        (
            cid
            for cid in player.hand
            if cid in state.cards
            and not is_departed_token(state.cards[cid])
            and "Creature" in state.cards[cid].types
            and "{G}" in (state.cards[cid].mana_cost or "").upper()
        ),
        None,
    )
    if not target:
        return
    player.hand.remove(target)
    player.battlefield.append(target)
    card = state.cards[target]
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.summoning_sick = True
    card.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, target)
    emit_event(state, "enters_battlefield", {"card_id": target, "controller": controller})
    state.log.append(f"{player.name} puts {card.name} from hand onto the battlefield.")


def temporary_pt_buff(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    power = int(payload.get("power", payload.get("amount", 1)) or 0)
    toughness = int(payload.get("toughness", payload.get("amount", 1)) or 0)
    if target in state.cards and (power or toughness):
        card = state.cards[target]
        card.counters["__eot_power"] = int(card.counters.get("__eot_power", 0)) + power
        card.counters["__eot_toughness"] = int(card.counters.get("__eot_toughness", 0)) + toughness
        state.log.append(
            f"{card.name} gets +{power}/+{toughness} until end of turn."
        )


def temporary_pt_buff_all(state: MatchState, controller: int, payload: dict) -> None:
    power = int(payload.get("power", 0))
    toughness = int(payload.get("toughness", 0))
    keyword = payload.get("keyword")
    if not power and not toughness and not keyword:
        return
    players = [state.players[controller]] if payload.get("controller_only") else state.players.values()
    required_subtypes = set(payload.get("creature_subtypes") or [])
    for player in players:
        for card_id in list(player.battlefield):
            card = state.cards[card_id]
            if "Creature" not in card.types:
                continue
            if required_subtypes:
                from rules_engine.library_permissions import creature_types

                if (not required_subtypes.intersection(creature_types(card))
                        and "changeling" not in {keyword.lower() for keyword in (card.keywords or [])}):
                    continue
            card.counters["__eot_power"] = int(card.counters.get("__eot_power", 0)) + power
            card.counters["__eot_toughness"] = int(card.counters.get("__eot_toughness", 0)) + toughness
            if keyword:
                card.counters[f"__eot_keyword_{keyword.lower()}"] = 1
    scope = (f"{payload['creature_subtype_label']} you control" if payload.get("creature_subtype_label")
             else "Creatures you control" if payload.get("controller_only") else "All creatures")
    state.log.append(f"{scope} get {power:+d}/{toughness:+d} until end of turn.")


def sacrifice(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards and target in state.players[controller].battlefield:
        from rules_engine.events import flush_staged_triggers
        started_staging = not state.trigger_staging
        if started_staging:
            state.trigger_staging = True
            state.trigger_staging_event = "sacrifice"
        card = state.cards[target]
        destination = replace_die_zone(state, card.controller, target)
        emit_event(state, "leaves_battlefield", {"card_id": target, "controller": controller})
        state.players[controller].battlefield.remove(target)
        zone_owner = state.players[getattr(card, "owner", card.controller)]
        if destination == "exile":
            zone_owner.exile.append(target)
            card.zone = Zone.EXILE
            state.log.append(f"{card.name} is exiled instead of dying.")
            emit_event(state, "sacrifice", {"card_id": target, "controller": controller})
            card.reset_zone_counters(Zone.EXILE)
            if started_staging:
                flush_staged_triggers(state)
            return
        zone_owner.graveyard.append(target)
        card.zone = Zone.GRAVEYARD
        emit_event(state, "permanent_dies", {"card_id": target, "controller": controller})
        if was_creature_on_battlefield(card):
            emit_event(state, "creature_dies", {"card_id": target, "controller": controller})
        emit_event(state, "sacrifice", {"card_id": target, "controller": controller})
        card.reset_zone_counters(Zone.GRAVEYARD)
        if started_staging:
            flush_staged_triggers(state)


def deal_damage_multi(state: MatchState, controller: int, payload: dict) -> None:
    recipients = [
        {("target_player" if str(target).isdigit() else "target_card_id"):
             int(target) if str(target).isdigit() else target, "amount": int(amount)}
        for target, amount in (payload.get("target_distribution") or {}).items()
    ]
    deal_damage_batch(state, controller, {"recipients": recipients, "__source_card_id": payload.get("__source_card_id"),
                                          "__source_lki": payload.get("__source_lki")})


def damage_each_creature_and_player(state: MatchState, controller: int, payload: dict) -> None:
    amount = max(0, int(payload.get("amount", 0)))
    if not amount:
        return
    recipients = [
        {"target_card_id": cid, "amount": amount}
        for player in state.players.values() for cid in list(player.battlefield)
        if "Creature" in state.cards[cid].types
    ]
    recipients.extend({"target_player": pid, "amount": amount} for pid in state.players)
    deal_damage_batch(state, controller, {"recipients": recipients, "__source_card_id": payload.get("__source_card_id"),
                                          "__source_lki": payload.get("__source_lki")})


def deal_damage_batch(state: MatchState, controller: int, payload: dict) -> None:
    source_id = payload.get("__source_card_id")
    source_lki = payload.get("__source_lki")
    lifelink_total = max(0, int(payload.get("lifelink_total", 0)))
    recipients = list(payload.get("recipients") or [])
    for index, recipient in enumerate(recipients):
        recipient = {**recipient, "__source_card_id": source_id, "__source_lki": source_lki,
                     "__defer_lethal": True, "__batch_damage": True}
        target_id = recipient.get("target_card_id")
        affected = state.cards[target_id].controller if target_id else recipient.get("target_player")
        event = "damage_to_permanent" if target_id else "damage_to_player"
        humans = set(getattr(state, "replacement_choice_players", set()) or set())
        if (state.replacement_choice_required and (not humans or affected in humans)
                and not damage_cant_be_prevented(state, source_card_id=source_id,
                                                target_player=recipient.get("target_player"), target_card_id=target_id)):
            options = replacement_options(
                state, event, target_player=affected if not target_id else None,
                target_card_id=target_id, source_card_id=source_id,
            )
            if len(options) > 1:
                state.pending_replacement_choice = {
                    "resume_kind": "damage_batch", "player_id": affected, "event": event,
                    "target_player": recipient.get("target_player"), "target_card_id": target_id,
                    "amount": recipient["amount"], "controller": controller, "source_card_id": source_id,
                    "source_lki": source_lki,
                    "options": options, "combat_damage_needs_sba": True,
                    "continuation_effects": [{
                        "effect_key": "deal_damage_batch",
                        "payload": {"recipients": recipients[index + 1:], "__source_card_id": source_id,
                                    "__source_lki": source_lki,
                                    "lifelink_total": lifelink_total},
                    }],
                }
                state.priority_player = affected
                state.passed_priority = set()
                return
        dealt = deal_damage(state, controller, recipient)
        pending = state.pending_replacement_choice or state.pending_mechanic_choice
        if pending:
            pending["combat_damage_needs_sba"] = True
            pending.setdefault("continuation_effects", []).append({
                "effect_key": "deal_damage_batch",
                "payload": {"recipients": recipients[index + 1:], "__source_card_id": source_id,
                            "__source_lki": source_lki,
                            "lifelink_total": lifelink_total},
            })
            return
        from rules_engine.damage_results import source_has_keyword
        if source_has_keyword(state, source_id, "lifelink", source_lki):
            lifelink_total += dealt
    _gain_lifelink_from_damage(state, source_id, lifelink_total, source_lki)


def tap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards:
        state.cards[target].tapped = True


def tap_all_opponent_creatures(state: MatchState, controller: int, payload: dict) -> None:
    for player_id, player in state.players.items():
        if player_id != controller:
            for cid in player.battlefield:
                if "Creature" in state.cards[cid].types:
                    state.cards[cid].tapped = True


def untap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards:
        state.cards[target].tapped = False


def crew_vehicle(state: MatchState, controller: int, payload: dict) -> None:
    vehicle_id = payload.get("card_id")
    vehicle = state.cards.get(vehicle_id) if vehicle_id else None
    if (vehicle is None or vehicle.zone != Zone.BATTLEFIELD
            or vehicle.effect_timestamp != payload.get("effect_timestamp", vehicle.effect_timestamp)):
        return
    if "Artifact" not in vehicle.types:
        vehicle.counters["__crew_added_artifact"] = 1
    if "Creature" not in vehicle.types:
        vehicle.counters["__crew_added_creature"] = 1
    vehicle.types = list(dict.fromkeys([*vehicle.types, "Artifact", "Creature"]))
    vehicle.counters["__crew_until_turn"] = int(state.turn)
    state.log.append(f"{state.players[controller].name} crews {vehicle.name} with {len(payload.get('crew_card_ids') or [])} creature(s).")


def continuous_buff(state: MatchState, controller: int, payload: dict) -> None:
    # No-op — continuous PT bonuses are computed dynamically by
    # effective_power() / effective_toughness() which scan all battlefield
    # permanents for anthem-like oracle text via _continuous_pt_delta().
    # Permanently mutating base stats here caused buffs to persist after
    # the source left the battlefield (Bug #7).
    pass


def grant_keyword(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    keyword = payload.get("keyword")
    if target in state.cards and keyword:
        card = state.cards[target]
        if payload.get("until_end_of_turn") and card.zone == Zone.BATTLEFIELD:
            card.counters[f"__eot_keyword_{keyword.lower()}"] = 1
        elif keyword not in card.keywords:
            card.keywords.append(keyword)


def prevent_damage(state: MatchState, controller: int, payload: dict) -> None:
    amount = int(payload.get("amount", 0))
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    if target_player is not None:
        add_player_prevention_shield(state, int(target_player), amount)
        state.log.append(f"{state.players[int(target_player)].name} gains a prevention shield of {amount}.")
        return
    if target_card_id in state.cards:
        card = state.cards[target_card_id]
        add_card_prevention_shield(card, amount)
        state.log.append(f"{card.name} gains a prevention shield of {amount}.")


def discard_cards(state: MatchState, controller: int, payload: dict) -> None:
    target_player = int(payload.get("target_player", 1 if controller == 2 else 2))
    amount = int(payload.get("amount", 1))
    player = state.players[target_player]
    from rules_engine.zone_actions import discard_selected, is_departed_token
    available = [cid for cid in player.hand if not is_departed_token(state.cards[cid])]
    count = min(max(0, amount), len(available))
    if count and not payload.get("random") and target_player in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            "kind": "discard", "player_id": target_player, "options": available,
            "count": count, "label": "Choose cards to discard",
        }
        state.priority_player = target_player
        state.passed_priority = set()
        return
    selected = state.rng.sample(available, count) if payload.get("random") else available[:count]
    discard_selected(state, target_player, selected)
    discarded = len(selected)
    state.log.append(f"{player.name} discards {discarded}.")


def each_player_discard(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.zone_actions import discard_simultaneous, is_departed_token

    amount = max(0, int(payload.get("amount", 1)))
    selected = {str(pid): list(ids) for pid, ids in payload.get("selected_cards", {}).items()}
    for pid in (state.active_player, 1 if state.active_player == 2 else 2):
        key = str(pid)
        if key in selected:
            continue
        options = [cid for cid in state.players[pid].hand if not is_departed_token(state.cards[cid])]
        count = min(amount, len(options))
        if count and pid in state.mechanic_choice_players and not payload.get("random"):
            state.pending_mechanic_choice = {
                "kind": "each_player_discard", "player_id": pid, "options": options,
                "count": count, "effect_payload": {"amount": amount, "selected_cards": selected},
                "effect_controller": controller, "label": "Choose cards to discard",
            }
            state.priority_player = pid
            state.passed_priority = set()
            return
        selected[key] = state.rng.sample(options, count) if payload.get("random") else options[:count]
    if not discard_simultaneous(state, {int(pid): ids for pid, ids in selected.items()}):
        raise ValueError("Simultaneous discard selections are no longer valid")
    for pid in (1, 2):
        state.log.append(f"{state.players[pid].name} discards {len(selected[str(pid)])}.")


def choose_revealed_hand_card(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.card_types import is_land_card
    from rules_engine.zone_actions import discard_selected, is_departed_token

    target = int(payload["target_player"])
    excluded = set(payload.get("excluded_types") or [])
    allowed = set(payload.get("allowed_types") or [])
    destination = payload.get("destination", "discard")
    revealed = [cid for cid in state.players[target].hand if not is_departed_token(state.cards[cid])]
    options = [cid for cid in revealed
               if ("Land" not in excluded or not is_land_card(state.cards[cid]))
               and ("Creature" not in excluded or "Creature" not in state.cards[cid].types)
               and (not allowed or allowed.intersection(state.cards[cid].types))
               and ("mv_max" not in payload or mana_value(state.cards[cid].mana_cost or "") <= int(payload["mv_max"]))
               and ("mv_min" not in payload or mana_value(state.cards[cid].mana_cost or "") >= int(payload["mv_min"]))]
    names = ", ".join(state.cards[cid].name for cid in revealed) or "(empty)"
    state.log.append(f"{state.players[target].name} reveals their hand: {names}.")
    linked_source = payload.get("linked_source_id")
    if linked_source:
        from rules_engine.linked_exile import source_still_present
        if not source_still_present(state, linked_source, int(payload.get("linked_source_timestamp", -1))):
            return
    if not options:
        return
    if controller in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            "kind": f"choose_revealed_{destination}", "player_id": controller,
            "target_player": target, "options": options, "count": 1,
            "label": f"Choose a card from the revealed hand to {destination}",
            "linked_source_id": linked_source,
            "linked_source_timestamp": payload.get("linked_source_timestamp"),
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    chosen = min(options, key=lambda cid: (state.cards[cid].mana_cost or "", cid))
    if destination == "exile":
        from rules_engine.zone_actions import exile_selected_from_hand
        if exile_selected_from_hand(state, target, [chosen]) and linked_source:
            from rules_engine.linked_exile import record_linked_exile
            record_linked_exile(state, linked_source, int(payload["linked_source_timestamp"]), [chosen], Zone.HAND)
    else:
        discard_selected(state, target, [chosen])


def _pause_topdeck_put(state: MatchState, controller: int, payload: dict, top_ids: list[str], eligible: list[str], max_count: int) -> bool:
    if not eligible or payload.get("selected_card_ids") is not None:
        return False
    if (controller not in state.mechanic_choice_players
            and (not state.replacement_choice_required or controller not in state.replacement_choice_players)):
        return False
    state.pending_mechanic_choice = {
        "kind": "topdeck_put", "player_id": controller, "options": eligible,
        "count": max_count, "min_count": 0, "top_ids": top_ids,
        "effect_key": payload["__effect_key"], "effect_payload": {key: value for key, value in payload.items() if key != "__effect_key"},
        "label": "Put up to the listed number of cards onto the battlefield",
    }
    state.priority_player = controller
    state.passed_priority = set()
    return True


def topdeck_put_creatures_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    top_n = max(1, int(payload.get("top_n", 6)))
    max_creatures = max(1, int(payload.get("max_creatures", 2)))
    mv_max = max(0, int(payload.get("mv_max", 3)))
    if not player.library:
        return

    # Library top is the tail (draw pops from end).
    top_slice = player.library[-top_n:]

    def is_eligible(cid: str) -> bool:
        card = state.cards[cid]
        if "Creature" not in card.types:
            return False
        return mana_value(card.mana_cost or "") <= mv_max

    eligibles = [cid for cid in top_slice if is_eligible(cid)]
    if _pause_topdeck_put(state, controller, {**payload, "__effect_key": "topdeck_put_creatures_battlefield"}, top_slice, eligibles, max_creatures):
        return
    eligibles.sort(
        key=lambda cid: (
            state.cards[cid].power or 0,
            state.cards[cid].toughness or 0,
            -mana_value(state.cards[cid].mana_cost or ""),
        ),
        reverse=True,
    )
    explicit = payload.get("selected_card_ids")
    if explicit is not None:
        eligible_set = set(eligibles)
        chosen = [cid for cid in explicit if cid in eligible_set][:max_creatures]
    else:
        chosen = eligibles[:max_creatures]

    # Remove inspected cards from library in top-to-bottom order.
    inspected_set = set(top_slice)
    remaining_library = [cid for cid in player.library if cid not in inspected_set]
    player.library = remaining_library

    # Put chosen creatures onto battlefield.
    entry_events = []
    for cid in chosen:
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.summoning_sick = "Creature" in card.types
        card.entered_turn = state.turn
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        entry_events.append({"card_id": cid, "controller": controller})
    emit_event_batch(state, "enters_battlefield", entry_events)

    # Random bottom order consumes the match RNG so snapshots replay identically.
    rest = [cid for cid in top_slice if cid not in set(chosen)]
    if payload.get("bottom_random"):
        state.rng.shuffle(rest)
    for cid in rest:
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    if payload.get("bottom_random"):
        player.library[:0] = rest
    else:
        for cid in rest:
            player.library.insert(0, cid)
    if (rest and payload.get("bottom_any_order") and payload.get("selected_card_ids") is not None
            and state.replacement_choice_required and controller in state.replacement_choice_players):
        state.pending_mechanic_choice = {
            "kind": "topdeck_bottom_order", "player_id": controller,
            "options": rest, "count": len(rest), "bottom_ids": rest,
            "label": "Choose the bottom order, from bottommost to topmost",
        }
        state.priority_player = controller
        state.passed_priority = set()


def topdeck_put_permanents_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    top_n = max(1, int(payload.get("top_n", 5)))
    max_permanents = max(1, int(payload.get("max_permanents", 2)))
    mv_max = payload.get("mv_max")
    top_slice = player.library[-top_n:]
    permanent_types = {"Creature", "Artifact", "Enchantment", "Land", "Planeswalker"}

    def mana_value_for(cid: str) -> int:
        req = parse_mana_cost(getattr(state.cards[cid], "mana_cost", "") or "")
        return int(req["generic"] + req["C"] + sum(req[c] for c in ["W", "U", "B", "R", "G"]))

    eligible = [
        cid for cid in top_slice
        if set(state.cards[cid].types).intersection(permanent_types)
        and (not payload.get("allowed_type") or payload["allowed_type"] in state.cards[cid].types)
        and (mv_max is None or mana_value_for(cid) <= max(0, int(mv_max)))
    ]
    if _pause_topdeck_put(state, controller, {**payload, "__effect_key": "topdeck_put_permanents_battlefield"}, top_slice, eligible, max_permanents):
        return
    eligible.sort(key=lambda cid: (mana_value_for(cid), state.cards[cid].name), reverse=True)
    explicit = payload.get("selected_card_ids")
    if explicit is not None:
        eligible_set = set(eligible)
        chosen = [cid for cid in explicit if cid in eligible_set][:max_permanents]
    else:
        chosen = eligible[:max_permanents]
    if pause_for_land_entries(state, controller, chosen, "topdeck_put_permanents_battlefield", {**payload, "selected_card_ids": chosen}):
        return
    chosen_set = set(chosen)
    player.library = [cid for cid in player.library if cid not in set(top_slice)]
    entry_events = []
    for cid in chosen:
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.controller = controller
        if "Land" in card.types:
            apply_entry_choice(state, controller, card, choice=(payload.get("__entry_choices") or {}).get(cid, "tapped"), effect_tapped=bool(payload.get("tapped")))
        else:
            card.tapped = False
        card.summoning_sick = "Creature" in card.types
        card.entered_turn = state.turn
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        entry_events.append({"card_id": cid, "controller": controller})
    emit_event_batch(state, "enters_battlefield", entry_events)
    rest = [cid for cid in top_slice if cid not in chosen_set]
    if payload.get("bottom_random"):
        state.rng.shuffle(rest)
    for cid in rest:
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    if payload.get("bottom_random"):
        player.library[:0] = rest
    else:
        for cid in rest:
            player.library.insert(0, cid)
    if (rest and payload.get("bottom_any_order") and payload.get("selected_card_ids") is not None
            and state.replacement_choice_required and controller in state.replacement_choice_players):
        state.pending_mechanic_choice = {
            "kind": "topdeck_bottom_order", "player_id": controller,
            "options": rest, "count": len(rest), "bottom_ids": rest,
            "label": "Choose the bottom order, from bottommost to topmost",
        }
        state.priority_player = controller
        state.passed_priority = set()
    state.log.append(f"{player.name} puts {len(chosen)} permanent(s) from the top of the library onto the battlefield.")


def topdeck_reveal_creature_to_hand(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[controller]
    top_n = max(1, int(payload.get("top_n", 4)))
    top_slice = list(player.library[-top_n:])
    eligible = []
    for cid in top_slice:
        card = state.cards[cid]
        if "Creature" not in card.types:
            continue
        if "mv_max" in payload and mana_value(card.mana_cost or "") > int(payload["mv_max"]):
            continue
        if "power_max" in payload:
            try:
                printed_power = int(card.power)
            except (TypeError, ValueError):
                continue
            if printed_power > int(payload["power_max"]):
                continue
        eligible.append(cid)
    if eligible and (controller in state.mechanic_choice_players
                     or (state.replacement_choice_required and controller in state.replacement_choice_players)):
        options = list(eligible)
        if payload.get("optional"):
            options.append("__none__")
        state.pending_mechanic_choice = {
            "kind": "topdeck_reveal_creature", "player_id": controller,
            "options": options, "count": 1, "top_ids": top_slice,
            "bottom_random": bool(payload.get("bottom_random")),
            "option_labels": {"__none__": "Reveal none"},
            "label": "Reveal a qualifying creature",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    def value(cid: str) -> tuple[int, int]:
        card = state.cards[cid]
        try:
            power = int(card.power or 0)
        except (TypeError, ValueError):
            power = 0
        return mana_value(card.mana_cost or ""), power

    chosen = max(eligible, key=value) if eligible else None
    finish_topdeck_reveal_creature(state, controller, top_slice, chosen, bool(payload.get("bottom_random")))


def finish_topdeck_reveal_creature(state: MatchState, controller: int, top_ids: list[str], chosen: str | None, bottom_random: bool) -> bool:
    player = state.players[controller]
    if not top_ids or player.library[-len(top_ids):] != top_ids or (chosen is not None and chosen not in top_ids):
        return False
    del player.library[-len(top_ids):]
    remaining = [cid for cid in top_ids if cid != chosen]
    if chosen is not None:
        state.cards[chosen].move_to_zone(Zone.HAND)
        player.hand.append(chosen)
    if bottom_random:
        state.rng.shuffle(remaining)
    player.library[:0] = remaining
    if chosen is not None:
        state.log.append(f"{player.name} reveals and puts {state.cards[chosen].name} into hand.")
    else:
        state.log.append(f"{player.name} looks at the top {len(top_ids)} cards and reveals none.")
    return True
