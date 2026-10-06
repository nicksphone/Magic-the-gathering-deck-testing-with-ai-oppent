from __future__ import annotations
from rules_engine.type_effects import effective_types

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
    source_sequence = card.zone_change_sequence
    cost = ninjutsu_cost(card)
    if not cost or not auto_pay_cost(state, player_id, cost, card_name=card.name,
            payment_kind='activation', payment_types=set(effective_types(state, card)), source_card_id=card_id, ability_kind='ninjutsu'):
        return False
    returned = state.cards[return_id]
    target = state.attack_targets.get(return_id, f"player:{3-player_id}")
    emit_event(state, "leaves_battlefield", {"card_id": return_id, "controller": player_id})
    player.battlefield.remove(return_id)
    state.players[returned.owner].hand.append(return_id)
    returned.move_to_zone(Zone.HAND)
    state.attackers.remove(return_id)
    state.attack_targets.pop(return_id, None)
    add_to_stack(state, card_id, player_id, f"{card.name} ninjutsu", "ninjutsu",
                 {"attack_target": target, "__source_zone_sequence": source_sequence}, is_spell=False)
    return True


def resolve_ninjutsu(state, controller: int, payload: dict) -> None:
    from rules_engine.events import emit_event
    card_id = payload.get("__source_card_id")
    player = state.players[controller]
    from rules_engine.zone_actions import is_departed_token
    card = state.cards.get(card_id)
    source_sequence = payload.get("__source_zone_sequence")
    # A returned hand card is a new object; paid costs do not follow it.
    if (card_id not in player.hand or card is None or card.zone != Zone.HAND
            or type(source_sequence) is not int or source_sequence != card.zone_change_sequence
            or is_departed_token(card)):
        return
    player.hand.remove(card_id)
    player.battlefield.append(card_id)
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
    from rules_engine.events import emit_event_batch, was_creature_on_battlefield
    from rules_engine.replacement import replace_die_zone
    pending = state.pending_mechanic_choice
    if pending and pending.get('kind') in {'library_top_order', 'library_order_shuffle', 'library_shuffle'}:
        from rules_engine.library_reorder import finish_reorder
        return finish_reorder(state, player_id, action)
    if pending and pending.get('kind') == 'optional_reveal':
        from rules_engine.optional_reveal import finish_reveal
        return finish_reveal(state, player_id, action)
    if pending and pending['kind'] == 'foretell_from_hand':
        from rules_engine.foretell import finish_hand_choice
        return finish_hand_choice(state, player_id, action)
    if pending and pending['kind'] in {'scry', 'scry_top_order', 'surveil', 'surveil_top_order'}:
        from rules_engine.scry import finish_scry
        return finish_scry(state, player_id, action)
    if pending and pending['kind'] == 'proliferate':
        ids = action.get('card_ids')
        if (pending['player_id'] != player_id or not isinstance(ids, list)
                or any(not isinstance(cid, str) for cid in ids)
                or len(set(ids)) != len(ids) or any(cid not in pending['options'] for cid in ids)):
            return False
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        state.pending_mechanic_choice = None
        resolve_effect(state, pending['controller'], 'proliferate',
                       {**pending['effect_payload'], 'recipients': ids})
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] in {"ward_payment", "ward_cost_cards", "counter_payment"}:
        from rules_engine.ward import finish_ward_choice
        return finish_ward_choice(state, player_id, action)
    if pending and pending['kind'] in {'optional_search', 'graveyard_return'}:
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        ids = action.get('card_ids')
        if (pending['player_id'] != player_id or not isinstance(ids, list) or len(ids) != 1
                or ids[0] not in pending['options']):
            return False
        if pending['kind'] == 'graveyard_return' and (
                ids[0] not in state.players[player_id].graveyard
                or state.cards[ids[0]].zone != Zone.GRAVEYARD
                or not set(pending['effect_payload']['allowed_types']).intersection(effective_types(state, state.cards[ids[0]]))):
            return False
        state.pending_mechanic_choice = None
        if pending['kind'] == 'graveyard_return':
            resolve_effect(state, player_id, 'choose_graveyard_return',
                           {**pending['effect_payload'], 'selected_card_ids': ids})
        elif ids == ['search']:
            resolve_effect(state, player_id, 'search_library',
                           {**pending['effect_payload'], '__search_accepted': True})
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "attacking_token_target":
        from effects.registry import resolve_effect
        from rules_engine.combat import _valid_defenders
        from rules_engine.stack_engine import resume_paused_resolution

        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list) or len(ids) != 1
                or ids[0] not in pending["options"]
                or ids[0] not in _valid_defenders(state, 3 - player_id)):
            return False
        payload = dict(pending["effect_payload"])
        chosen_targets = [*pending.get("selected_attack_targets", []), ids[0]]
        remaining = max(0, int(pending["remaining_amount"]) - 1)
        if remaining:
            pending["selected_attack_targets"] = chosen_targets
            pending["remaining_amount"] = remaining
            state.pending_mechanic_choice = pending
            state.priority_player = player_id
            state.passed_priority = set()
            return True
        state.pending_mechanic_choice = None
        resolve_effect(state, player_id, "create_token", {
            **payload, "amount": len(chosen_targets), "attack_targets": chosen_targets,
        })
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "copy_target":
        from rules_engine.stack_engine import resume_paused_resolution
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != 1 or ids[0] not in pending["options"]):
            return False
        copied = next((item for item in state.stack if item.id == pending["stack_id"]), None)
        if copied is None:
            return False
        chosen = ids[0]
        if pending.get('linked_target_index') is not None:
            from rules_engine.linked_targets import choose_linked_copy_target
            if not choose_linked_copy_target(state, copied, pending, chosen):
                return False
            if not state.pending_mechanic_choice and not pending.get('resolving_item'):
                from rules_engine.ward import mark_stack_targets
                mark_stack_targets(state, copied)
            resume_paused_resolution(state, pending)
            return True
        if pending.get('ordered_target_index') is not None:
            from rules_engine.ordered_targets import choose_ordered_copy_target
            if not choose_ordered_copy_target(state, copied, pending, chosen):
                return False
            if not state.pending_mechanic_choice and not pending.get('resolving_item'):
                from rules_engine.ward import mark_stack_targets
                mark_stack_targets(state, copied)
            resume_paused_resolution(state, pending)
            return True
        if pending.get("clause_effect_index") is not None:
            from effects.handlers import _offer_clause_copy_target_choice

            index = pending["clause_effect_index"]
            key = pending["clause_target_key"]
            effects = copied.payload.get("effects") or []
            announced = copied.payload.get("__announced_targets") or {}
            if index >= len(effects) or key not in announced or effects[index].get("payload", {}).get(key) != announced[key]:
                return False
            if chosen != "keep":
                chosen_key, raw_value = chosen.split(":", 1)
                if chosen_key != key:
                    return False
                value = int(raw_value) if key == "target_player" else raw_value
                announced[key] = value
                effects[index]["payload"][key] = value
                copied.targets = [str(announced[target]) for target in ("target_card_id", "target_player", "target_stack_id")
                                  if announced.get(target) is not None]
                state.log.append(f"{state.players[player_id].name} changes a target of {copied.label}.")
            state.pending_mechanic_choice = None
            _offer_clause_copy_target_choice(
                state, player_id, copied, remaining_indices=pending["remaining_clause_indices"],
                slot_number=pending["target_slot_number"] + 1,
            )
            resume_paused_resolution(state, pending)
            return True
        if pending.get("mode_target_text") is not None:
            from effects.handlers import _offer_modal_copy_target_choice

            mode = pending["mode_target_text"]
            announced = copied.payload.get("__announced_targets") or {}
            selected = (announced.get("mode_targets") or {}).get(mode) or {}
            effects = [effect for effect in copied.payload.get("effects", []) if effect.get("mode_text") == mode]
            if len(selected) != 1 or len(effects) != 1:
                return False
            old_key, old_value = next(iter(selected.items()))
            if effects[0].get("payload", {}).get(old_key) != old_value:
                return False
            if chosen != "keep":
                key, raw_value = chosen.split(":", 1)
                value = int(raw_value) if key == "target_player" else raw_value
                announced["mode_targets"][mode] = {key: value}
                effects[0]["payload"].pop(old_key)
                effects[0]["payload"][key] = value
                copied.targets = [
                    str(target)
                    for mode_targets in announced["mode_targets"].values()
                    for target in mode_targets.values()
                ]
                state.log.append(f"{state.players[player_id].name} changes a target of {copied.label}.")
            state.pending_mechanic_choice = None
            _offer_modal_copy_target_choice(
                state, player_id, copied, remaining_modes=pending["remaining_modes"],
                slot_number=pending["target_slot_number"] + 1,
            )
            resume_paused_resolution(state, pending)
            return True
        if pending.get("distribution_target") is not None:
            from effects.handlers import _offer_divided_copy_target_choice

            old_id = pending["distribution_target"]
            distribution = copied.payload.get("target_distribution") or {}
            if old_id not in distribution:
                return False
            if chosen != "keep":
                new_id = chosen.split(":", 1)[1]
                if new_id in distribution:
                    return False
                updated = {new_id if target == old_id else target: amount
                           for target, amount in distribution.items()}
                copied.payload["target_distribution"] = updated
                copied.payload["__announced_targets"]["target_distribution"] = dict(updated)
                copied.targets = list(updated)
                state.log.append(f"{state.players[player_id].name} changes a target of {copied.label}.")
            state.pending_mechanic_choice = None
            _offer_divided_copy_target_choice(
                state, player_id, copied,
                remaining_targets=pending["remaining_distribution_targets"],
                slot_number=pending["target_slot_number"] + 1,
                slot_total=pending["target_slot_total"],
            )
            resume_paused_resolution(state, pending)
            return True
        if chosen != "keep":
            key, raw_value = chosen.split(":", 1)
            value = int(raw_value) if key == "target_player" else raw_value
            announced = copied.payload.setdefault("__announced_targets", {})
            for old_key in ("target_player", "target_card_id", "target_stack_id"):
                announced.pop(old_key, None)
                copied.payload.pop(old_key, None)
            announced[key] = value
            copied.payload[key] = value
            if copied.effect_key == 'conditional_instruction':
                from rules_engine.conditional_instructions import capture_target
                capture_target(state, copied.payload)
            if copied.effect_key == 'landfall_alternative':
                for branch in copied.payload['branches']:
                    for old_key in ('target_player', 'target_card_id', 'target_stack_id'):
                        branch['payload'].pop(old_key, None)
                    branch['payload'][key] = value
            if key == 'target_card_id' and (copied.payload.get('__copied_card') or {}).get('bestow_characteristics'):
                from game_state.state import object_incarnation
                target = state.cards[value]
                copied.payload['__bestow_target_incarnation'] = [object_incarnation(target), target.zone_change_sequence]
            copied.targets = [str(value)]
            state.log.append(f"{state.players[player_id].name} changes {copied.label}'s target.")
        state.pending_mechanic_choice = None
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] in {"choose_revealed_discard", "choose_revealed_exile"}:
        from rules_engine.stack_engine import resume_paused_resolution
        from rules_engine.zone_actions import discard_selected, exile_selected_from_hand
        ids = action.get("card_ids")
        target = pending["target_player"]
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != 1 or ids[0] not in pending["options"]
                or ids[0] not in state.players[target].hand):
            return False
        state.pending_mechanic_choice = None
        move = exile_selected_from_hand if pending["kind"] == "choose_revealed_exile" else discard_selected
        if not move(state, target, ids):
            state.pending_mechanic_choice = pending
            return False
        if pending["kind"] == "choose_revealed_exile" and pending.get("linked_source_id"):
            from rules_engine.linked_exile import record_linked_exile
            record_linked_exile(state, pending["linked_source_id"], int(pending["linked_source_timestamp"]), ids, Zone.HAND)
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "linked_exile_copy":
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != 1 or ids[0] not in pending["options"]):
            return False
        state.pending_mechanic_choice = None
        resolve_effect(state, player_id, pending["effect_key"], {
            **pending["effect_payload"], "selected_card_id": ids[0],
        })
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "each_player_discard":
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or len(ids) != pending["count"] or len(set(ids)) != len(ids)
                or any(cid not in pending["options"] or cid not in state.players[player_id].hand for cid in ids)):
            return False
        payload = dict(pending["effect_payload"])
        payload["selected_cards"] = {**payload["selected_cards"], str(player_id): ids}
        state.pending_mechanic_choice = None
        resolve_effect(state, pending["effect_controller"], "each_player_discard", payload)
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "discard":
        from rules_engine.zone_actions import discard_selected
        from rules_engine.stack_engine import resume_paused_resolution
        ids = action.get("card_ids")
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or not pending.get('min_count', pending['count']) <= len(ids) <= pending['count'] or len(set(ids)) != len(ids)
                or any(cid not in pending["options"] or cid not in state.players[player_id].hand for cid in ids)):
            return False
        state.pending_mechanic_choice = None
        if not discard_selected(state, player_id, ids):
            state.pending_mechanic_choice = pending
            return False
        state.log.append(f"{state.players[player_id].name} discards {len(ids)}.")
        from effects.handlers import resolve_discard_followup
        resolve_discard_followup(state, pending.get('effect_controller', player_id), pending.get('followup_effect'), len(ids))
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] == "draw":
        from rules_engine.dredge import complete_draw_choice
        return complete_draw_choice(state, player_id, action)
    if pending and pending['kind'] == 'saga_entry':
        choice = action.get('choice_id')
        if pending['player_id'] != player_id or choice not in pending['options']:
            return False
        from effects.registry import resolve_effect
        from rules_engine.stack_engine import resume_paused_resolution
        payload = pending['effect_payload']
        payload['entry_payload']['__read_ahead_chapter'] = int(choice)
        state.pending_mechanic_choice = None
        resolve_effect(state, player_id, pending['effect_key'], payload)
        resume_paused_resolution(state, pending)
        return True
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
        state.pending_mechanic_choice = None
        if not finish_topdeck_reveal_creature(state, player_id, pending["top_ids"], chosen,
                                             pending["bottom_random"], pending.get("bottom_any_order", False)):
            state.pending_mechanic_choice = pending
            return False
        from rules_engine.stack_engine import resume_paused_resolution
        resume_paused_resolution(state, pending)
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
        from rules_engine.stack_engine import resume_paused_resolution
        resume_paused_resolution(state, pending)
        return True
    if pending and pending["kind"] in {"topdeck_put", "look_top_choose", "look_top_select_hand", "search_library"}:
        ids = action.get("card_ids")
        if (pending.get("effect_key") == "look_top_distinct_types_to_hand"
                and isinstance(ids, list) and all(isinstance(cid, str) for cid in ids)):
            from rules_engine.card_types import cards_have_distinct_card_types
            if not cards_have_distinct_card_types(state, ids):
                return False
        if (pending["player_id"] != player_id or not isinstance(ids, list)
                or any(not isinstance(cid, str) for cid in ids)
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
            from rules_engine.stack_engine import resume_paused_resolution
            resume_paused_resolution(state, pending)
            return True
        from rules_engine.stack_engine import resume_paused_resolution
        resume_paused_resolution(state, pending)
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
    for event in events:
        card = state.cards[event["card_id"]]
        if card.zone == Zone.EXILE:
            card.reset_zone_counters(Zone.EXILE)
    died = [event for event in events if state.cards[event["card_id"]].zone == Zone.GRAVEYARD]
    emit_event_batch(state, "permanent_dies", died)
    emit_event_batch(state, "creature_dies", [event for event in died if was_creature_on_battlefield(state.cards[event["card_id"]])])
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
        if cost and can_pay_with_pool_and_lands(state, player_id, cost, card_name=card.name,
                payment_kind='activation', payment_types=set(effective_types(state, card)), source_card_id=cid, ability_kind='ninjutsu'):
            for return_id in attackers:
                moves.append({"type": "ninjutsu", "card_id": cid, "return_card_id": return_id, "card_name": card.name, "mana_cost": cost})
    return moves
