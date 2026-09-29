from __future__ import annotations

import uuid
import re
from copy import copy
from typing import Any

from game_state.state import MatchState, StackItem, Zone
from rules_engine.card_types import is_token_card
from rules_engine.oracle_text import without_reminder_text


def capture_last_known_battlefield(state: MatchState, card_id: str) -> None:
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD:
        return
    from rules_engine.continuous import effective_power, effective_toughness
    card.last_known_battlefield = {
        "name": card.name,
        "oracle_text": card.oracle_text,
        "types": list(card.types),
        "controller": card.controller,
        "power": effective_power(state, card_id),
        "toughness": effective_toughness(state, card_id),
        "selected_face_index": card.selected_face_index,
    }


def _departed_card_view(state: MatchState, card_id: str | None):
    card = state.cards.get(card_id) if card_id else None
    if card is None or card.zone == Zone.BATTLEFIELD or not card.last_known_battlefield:
        return card
    former = copy(card)
    for key, value in card.last_known_battlefield.items():
        setattr(former, key, value)
    return former


def was_creature_on_battlefield(card) -> bool:
    return "Creature" in card.last_known_battlefield.get("types", card.types)


def emit_event(state: MatchState, event: str, payload: dict[str, Any]) -> None:
    if event == "leaves_battlefield":
        capture_last_known_battlefield(state, payload.get("card_id"))
    triggers = _collect_triggers(state, event, payload)
    _push_triggers(state, event, triggers)
    if event == "leaves_battlefield":
        _finish_battlefield_exit(state, payload.get("card_id"))
    elif event in {"permanent_dies", "creature_dies"}:
        _finish_death_event(state, event, payload.get("card_id"))


def emit_event_batch(state: MatchState, event: str, payloads: list[dict[str, Any]]) -> None:
    """Collect simultaneous events before putting their triggers on the stack."""
    triggers: list[dict[str, Any]] = []
    one_or_more_sources: set[str] = set()
    if event == "leaves_battlefield":
        for payload in payloads:
            capture_last_known_battlefield(state, payload.get("card_id"))
    for payload in payloads:
        for trigger in _collect_triggers(state, event, payload):
            source_id = str(trigger.get("source_card_id", ""))
            source = state.cards.get(source_id)
            oracle = (getattr(source, "oracle_text", "") or "").lower() if source else ""
            if "one or more" in oracle:
                if source_id in one_or_more_sources:
                    continue
                one_or_more_sources.add(source_id)
            triggers.append(trigger)
    _push_triggers(state, event, triggers)
    if event == "leaves_battlefield":
        for payload in payloads:
            _finish_battlefield_exit(state, payload.get("card_id"))
    elif event in {"permanent_dies", "creature_dies"}:
        for payload in payloads:
            _finish_death_event(state, event, payload.get("card_id"))


def _finish_death_event(state: MatchState, event: str, card_id: str | None) -> None:
    card = state.cards.get(card_id) if card_id else None
    if card and card.zone == Zone.GRAVEYARD and (event == "creature_dies" or not was_creature_on_battlefield(card)):
        card.reset_zone_counters(Zone.GRAVEYARD)


def _finish_battlefield_exit(state: MatchState, card_id: str | None) -> None:
    card = state.cards.get(card_id) if card_id else None
    if card is None:
        return
    if card.zone.value == "exile":
        card.reset_zone_counters(card.zone)
    state.temporary_control_changes.pop(card_id, None)
    from rules_engine.alternative_casts import restore_printed_characteristics
    restore_printed_characteristics(card)
    if card.layout in {"transform", "meld", "flip", "double_faced_token"} and card.selected_face_index not in {None, 0} and card.card_faces:
        from rules_engine.card_faces import apply_transform_face
        apply_transform_face(card, 0)
    for attachment in state.cards.values():
        if attachment.id == card_id or attachment.attached_to == card_id:
            attachment.attached_to = None
            attachment.counters.pop("__attached_to", None)


def _push_triggers(state: MatchState, event: str, triggers: list[dict[str, Any]]) -> None:
    if not triggers:
        return
    if state.trigger_staging:
        state.staged_triggers.extend(
            {**trigger, "payload": {**trigger["payload"], "__trigger_event": event}}
            for trigger in triggers
        )
        return
    if state.cleanup_pending:
        state.cleanup_deferred_triggers.extend({**trigger, "payload": {**trigger["payload"], "__trigger_event": event}} for trigger in triggers)
        return
    active = state.active_player
    controller_order = [active, 1 if active == 2 else 2]
    groups: dict[str, list[dict[str, Any]]] = {}
    for controller in controller_order:
        group = [dict(trigger) for trigger in triggers if int(trigger["controller"]) == controller]
        for index, trigger in enumerate(group):
            trigger["_choice_id"] = f"{trigger['source_card_id']}:{index}"
        if group:
            groups[str(controller)] = group

    choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
    if getattr(state, "trigger_order_choice_required", False):
        for controller in controller_order:
            group = groups.get(str(controller), [])
            if len(group) > 1 and (not choice_players or controller in choice_players):
                state.pending_trigger_order = {
                    "event": event,
                    "groups": groups,
                    "controller_order": controller_order,
                    "selected_orders": {},
                    "current_controller": controller,
                }
                state.priority_player = controller
                state.passed_priority = set()
                state.log.append(
                    f"Trigger order required for {event}; {state.players[controller].name} must order {len(group)} triggered abilities."
                )
                return

    _append_trigger_groups(state, event, groups, controller_order, {})


