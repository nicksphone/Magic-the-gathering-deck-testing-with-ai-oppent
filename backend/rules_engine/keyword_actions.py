from __future__ import annotations

import re

from game_state.state import Step, Zone, assign_static_order_on_battlefield_entry
from rules_engine.mana import auto_pay_cost, can_pay_with_pool_and_lands


def ninjutsu_cost(card) -> str | None:
    match = re.search(r"(?:^|\n)\s*ninjutsu\s+((?:\{[^}]+\})+)", card.oracle_text or "", re.IGNORECASE)
    return match.group(1) if match else None


def ninjutsu_attackers(state, player_id: int) -> list[str]:
    if state.active_player != player_id or not state.blockers_declared or state.step not in {Step.DECLARE_BLOCKERS, Step.COMBAT_DAMAGE, Step.END_COMBAT}:
        return []
    return [cid for cid in state.attackers if cid in state.players[player_id].battlefield and not state.blocks.get(cid)]


def activate_ninjutsu(state, player_id: int, action: dict) -> bool:
    from rules_engine.events import emit_event
    from rules_engine.stack_engine import add_to_stack
    card_id = action.get("card_id")
    return_id = action.get("return_card_id")
    player = state.players[player_id]
    from rules_engine.zone_actions import is_departed_token
    if card_id not in player.hand or return_id not in ninjutsu_attackers(state, player_id) or is_departed_token(state.cards[card_id]):
        return False
    card = state.cards[card_id]
    cost = ninjutsu_cost(card)
    if not cost or not auto_pay_cost(state, player_id, cost, card_name=card.name):
        return False
    returned = state.cards[return_id]
    target = state.attack_targets.get(return_id, f"player:{3-player_id}")
    emit_event(state, "leaves_battlefield", {"card_id": return_id, "controller": player_id})
    player.battlefield.remove(return_id)
    state.players[returned.owner].hand.append(return_id)
    returned.move_to_zone(Zone.HAND)
    state.attackers.remove(return_id)
    state.attack_targets.pop(return_id, None)
    add_to_stack(state, card_id, player_id, f"{card.name} ninjutsu", "ninjutsu", {"attack_target": target}, is_spell=False)
    return True


def resolve_ninjutsu(state, controller: int, payload: dict) -> None:
    from rules_engine.events import emit_event
    card_id = payload.get("__source_card_id")
    player = state.players[controller]
    from rules_engine.zone_actions import is_departed_token
    if card_id not in player.hand or is_departed_token(state.cards[card_id]):
        return
    player.hand.remove(card_id)
    player.battlefield.append(card_id)
    card = state.cards[card_id]
    card.zone = Zone.BATTLEFIELD
    card.tapped = True
    card.summoning_sick = True
    card.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, card_id)
    if state.step in {Step.DECLARE_BLOCKERS, Step.COMBAT_DAMAGE, Step.END_COMBAT} and state.active_player == controller:
        state.attackers.append(card_id)
        state.attack_targets[card_id] = payload["attack_target"]
    emit_event(state, "enters_battlefield", {"card_id": card_id, "controller": controller})


def resolve_annihilator(state, controller: int, payload: dict) -> None:
    player_id = int(payload["target_player"])
    choices = list(state.players[player_id].battlefield)
    count = min(max(0, int(payload["amount"])), len(choices))
    if not count:
        return
    state.pending_mechanic_choice = {"kind": "sacrifice", "player_id": player_id, "options": choices, "count": count, "label": "Annihilator"}
    state.priority_player = player_id
    state.passed_priority = set()