def flush_staged_triggers(state: MatchState) -> None:
    if not state.trigger_staging or state.pending_replacement_choice:
        return
    triggers = state.staged_triggers
    state.staged_triggers = []
    state.trigger_staging = False
    _push_triggers(state, state.trigger_staging_event, triggers)


def _append_trigger_groups(
    state: MatchState,
    event: str,
    groups: dict[str, list[dict[str, Any]]],
    controller_order: list[int],
    selected_orders: dict[str, list[str]],
) -> None:
    ordered: list[dict[str, Any]] = []
    for controller in controller_order:
        group = list(groups.get(str(controller), []))
        requested = selected_orders.get(str(controller))
        if requested:
            by_id = {str(trigger.get("_choice_id")): trigger for trigger in group}
            group = [by_id[choice_id] for choice_id in requested if choice_id in by_id]
        ordered.extend(group)
    target_stack_ids: list[str] = []
    for order_index, trig in enumerate(ordered):
        payload = dict(trig["payload"])
        item = StackItem(
            id=str(uuid.uuid4()),
            source_card_id=trig["source_card_id"],
            controller=trig["controller"],
            label=trig["label"],
            effect_key=trig["effect_key"],
            payload={**payload, "__trigger_order": order_index, "__trigger_event": payload.get("__trigger_event", event)},
        )
        clause = _targeted_trigger_clause(state, item)
        if clause:
            item.payload["__trigger_target_clause"] = clause
            options = trigger_target_options(state, item)
            if not options:
                state.log.append(f"{item.label} has no legal target and is not put on the stack.")
                continue
            choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
            if getattr(state, "trigger_order_choice_required", False) and (not choice_players or item.controller in choice_players):
                target_stack_ids.append(item.id)
            else:
                # Non-human controllers still need a legal target at stack entry.
                # Destructive effects prefer an opponent's permanent over their own.
                if item.effect_key in {"destroy_permanent", "destroy", "exile", "exile_permanent"}:
                    options.sort(key=lambda option: state.cards[option["target_card_id"]].controller == item.controller)
                item.payload["target_card_id"] = options[0]["target_card_id"]
                item.payload["__trigger_target_choice"] = True
        state.stack.append(item)
    if target_stack_ids:
        _advance_trigger_target(state, event, target_stack_ids)
    state.log.append(f"{len(ordered)} triggered ability(s) added to stack ({event}).")


def resume_trigger_order(state: MatchState, requested_order: list[str]) -> bool:
    pending = getattr(state, "pending_trigger_order", None)
    if not pending or pending.get("phase") == "targets":
        return False
    controller = int(pending.get("current_controller", -1))
    group = list((pending.get("groups") or {}).get(str(controller), []))
    valid_ids = [str(trigger.get("_choice_id")) for trigger in group]
    requested = [str(value) for value in requested_order]
    if len(requested) != len(valid_ids) or set(requested) != set(valid_ids):
        state.log.append("Invalid trigger order; simultaneous trigger resolution remains paused.")
        return False
    selected = dict(pending.get("selected_orders") or {})
    selected[str(controller)] = requested
    controller_order = [int(value) for value in pending.get("controller_order", [])]
    choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
    next_controller = None
    for candidate in controller_order:
        candidate_group = list((pending.get("groups") or {}).get(str(candidate), []))
        if len(candidate_group) > 1 and str(candidate) not in selected and (
            not choice_players or candidate in choice_players
        ):
            next_controller = candidate
            break
    if next_controller is not None:
        pending["selected_orders"] = selected
        pending["current_controller"] = next_controller
        state.pending_trigger_order = pending
        state.priority_player = next_controller
        state.passed_priority = set()
        state.log.append(
            f"{state.players[controller].name} ordered simultaneous triggers; awaiting Player {next_controller}."
        )
        return True
    state.pending_trigger_order = None
    _append_trigger_groups(
        state,
        str(pending.get("event", "trigger")),
        pending.get("groups") or {},
        controller_order,
        selected,
    )
    state.log.append(f"{state.players[controller].name} finalized simultaneous trigger order.")
    return True


def _targeted_trigger_clause(state: MatchState, item: StackItem) -> str | None:
    event = item.payload.get("__trigger_event")
    if event not in {"enters_battlefield", "spell_cast"} or item.payload.get("__trigger_target_clause"):
        return None
    card = state.cards.get(item.source_card_id)
    if not card:
        return None
    for sentence in re.split(r"(?<=\.)\s+|\n", card.oracle_text or ""):
        clause = sentence.strip()
        matches_event = (
            re.match(r"^(?:when|whenever)\b.*\benters\b", clause, re.I)
            if event == "enters_battlefield" else
            re.match(r"^(?:when|whenever) you cast this spell\b", clause, re.I)
        )
        if matches_event and re.search(r"\btarget\b", clause, re.I):
            if re.search(r"\btarget (?:artifact or enchantment|creature|artifact|enchantment|nonland permanent|permanent)\b", clause, re.I) and item.effect_key in {"destroy_permanent", "destroy", "exile", "exile_permanent", "tap_permanent", "untap_permanent", "return_to_hand", "add_counters", "deal_damage"}:
                return clause
    return None


def trigger_target_options(state: MatchState, item: StackItem) -> list[dict[str, Any]]:
    clause = item.payload.get("__trigger_target_clause")
    source = state.cards.get(item.source_card_id)
    if not clause or not source:
        return []
    from rules_engine.oracle_effects import inspect_target_hints
    from rules_engine.targeting import validate_protection_targets, validate_hexproof_shroud_targets
    proxy = copy(source)
    proxy.oracle_text = clause
    hints = inspect_target_hints(state, proxy, item.controller)
    low = clause.lower()
    if "target artifact or enchantment" in low:
        key = "noncreature_permanent_targets"
    elif "target nonland permanent" in low or "target permanent" in low:
        key = "permanent_targets"
    elif "target creature" in low:
        key = "creature_targets"
    elif "target artifact" in low:
        key = "artifact_targets"
    else:
        key = "enchantment_targets"
    options = []
    for target in hints.get(key, []):
        choice = {"target_card_id": target["id"]}
        if validate_protection_targets(state, source, choice)[0] and validate_hexproof_shroud_targets(state, item.controller, choice)[0]:
            options.append({**choice, "target_name": target["name"]})
    return options


def _advance_trigger_target(state: MatchState, event: str, stack_ids: list[str]) -> None:
    remaining = [sid for sid in stack_ids if any(item.id == sid for item in state.stack)]
    if not remaining:
        state.pending_trigger_order = None
        return
    item = next(item for item in state.stack if item.id == remaining[0])
    state.pending_trigger_order = {
        "phase": "targets", "event": event, "stack_ids": remaining,
        "current_stack_id": item.id, "current_controller": item.controller,
    }
    state.priority_player = item.controller
    state.passed_priority = set()
    state.log.append(f"{state.players[item.controller].name} must choose a target for {item.label}.")


def resume_trigger_target(state: MatchState, stack_id: str, target_card_id: str) -> bool:
    pending = state.pending_trigger_order or {}
    if pending.get("phase") != "targets" or pending.get("current_stack_id") != stack_id:
        return False
    item = next((item for item in state.stack if item.id == stack_id), None)
    if not item or target_card_id not in {option["target_card_id"] for option in trigger_target_options(state, item)}:
        return False
    item.payload["target_card_id"] = target_card_id
    item.payload["__trigger_target_choice"] = True
    state.log.append(f"{state.players[item.controller].name} targets {state.cards[target_card_id].name} with {item.label}.")
    _advance_trigger_target(state, str(pending["event"]), list(pending["stack_ids"])[1:])
    return True