def finish_mechanic_choice(state, player_id: int, action: dict) -> bool:
    from rules_engine.events import emit_event_batch
    from rules_engine.replacement import replace_die_zone
    pending = state.pending_mechanic_choice
    if pending and pending["kind"] == "draw":
        from rules_engine.dredge import complete_draw_choice
        return complete_draw_choice(state, player_id, action)
    if pending and pending["kind"] == "land_entry":
        choice = action.get("choice_id")
        if pending["player_id"] != player_id or choice not in pending["options"]:
            return False
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        payload = dict(pending["effect_payload"])
        payload["__entry_choices"] = {**payload.get("__entry_choices", {}), pending["entry_card_id"]: choice}
        if not state.trigger_staging:
            state.trigger_staging = True
            state.trigger_staging_event = "land_entry"
        state.pending_mechanic_choice = None
        resolve_effect(state, player_id, pending["effect_key"], payload)
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "topdeck_reveal_creature":
        ids = action.get("card_ids")
        if pending["player_id"] != player_id or not isinstance(ids, list) or len(ids) != 1 or ids[0] not in pending["options"]:
            return False
        from effects.handlers import finish_topdeck_reveal_creature
        chosen = None if ids[0] == "__none__" else ids[0]
        if not finish_topdeck_reveal_creature(state, player_id, pending["top_ids"], chosen, pending["bottom_random"]):
            return False
        state.pending_mechanic_choice = None
        if pending.get("resolving_item"):
            from game_state.state import StackItem
            from rules_engine.stack_engine import finish_stack_resolution
            item = StackItem(**pending["resolving_item"])
            finish_stack_resolution(state, item, {**item.payload, "__source_card_id": item.source_card_id})
        if not state.pending_trigger_order and not state.pending_replacement_choice:
            state.priority_player = state.active_player
            state.passed_priority = set()
        return True
    if pending and pending["kind"] == "topdeck_bottom_order":
        ids = action.get("card_ids")
        bottom = pending["bottom_ids"]
        player = state.players[player_id]
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != len(bottom) or len(set(ids)) != len(ids)
                or set(ids) != set(bottom) or set(player.library[:len(bottom)]) != set(bottom)):
            return False
        player.library[:len(bottom)] = ids
        state.pending_mechanic_choice = None
        if pending.get("resolving_item"):
            from game_state.state import StackItem
            from rules_engine.stack_engine import finish_stack_resolution
            item = StackItem(**pending["resolving_item"])
            finish_stack_resolution(state, item, {**item.payload, "__source_card_id": item.source_card_id})
        if not state.pending_trigger_order and not state.pending_replacement_choice:
            state.priority_player = state.active_player
            state.passed_priority = set()
        return True
    if pending and pending["kind"] in {"topdeck_put", "look_top_choose", "look_top_select_hand", "search_library"}:
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) > pending["count"] or len(ids) != len(set(ids))
                or (pending["kind"] == "search_library" and len(ids) < pending.get("min_count", 0))
                or (pending["kind"] == "look_top_choose" and len(ids) != pending["count"])
                or (pending["kind"] == "look_top_select_hand" and len(ids) != pending["count"])
                or any(cid not in pending["options"] for cid in ids)
                or (pending.get("top_ids") is not None and state.players[player_id].library[-len(pending["top_ids"]):] != pending["top_ids"])
                or (pending.get("library_ids") is not None and state.players[player_id].library != pending["library_ids"])):
            return False
        from effects.registry import resolve_effect
        if pending["kind"] == "look_top_choose":
            payload = {**pending["effect_payload"], "top_choice_hand_id": ids[0],
                       "top_choice_exile_id": ids[1], "top_choice_bottom_ids": ids[2:]}
            effect_key = "look_top_choose"
        else:
            payload = {**pending["effect_payload"], "selected_card_ids": ids}
            effect_key = pending["effect_key"]
        state.pending_mechanic_choice = None
        resolve_effect(state, player_id, effect_key, payload)
        if state.pending_mechanic_choice:
            if pending.get("resolving_item"):
                state.pending_mechanic_choice["resolving_item"] = pending["resolving_item"]
            return True
        if pending.get("resolving_item"):
            from game_state.state import StackItem
            from rules_engine.stack_engine import finish_stack_resolution
            item = StackItem(**pending["resolving_item"])
            finish_stack_resolution(state, item, {**item.payload, "__source_card_id": item.source_card_id})
        if not state.pending_trigger_order and not state.pending_replacement_choice:
            state.priority_player = state.active_player
            state.passed_priority = set()
        return True
    if not pending or pending["player_id"] != player_id or pending["kind"] != "sacrifice":
        return False
    ids = action.get("card_ids", [])
    if not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids) or len(ids) != pending["count"] or len(set(ids)) != len(ids) or any(cid not in state.players[player_id].battlefield or cid not in pending["options"] for cid in ids):
        return False
    events = [{"card_id": cid, "controller": player_id} for cid in ids]
    destinations = {cid: replace_die_zone(state, player_id, cid) for cid in ids}
    emit_event_batch(state, "leaves_battlefield", events)
    for cid in ids:
        card = state.cards[cid]
        state.players[player_id].battlefield.remove(cid)
        zone = Zone.EXILE if destinations[cid] == "exile" else Zone.GRAVEYARD
        getattr(state.players[card.owner], zone.value).append(cid)
        card.zone = zone
        state.log.append(f"{state.players[player_id].name} sacrifices {card.name}.")
    emit_event_batch(state, "sacrifice", events)
    died = [event for event in events if state.cards[event["card_id"]].zone == Zone.GRAVEYARD]
    emit_event_batch(state, "permanent_dies", died)
    emit_event_batch(state, "creature_dies", [event for event in died if "Creature" in state.cards[event["card_id"]].types])
    state.pending_mechanic_choice = None
    if pending.get("resolving_item"):
        from game_state.state import StackItem
        from rules_engine.stack_engine import finish_stack_resolution
        item = StackItem(**pending["resolving_item"])
        finish_stack_resolution(state, item, {**item.payload, "__source_card_id": item.source_card_id})
    if not state.pending_trigger_order and not state.pending_replacement_choice:
        state.priority_player = state.active_player
        state.passed_priority = set()
    return True


def ninjutsu_moves(state, player_id: int) -> list[dict]:
    from rules_engine.zone_actions import is_departed_token
    attackers = ninjutsu_attackers(state, player_id)
    if not attackers:
        return []
    moves = []
    for cid in state.players[player_id].hand:
        card = state.cards[cid]
        if is_departed_token(card):
            continue
        cost = ninjutsu_cost(card)
        if cost and can_pay_with_pool_and_lands(state, player_id, cost, card_name=card.name):
            for return_id in attackers:
                moves.append({"type": "ninjutsu", "card_id": cid, "return_card_id": return_id, "card_name": card.name, "mana_cost": cost})
    return moves