def _collect_triggers(state: MatchState, event: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if event == "creature_dies":
        dead_id = payload.get("card_id")
        dead = _departed_card_view(state, dead_id)
        if dead and dead_id not in state.players[dead.controller].battlefield:
            oracle = without_reminder_text((dead.oracle_text or "").lower())
            if "when this creature dies" in oracle and _matches_creature_dies_trigger(state, dead, oracle, payload):
                if "power" not in payload and dead.last_known_battlefield:
                    payload = {**payload, "power": dead.last_known_battlefield["power"]}
                out.append(_trigger_from_oracle(
                    state, dead.id, dead.controller, oracle,
                    default_label=f"{dead.name} trigger", event=event, payload=payload,
                ))
    if event == "attack_declared":
        attacker = state.cards.get(payload.get("card_id"))
        if attacker:
            for amount in re.findall(r"\bannihilator\s+(\d+)", without_reminder_text(attacker.oracle_text or ""), re.IGNORECASE):
                out.append({"source_card_id": attacker.id, "controller": attacker.controller, "label": f"{attacker.name} annihilator {amount}", "effect_key": "annihilator", "payload": {"target_player": 3 - attacker.controller, "amount": int(amount)}})
    if event == "spell_cast":
        source_card_id = str(payload.get("source_card_id", "") or "")
        source_card = state.cards.get(source_card_id) if source_card_id else None
        cast_controller = int(payload.get("controller", 0) or 0)
        source_oracle = without_reminder_text((getattr(source_card, "oracle_text", "") or "").lower()) if source_card else ""
        if source_card is not None and cast_controller == source_card.controller and "when you cast this spell" in source_oracle:
            out.append(
                _trigger_from_oracle(
                    state,
                    source_card_id,
                    cast_controller,
                    source_oracle,
                    default_label=f"{source_card.name} cast trigger",
                    event=event,
                    payload=payload,
                )
            )
    for pid, pstate in state.players.items():
        for cid in list(pstate.battlefield):
            card = state.cards[cid]
            oracle = without_reminder_text((card.oracle_text or "").lower())
            once_each_turn = "only once each turn" in oracle or "this ability triggers only once each turn" in oracle
            trigger_key = f"{cid}:{event}"
            if once_each_turn and trigger_key in state.trigger_once_seen_this_turn:
                continue

            if event == "draw_card" and payload.get("player_id") == card.controller and "whenever you draw a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "draw_card" and payload.get("player_id") != card.controller and "whenever an opponent draws a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "life_gain" and payload.get("player_id") == card.controller and "whenever you gain life" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "life_paid" and payload.get("player_id") == card.controller and "whenever you pay life" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "creature_dies" and _matches_creature_dies_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "permanent_dies" and _matches_permanent_dies_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "leaves_battlefield" and _matches_leaves_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "day_night_changed" and _matches_day_night_trigger(oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "enters_battlefield" and _matches_enters_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} ETB", event=event, payload=payload))
            elif event == "sacrifice" and _matches_sacrifice_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} sacrifice trigger", event=event, payload=payload))
            elif event == "discard" and _matches_discard_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} discard trigger", event=event, payload=payload))
            elif event == "cycle" and _matches_cycle_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} cycling trigger", event=event, payload=payload))
            elif event == "combat_damage_dealt" and _matches_combat_damage_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} combat damage trigger", event=event, payload=payload))
            elif event == "attack_declared" and _matches_attack_trigger(state, card, oracle, payload):
                stripped = re.sub(r"annihilator\s+\d+\s*\([^)]*\)", "", oracle)
                if _matches_attack_trigger(state, card, stripped, payload):
                    out.append(_trigger_from_oracle(state, cid, card.controller, stripped, default_label=f"{card.name} attack trigger", event=event, payload=payload))
            elif event == "block_declared" and _matches_block_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} block trigger", event=event, payload=payload))
            elif event in {"spell_cast", "spell_copy"}:
                cast_controller = int(payload.get("controller", 0) or 0)
                source_card_id = str(payload.get("source_card_id", "") or "")
                source_card = state.cards.get(source_card_id) if source_card_id else None
                source_types = {t.lower() for t in (getattr(source_card, "types", []) or [])}
                if event == "spell_cast" and cast_controller == card.controller and "whenever you cast a spell" in oracle:
                    out.append(
                        _trigger_from_oracle(
                            state,
                            cid,
                            card.controller,
                            oracle,
                            default_label=f"{card.name} cast trigger",
                            event=event,
                            payload=payload,
                        )
                    )
                elif event == "spell_cast" and cast_controller == card.controller and (
                    ("whenever you cast an instant spell" in oracle and "instant" in source_types)
                    or ("whenever you cast a sorcery spell" in oracle and "sorcery" in source_types)
                    or ("whenever you cast an instant or sorcery spell" in oracle and ("instant" in source_types or "sorcery" in source_types))
                ):
                    out.append(
                        _trigger_from_oracle(
                            state,
                            cid,
                            card.controller,
                            oracle,
                            default_label=f"{card.name} cast trigger",
                            event=event,
                            payload=payload,
                        )
                    )
                elif cast_controller == card.controller and source_card and "creature" not in source_types and (
                    ("prowess" in oracle and event == "spell_cast")
                    or "magecraft" in oracle
                    or (event == "spell_cast" and "whenever you cast a noncreature spell" in oracle)
                    or (event == "spell_cast" and "whenever you cast a non-creature spell" in oracle)
                    or "whenever you cast or copy an instant or sorcery spell" in oracle
                    or "whenever you cast or copy a noncreature spell" in oracle
                    or "whenever you cast or copy a non-creature spell" in oracle
                    or (event == "spell_cast" and "gets +1/+1 until end of turn" in oracle)
                ):
                    ability = _trigger_from_oracle(
                        state,
                        cid,
                        card.controller,
                        oracle,
                        default_label=f"{card.name} spell trigger",
                        event=event,
                        payload=payload,
                    )
                    if ability["effect_key"] != "noop":
                        out.append(ability)
                    elif "prowess" in oracle or "magecraft" in oracle or "gets +1/+1 until end of turn" in oracle:
                        out.append(
                            {
                                "source_card_id": cid,
                                "controller": card.controller,
                                "label": f"{card.name} spell trigger",
                                "effect_key": "temporary_pt_buff",
                                "payload": {"target_card_id": cid, "power": 1, "toughness": 1},
                            }
                        )
            elif event == "begin_step":
                step = str(payload.get("step", "")).lower()
                active_player = int(payload.get("active_player", 0) or 0)
                if step == "upkeep":
                    if "at the beginning of each upkeep" in oracle or "at the beginning of upkeep" in oracle:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} upkeep trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                    elif "at the beginning of your upkeep" in oracle and card.controller == active_player:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} upkeep trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                elif step == "end_step":
                    # Delayed sacrifice marker support for token effects.
                    if card.counters.get("__sac_next_end_step", 0) > 0:
                        out.append(
                            {
                                "source_card_id": cid,
                                "controller": card.controller,
                                "label": f"{card.name} delayed sacrifice",
                                "effect_key": "sacrifice",
                                "payload": {"target_card_id": cid},
                            }
                        )
                    if "at the beginning of each end step" in oracle or "at the beginning of end step" in oracle:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} end-step trigger",
                                event=event,
                                payload=payload,
                            )
                        )
                    elif "at the beginning of your end step" in oracle and card.controller == active_player:
                        out.append(
                            _trigger_from_oracle(
                                state,
                                cid,
                                card.controller,
                                oracle,
                                default_label=f"{card.name} end-step trigger",
                                event=event,
                                payload=payload,
                            )
                        )
            if once_each_turn:
                state.trigger_once_seen_this_turn.add(trigger_key)
    out.sort(key=lambda trig: (0 if trig["controller"] == state.active_player else 1, str(trig["source_card_id"]), str(trig["label"])))
    return out


def _matches_creature_dies_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    dead_id = payload.get("card_id")
    dead_card = _departed_card_view(state, dead_id)
    dead_types = set(getattr(dead_card, "types", []) or []) if dead_card else set()
    if "when this creature dies" in oracle:
        return bool(dead_card) and dead_id == card.id and "Creature" in dead_types
    if "whenever another creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and dead_id != card.id and "Creature" in dead_types
    if "whenever a creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types
    if "whenever another nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and dead_id != card.id and "Creature" in dead_types and not is_token_card(dead_card)
    if "whenever a nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types and not is_token_card(dead_card)
    if "whenever one or more nontoken creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types and not is_token_card(dead_card)
    if "whenever one or more creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and "Creature" in dead_types
    if "whenever a creature dies" in oracle or "whenever another creature dies" in oracle:
        return True
    if "whenever one or more creatures die" in oracle:
        return True
    if "whenever a creature you control dies" in oracle or "whenever another creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller
    if "whenever one or more creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller
    if "whenever a nontoken creature you control dies" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and not is_token_card(dead_card)
    if "whenever one or more nontoken creatures you control die" in oracle:
        return bool(dead_card) and dead_card.controller == card.controller and not is_token_card(dead_card)
    return False


def _matches_permanent_dies_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    dead_id = payload.get("card_id")
    dead_card = _departed_card_view(state, dead_id)
    if not dead_card:
        return False
    if "whenever another permanent you control dies" in oracle:
        return dead_card.controller == card.controller and dead_id != card.id
    if "whenever a permanent you control dies" in oracle:
        return dead_card.controller == card.controller
    if "whenever another nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and dead_id != card.id and not is_token_card(dead_card)
    if "whenever a nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and not is_token_card(dead_card)
    if "whenever one or more nontoken permanents you control die" in oracle:
        return dead_card.controller == card.controller and not is_token_card(dead_card)
    if "whenever one or more permanents you control die" in oracle:
        return dead_card.controller == card.controller
    if "whenever a permanent dies" in oracle or "whenever another permanent dies" in oracle:
        return True
    if "whenever one or more permanents die" in oracle:
        return True
    if "whenever a nontoken permanent you control dies" in oracle:
        return dead_card.controller == card.controller and not is_token_card(dead_card)
    if "whenever one or more nontoken permanents you control die" in oracle:
        return dead_card.controller == card.controller and not is_token_card(dead_card)
    if "whenever an artifact dies" in oracle or "whenever another artifact dies" in oracle:
        return "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever an artifact you control dies" in oracle or "whenever another artifact you control dies" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever one or more artifacts you control die" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (getattr(dead_card, "types", []) or [])
    if "whenever an enchantment dies" in oracle or "whenever another enchantment dies" in oracle:
        return "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever an enchantment you control dies" in oracle or "whenever another enchantment you control dies" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever one or more enchantments you control die" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (getattr(dead_card, "types", []) or [])
    if "whenever an artifact or enchantment dies" in oracle or "whenever another artifact or enchantment dies" in oracle:
        return _has_artifact_or_enchantment_type(dead_card)
    if "whenever an artifact or enchantment you control dies" in oracle or "whenever another artifact or enchantment you control dies" in oracle:
        return dead_card.controller == card.controller and _has_artifact_or_enchantment_type(dead_card)
    if "whenever one or more artifacts or enchantments you control die" in oracle:
        return dead_card.controller == card.controller and _has_artifact_or_enchantment_type(dead_card)
    return False


def _matches_leaves_battlefield_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    leaving_id = payload.get("card_id")
    leaving = state.cards.get(leaving_id) if leaving_id else None
    if leaving is None:
        return False
    leaving_types = {str(value).lower() for value in (getattr(leaving, "types", []) or [])}
    controlled = leaving.controller == card.controller
    other = leaving_id != card.id
    if "whenever another creature you control leaves the battlefield" in oracle:
        return controlled and other and "creature" in leaving_types
    if "whenever a creature you control leaves the battlefield" in oracle:
        return controlled and "creature" in leaving_types
    if "whenever one or more creatures you control leave the battlefield" in oracle:
        return controlled and "creature" in leaving_types
    if "whenever one or more creatures leave the battlefield" in oracle:
        return "creature" in leaving_types
    if "whenever another permanent you control leaves the battlefield" in oracle:
        return controlled and other
    if "whenever a permanent you control leaves the battlefield" in oracle:
        return controlled
    if "whenever one or more permanents you control leave the battlefield" in oracle:
        return controlled
    if "whenever one or more permanents leave the battlefield" in oracle:
        return True
    if "whenever another artifact you control leaves the battlefield" in oracle:
        return controlled and other and "artifact" in leaving_types
    if "whenever an artifact you control leaves the battlefield" in oracle:
        return controlled and "artifact" in leaving_types
    if "whenever another enchantment you control leaves the battlefield" in oracle:
        return controlled and other and "enchantment" in leaving_types
    if "whenever an enchantment you control leaves the battlefield" in oracle:
        return controlled and "enchantment" in leaving_types
    if "whenever another permanent leaves the battlefield" in oracle:
        return other
    if "whenever a permanent leaves the battlefield" in oracle:
        return True
    if "whenever another creature leaves the battlefield" in oracle:
        return other and "creature" in leaving_types
    if "whenever a creature leaves the battlefield" in oracle:
        return "creature" in leaving_types
    return False


def _matches_day_night_trigger(oracle: str, payload: dict[str, Any]) -> bool:
    destination = str(payload.get("to", "") or "").lower()
    if destination not in {"day", "night"}:
        return False
    if destination == "day":
        return "becomes day" in oracle or "becomes day" in oracle.replace("the game ", "")
    return "becomes night" in oracle or "becomes night" in oracle.replace("the game ", "")


def _matches_enters_battlefield_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    # Modern Oracle abbreviates battlefield entry to "enters".
    oracle = re.sub(r"\benters\b(?! the battlefield)", "enters the battlefield", oracle)
    entering_id = payload.get("card_id")
    if not entering_id or entering_id not in state.cards:
        return False
    entering_card = state.cards[entering_id]
    # Check controller-scoped clauses before their broader prefixes. Without
    # this ordering, "a creature enters" also matches "under your control".
    entering_types = set(getattr(entering_card, "types", []) or [])
    enters_for_controller = entering_card.controller == card.controller
    if "another creature enters the battlefield under your control" in oracle:
        return "Creature" in entering_types and enters_for_controller and entering_id != card.id
    if "a creature enters the battlefield under your control" in oracle:
        return "Creature" in entering_types and enters_for_controller
    if "another permanent enters the battlefield under your control" in oracle:
        return enters_for_controller and entering_id != card.id
    if "a permanent enters the battlefield under your control" in oracle:
        return enters_for_controller
    if "another artifact enters the battlefield under your control" in oracle:
        return "Artifact" in entering_types and enters_for_controller and entering_id != card.id
    if "an artifact enters the battlefield under your control" in oracle:
        return "Artifact" in entering_types and enters_for_controller
    if "another enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in entering_types and enters_for_controller and entering_id != card.id
    if "an enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in entering_types and enters_for_controller
    if "another artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and enters_for_controller and entering_id != card.id
    if "an artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and enters_for_controller
    if f"when {card.name.lower()} enters the battlefield" in oracle:
        return entering_id == card.id
    if any(f"when {subject} enters the battlefield" in oracle for subject in ("this creature", "this permanent", "this artifact", "this enchantment", "this planeswalker")):
        return entering_id == card.id
    if "whenever another creature enters the battlefield" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever a creature enters the battlefield" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or [])
    if "whenever a creature enters the battlefield under your control" in oracle:
        return "Creature" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield" in oracle:
        return entering_id != card.id
    if "whenever a permanent enters the battlefield" in oracle:
        return True
    if "whenever a permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller and entering_id != card.id
    if "whenever an artifact enters the battlefield" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or [])
    if "whenever an artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another artifact enters the battlefield" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever another artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever an enchantment enters the battlefield" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or [])
    if "whenever an enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another enchantment enters the battlefield" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_id != card.id
    if "whenever another enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever an artifact or enchantment enters the battlefield" in oracle:
        return _has_artifact_or_enchantment_type(entering_card)
    if "whenever an artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_card.controller == card.controller
    if "whenever another artifact or enchantment enters the battlefield" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_id != card.id
    if "whenever another artifact or enchantment enters the battlefield under your control" in oracle:
        return _has_artifact_or_enchantment_type(entering_card) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever a token enters the battlefield" in oracle:
        return is_token_card(entering_card)
    if "whenever a token enters the battlefield under your control" in oracle:
        return is_token_card(entering_card) and entering_card.controller == card.controller
    if "landfall" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever a land enters the battlefield under your control" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller
    if "whenever another land enters the battlefield under your control" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever a land enters the battlefield" in oracle:
        return "Land" in (getattr(entering_card, "types", []) or [])
    return False


def _has_artifact_or_enchantment_type(card) -> bool:
    types = {str(t).lower() for t in (getattr(card, "types", []) or [])}
    return "artifact" in types or "enchantment" in types


def _matches_sacrifice_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    sac_id = payload.get("card_id")
    if not sac_id or sac_id not in state.cards:
        return False
    sac_card = state.cards[sac_id]
    if "whenever you sacrifice a permanent" in oracle:
        return sac_card.controller == card.controller
    if "whenever a permanent you control is sacrificed" in oracle or "whenever a permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller
    if "whenever you sacrifice a creature" in oracle:
        return sac_card.controller == card.controller and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever a creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever an enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact or enchantment you control is sacrificed" in oracle or "whenever an enchantment or artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and _has_artifact_or_enchantment_type(sac_card)
    if "whenever a creature is sacrificed" in oracle:
        return "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact is sacrificed" in oracle:
        return "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever an enchantment is sacrificed" in oracle:
        return "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever an artifact or enchantment is sacrificed" in oracle or "whenever an enchantment or artifact is sacrificed" in oracle:
        return _has_artifact_or_enchantment_type(sac_card)
    if "whenever a permanent is sacrificed" in oracle:
        return True
    if "whenever another permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id
    if "whenever another creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Creature" in (getattr(sac_card, "types", []) or [])
    if "whenever another artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Artifact" in (getattr(sac_card, "types", []) or [])
    if "whenever another enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Enchantment" in (getattr(sac_card, "types", []) or [])
    if "whenever another artifact or enchantment you control is sacrificed" in oracle or "whenever another enchantment or artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and _has_artifact_or_enchantment_type(sac_card)
    return False


def _matches_discard_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    discarded_id = payload.get("card_id")
    if not discarded_id or discarded_id not in state.cards:
        return False
    discarded_card = state.cards[discarded_id]
    discarding_player = payload.get("controller", discarded_card.controller)
    if "whenever you discard a card" in oracle:
        return discarding_player == card.controller
    if "whenever you discard one or more cards" in oracle:
        return discarding_player == card.controller
    if "whenever one or more cards are discarded" in oracle:
        return True
    if "whenever a card is discarded" in oracle:
        return True
    if "whenever a card you discard" in oracle:
        return discarding_player == card.controller
    if "whenever an opponent discards a card" in oracle or "whenever an opponent discards one or more cards" in oracle:
        return discarding_player != card.controller
    if "whenever one or more cards an opponent discards" in oracle:
        return discarding_player != card.controller
    return False


def _matches_cycle_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    cycled_id = payload.get("card_id")
    cycled = state.cards.get(cycled_id) if cycled_id else None
    if cycled is None:
        return False
    cycling_controller = int(payload.get("controller", getattr(cycled, "controller", 0)) or 0)
    if "an opponent cycles" in oracle or "whenever an opponent cycles" in oracle:
        return cycling_controller != card.controller
    if "you cycle" not in oracle and "whenever you cycle" not in oracle:
        return False
    if cycling_controller != card.controller:
        return False
    if "you cycle a card" in oracle or "you cycle one or more cards" in oracle:
        return True
    # Named cycling triggers (for example, "When you cycle Shark Typhoon")
    # are matched against the actual cycled card name, not a card-specific ID.
    cycled_name = re.sub(r"\s+\([^)]*\)", "", str(cycled.name or "")).strip().lower()
    return bool(cycled_name and f"cycle {cycled_name}" in oracle)


def _matches_combat_damage_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    source_id = payload.get("source_card_id")
    if not source_id or source_id not in state.cards:
        return False
    source_card = state.cards[source_id]
    if source_card.controller != card.controller:
        return False
    if source_id != card.id and "whenever a creature you control deals combat damage" not in oracle and "whenever a creature you control deals combat damage to" not in oracle:
        # Only source-specific combat damage triggers are supported here unless the card explicitly references a creature you control.
        return False
    target_player = payload.get("target_player")
    target_card_id = payload.get("target_card_id")
    if target_player is not None:
        if "deals combat damage to a player" in oracle or "deals combat damage to an opponent" in oracle:
            return True
        if "whenever this creature deals combat damage to a player" in oracle:
            return source_id == card.id
        if "whenever a creature you control deals combat damage to a player" in oracle:
            return "Creature" in (getattr(source_card, "types", []) or [])
    if target_card_id is not None:
        target_card = state.cards.get(target_card_id)
        if not target_card:
            return False
        if "deals combat damage to a creature" in oracle:
            return True
        if "whenever this creature deals combat damage to a creature" in oracle:
            return source_id == card.id
        if "whenever a creature you control deals combat damage to a creature" in oracle:
            return "Creature" in (getattr(source_card, "types", []) or [])
    return False


def _matches_attack_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    attacking_id = payload.get("card_id")
    if not attacking_id or attacking_id not in state.cards:
        return False
    attacking_card = state.cards[attacking_id]
    if attacking_card.controller != card.controller:
        return False
    if "whenever this creature attacks" in oracle or "whenever this token attacks" in oracle:
        return attacking_id == card.id
    named_attack = re.search(r"whenever\s+(.+?)\s+attacks", oracle)
    if named_attack:
        named_source = re.sub(r"\s+\([^)]*\)", "", named_attack.group(1)).strip()
        if named_source not in {
            "this creature",
            "this token",
            "a creature",
            "another creature",
            "a creature you control",
            "another creature you control",
            "one or more creatures",
            "you",
        }:
            return attacking_id == card.id and named_source == (getattr(card, "name", "") or "").lower()
    if "whenever this creature or another creature attacks" in oracle:
        return True
    if "whenever a creature attacks" in oracle:
        return True
    if "whenever a creature you control attacks" in oracle:
        return attacking_card.controller == card.controller and "Creature" in (getattr(attacking_card, "types", []) or [])
    if "whenever you attack" in oracle:
        return attacking_card.controller == card.controller
    if "whenever one or more creatures attack" in oracle:
        return True
    return False


def _matches_block_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    blocker_id = payload.get("blocker_id")
    if not blocker_id or blocker_id not in state.cards:
        return False
    blocker_card = state.cards[blocker_id]
    if blocker_card.controller != card.controller:
        return False
    if "whenever this creature blocks" in oracle:
        return blocker_id == card.id
    if "whenever a creature blocks" in oracle:
        return True
    if "whenever a creature you control blocks" in oracle:
        return "Creature" in (getattr(blocker_card, "types", []) or [])
    if "whenever another creature you control blocks" in oracle:
        return blocker_card.controller == card.controller and blocker_id != card.id and "Creature" in (getattr(blocker_card, "types", []) or [])
    if "whenever this creature or another creature blocks" in oracle:
        return True
    return False


def _order_apnap(state: MatchState, triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = state.active_player
    non_active = 1 if active == 2 else 2
    first = [t for t in triggers if t["controller"] == active]
    second = [t for t in triggers if t["controller"] == non_active]
    return first + second


def _trigger_from_oracle(
    state: MatchState,
    source_card_id: str,
    controller: int,
    oracle: str,
    default_label: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    oracle = without_reminder_text(oracle)
    opponent = 1 if controller == 2 else 2
    gain_amount = _first_number(oracle, r"gain (\d+) life")
    lose_amount = _first_number(oracle, r"lose (\d+) life")
    source_card = state.cards.get(source_card_id)
    if source_card is not None:
        if event == "life_paid":
            counter_match = re.search(
                r"whenever you pay life, put that many ([+\w/-]+) counters? on this (?:creature|artifact|enchantment|permanent)",
                oracle,
            )
            if counter_match:
                return {
                    "source_card_id": source_card_id,
                    "controller": controller,
                    "label": default_label,
                    "effect_key": "add_counters",
                    "payload": {
                        "target_card_id": source_card_id,
                        "counter": counter_match.group(1),
                        "amount": int(payload.get("amount", 0)),
                    },
                }
        source_name = re.escape((source_card.name or "").lower())
        if event == "enters_battlefield" and re.search(
            rf"\bwhen (?:this (?:creature|permanent|artifact|enchantment)|{source_name}) enters(?: the battlefield)?, exile all graveyards\b",
            oracle,
        ):
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "exile_all_graveyards",
                "payload": {},
            }
        if event in {"spell_cast", "spell_copy"} and "when you cast this spell" in oracle and "gain half x life" in oracle and "draw half x cards" in oracle:
            raw_x = payload.get("x_value", payload.get("stack_payload", {}).get("x_value", 0))
            try:
                half_x = max(0, int(raw_x or 0)) // 2
            except (TypeError, ValueError):
                half_x = 0
            effects = []
            if half_x:
                effects.extend(
                    [
                        {"effect_key": "gain_life", "payload": {"target_player": controller, "amount": half_x}},
                        {"effect_key": "draw_cards", "payload": {"target_player": controller, "amount": half_x}},
                    ]
                )
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "effect_sequence",
                "payload": {"effects": effects},
            }
        if event == "enters_battlefield" and ("when this creature enters the battlefield" in oracle or "when this creature enters," in oracle) and "cast target instant card from your graveyard" in oracle:
            target = next(
                (
                    cid
                    for cid in state.players[controller].graveyard
                    if cid in state.cards and "Instant" in (state.cards[cid].types or [])
                ),
                None,
            )
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "cast_from_graveyard",
                "payload": {"target_card_id": target},
            }
        if (
            event == "creature_dies"
            and "when this creature dies" in oracle
            and "deals damage equal to its power" in oracle
        ):
            amount = int(payload["power"] if "power" in payload else getattr(source_card, "power", 0) or 0)
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "deal_damage",
                "payload": {"target_player": opponent, "amount": max(0, amount)},
            }
        if event == "begin_step" and "transform" in oracle and "top card" in oracle and "instant or sorcery" in oracle:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "transform_if_top_matches",
                "payload": {"target_card_id": source_card_id, "required_types": ["Instant", "Sorcery"], "face_index": 1},
            }
        source_name = re.escape((source_card.name or "").lower())
        self_counter = re.search(
            rf"put\s+(a|an|one|two|three|four|five|\d+)\s+\+1/\+1\s+counters?\s+on\s+(?:this creature|this card|{source_name})",
            oracle,
        )
        if self_counter:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "add_counters",
                "payload": _maybe_payload(
                    oracle,
                    {
                        "target_card_id": source_card_id,
                        "counter": "+1/+1",
                        "amount": _number_token(self_counter.group(1)),
                    },
                ),
            }
    if event == "draw_card":
        drawn_by = int(payload.get("player_id", 0) or 0)
        if drawn_by == controller and "whenever you draw a card" in oracle and gain_amount > 0:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "gain_life",
                "payload": _maybe_payload(oracle, {"target_player": controller, "amount": gain_amount}),
            }
        if drawn_by != controller and "whenever an opponent draws a card" in oracle and lose_amount > 0:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "lose_life",
                "payload": _maybe_payload(oracle, {"target_player": drawn_by, "amount": lose_amount}),
            }

    if "draw a card" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "draw_cards",
            "payload": _maybe_payload(oracle, {"amount": 1}),
        }
    if "gain 1 life" in oracle or "gain life" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "gain_life",
            "payload": _maybe_payload(oracle, {"amount": gain_amount or 1}),
        }
    if "deals 1 damage" in oracle or "deal 1 damage" in oracle:
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "deal_damage",
            "payload": _maybe_payload(oracle, {"target_player": opponent, "amount": 1}),
        }
    if any(
        token in oracle
        for token in (
            "create ",
            "destroy target",
            "exile target",
            "tap target",
            "untap target",
            "search your library",
            "discard",
            "sacrifice",
            "return target",
            "add ",
            "lose ",
            "loses ",
            "counter target",
            "cast target",
            "reveals the top card",
        )
    ):
        from rules_engine.ability_model import build_ability_spec

        source_card = state.cards.get(source_card_id)
        if source_card is not None:
            parser_payload = dict(payload)
            # Cycle triggers need the permanent that owns the trigger as the
            # token/effect source. Other event payloads already use
            # source_card_id for the spell or permanent that caused the event.
            if event == "cycle":
                parser_payload["source_card_id"] = source_card_id
            ability = build_ability_spec(state, source_card, controller, action_targets=parser_payload)
            effect_key, effect_payload = ability.effect.key, ability.effect.payload
            if effect_key and effect_key != "noop":
                return {
                    "source_card_id": source_card_id,
                    "controller": controller,
                    "label": default_label,
                    "effect_key": effect_key,
                    "payload": _maybe_payload(oracle, effect_payload),
                }
    return {
        "source_card_id": source_card_id,
        "controller": controller,
        "label": default_label,
        "effect_key": "noop",
        "payload": {},
    }


def _first_number(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except Exception:
        return 0


def _number_token(token: str) -> int:
    values = {
        "a": 1,
        "an": 1,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }
    raw = str(token or "").lower()
    return values.get(raw, int(raw) if raw.isdigit() else 1)


def _maybe_payload(oracle: str, payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    low = (oracle or "").lower()
    if "you may" not in low:
        return out
    out["__may"] = True
    # Conservative default: skip optional effects that only lose life; otherwise choose yes.
    if "lose life" in low and "gain life" not in low and "draw" not in low:
        out["__may_choose"] = False
    else:
        out["__may_choose"] = True
    return out
