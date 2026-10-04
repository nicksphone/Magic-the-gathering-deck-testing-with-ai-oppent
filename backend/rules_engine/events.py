from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from copy import copy
from typing import Any

from game_state.state import MatchState, StackItem, Zone, object_incarnation
from rules_engine.card_types import is_token_card
from rules_engine.oracle_text import without_reminder_text


TRANSFORM_DRAW_RE = re.compile(
    r"whenever a permanent you control transforms or a permanent enters the battlefield under your control transformed,\s*"
    r"you may draw a card\.\s*do this only once each turn",
    re.IGNORECASE,
)
TEAM_COUNTER_RE = re.compile(r"\bput a (\+\d+/\+\d+) counter on each creature you control\b")
TRIBAL_GROUP_ENTRY_RE = re.compile(
    r"\bwhenever one or more (other )?([a-z-]+) "
    r"(?:you control enter(?: the battlefield)?|enter(?: the battlefield)? under your control)\b",
    re.IGNORECASE,
)
ATTACK_REWARD_RE = re.compile(
    r"at the beginning of your end step, put (a|an|one|two|three|four|five|\d+) "
    r"([a-z-]+) counters? on this (?:creature|artifact|enchantment|permanent)\. "
    r"if you attacked with (a|an|one|two|three|four|five|\d+) or more creatures this turn, "
    r"draw a card\. otherwise, (create [^.]+\.) then if this "
    r"(?:creature|artifact|enchantment|permanent) has (a|an|one|two|three|four|five|\d+) "
    r"or more \2 counters on it, transform it\.",
    re.IGNORECASE,
)


def capture_last_known_battlefield(state: MatchState, card_id: str) -> None:
    card = state.cards.get(card_id)
    if card is None or card.zone != Zone.BATTLEFIELD:
        return
    from rules_engine.continuous import effective_keyword_counts, effective_power, effective_toughness, printed_abilities_suppressed
    from rules_engine.colors import card_color_names, card_color_symbols
    keyword_counts = effective_keyword_counts(state, card_id)
    card.last_known_battlefield = {
        "name": card.name,
        "oracle_text": card.oracle_text,
        "types": list(effective_types(state, card)),
        "controller": card.controller,
        "power": effective_power(state, card_id),
        "toughness": effective_toughness(state, card_id),
        "keywords": list(keyword_counts),
        "keyword_counts": keyword_counts,
        "counters": dict(card.counters),
        "colors": sorted(card_color_symbols(card)),
        "color_names": sorted(card_color_names(card)),
        "selected_face_index": card.selected_face_index,
        "battlefield_incarnation": object_incarnation(card),
        "effect_timestamp": card.effect_timestamp,
        "was_kicked": card.was_kicked,
        "printed_abilities_suppressed": printed_abilities_suppressed(state, card_id),
    }
    for item in state.stack:
        if item.source_card_id == card_id:
            item.payload.setdefault("__source_lki", dict(card.last_known_battlefield))


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
    if event in {'leaves_battlefield', 'enters_battlefield', 'spell_cast', 'discard', 'creature_dies', 'permanent_dies'}:
        from game_state.observations import observe_cards
        observe_cards(state, [payload.get('card_id')])
    if event == "leaves_battlefield":
        capture_last_known_battlefield(state, payload.get("card_id"))
        _record_departure(state, payload)
    triggers = _collect_triggers(state, event, payload)
    _push_triggers(state, event, triggers)
    if event == "leaves_battlefield":
        _finish_battlefield_exit(state, payload.get("card_id"))
    elif event in {"permanent_dies", "creature_dies"}:
        _finish_death_event(state, event, payload.get("card_id"))


def emit_event_batch(state: MatchState, event: str, payloads: list[dict[str, Any]]) -> None:
    """Collect simultaneous events before putting their triggers on the stack."""
    if event in {'leaves_battlefield', 'enters_battlefield', 'spell_cast', 'discard', 'creature_dies', 'permanent_dies'}:
        from game_state.observations import observe_cards
        observe_cards(state, [payload.get('card_id') for payload in payloads])
    triggers: list[dict[str, Any]] = []
    one_or_more_sources: set[str] = set()
    if event == "leaves_battlefield":
        for payload in payloads:
            capture_last_known_battlefield(state, payload.get("card_id"))
            _record_departure(state, payload)
    departed_ids = [payload["card_id"] for payload in payloads if payload.get("card_id")] if event in {"permanent_dies", "creature_dies", "sacrifice"} else []
    for payload in payloads:
        event_payload = {**payload, "__simultaneous_source_ids": departed_ids} if departed_ids else payload
        for trigger in _collect_triggers(state, event, event_payload):
            source_id = str(trigger.get("source_card_id", ""))
            source = _departed_card_view(state, source_id)
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


def _record_departure(state, payload):
    card = state.cards.get(payload.get('card_id'))
    if card is not None and payload.get('controller') in state.players:
        state.players_with_permanent_departure.add(payload['controller'])


def _finish_death_event(state: MatchState, event: str, card_id: str | None) -> None:
    card = state.cards.get(card_id) if card_id else None
    if card and card.zone == Zone.GRAVEYARD and (event == "creature_dies" or not was_creature_on_battlefield(card)):
        card.reset_zone_counters(Zone.GRAVEYARD)


def _finish_battlefield_exit(state: MatchState, card_id: str | None) -> None:
    card = state.cards.get(card_id) if card_id else None
    if card is None:
        return
    from rules_engine.type_effects import clear_type_effects
    clear_type_effects(card)
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
    # Choosing a trigger's targets can itself trigger ward. Put that next wave
    # above the targeted ability before returning priority, not on a later pass.
    while state.trigger_staging and not state.pending_replacement_choice and not state.pending_trigger_order:
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
        else:
            choice_players = set(state.trigger_order_choice_players or set())
            human_order = state.trigger_order_choice_required and (not choice_players or controller in choice_players)
            if not human_order:
                from ai.trigger_policy import preferred_trigger_order
                group = preferred_trigger_order(group, controller)
        ordered.extend(group)
    target_stack_ids: list[str] = []
    targeted_items = []
    for order_index, trig in enumerate(ordered):
        payload = dict(trig["payload"])
        if trig["effect_key"] == "ward_payment":
            source = state.cards.get(trig["source_card_id"])
            lki = source.last_known_battlefield if source else {}
            if lki.get("battlefield_incarnation") == payload.get("ward_incarnation"):
                payload.setdefault("__source_lki", dict(lki))
        item = StackItem(
            id=state.allocate_object_id(),
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
            item.payload.pop("target_player", None)
            item.payload.pop("target_card_id", None)
            choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
            if getattr(state, "trigger_order_choice_required", False) and (not choice_players or item.controller in choice_players):
                target_stack_ids.append(item.id)
            else:
                # Non-human controllers still need a legal target at stack entry.
                # Destructive effects prefer an opponent's permanent over their own.
                if item.effect_key in {"destroy_permanent", "destroy", "exile", "exile_permanent"}:
                    options.sort(key=lambda option: state.cards[option["target_card_id"]].controller == item.controller)
                if item.payload.get("__targeted_life_loss"):
                    options.sort(key=lambda option: option["target_player"] == item.controller)
                if item.effect_key == 'cast_from_graveyard':
                    from ai.effect_cast_policy import preferred_graveyard_spell
                    choice = preferred_graveyard_spell(state, item.controller, options)
                elif item.effect_key == "deal_damage":
                    from ai.heuristics import choose_damage_trigger_target
                    choice = choose_damage_trigger_target(state, item.controller, int(item.payload.get("amount", 0)), options)
                else:
                    choice = options[0]
                item.payload.update({key: choice[key] for key in ("target_card_id", "target_player") if key in choice})
                item.payload["__trigger_target_choice"] = True
        state.stack.append(item)
        if item.payload.get("__trigger_target_choice"):
            from rules_engine.flashback_grants import remember_target
            remember_target(state, item)
            targeted_items.append(item)
    if targeted_items:
        from rules_engine.ward import mark_stack_targets
        state.trigger_staging = True
        state.trigger_staging_event = "becomes_target"
        for item in targeted_items:
            mark_stack_targets(state, item)
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
    if item.payload.get('__trigger_resolution_text'):
        return item.payload['__trigger_full_clause']
    event = item.payload.get("__trigger_event")
    if event == 'saga_lore_added':
        clause = item.payload.get('__chapter_clause', '')
        if (item.effect_key == 'deal_damage' and 'any target' in clause.lower()
                or re.search(r'\btarget (?:artifact or enchantment|creature|artifact|enchantment|nonland permanent|permanent)\b', clause, re.I)
                and item.effect_key in {'destroy_permanent', 'destroy', 'exile', 'exile_permanent',
                                       'tap', 'untap', 'return_permanent_to_hand', 'add_counters', 'deal_damage'}):
            return clause
        return None
    patterns = {
        "enters_battlefield": r"^(?:when|whenever)\b.*\benters\b",
        "spell_cast": r"^when you cast this spell\b",
        "sacrifice": r"^(?:when|whenever)\b.*\bsacrific(?:e|es|ed)\b",
        "creature_dies": r"^(?:when|whenever)\b.*\bdies\b",
        "permanent_dies": r"^(?:when|whenever)\b.*\bput into a graveyard from the battlefield\b",
    }
    if event not in patterns or item.payload.get("__trigger_target_clause"):
        return None
    card = _departed_card_view(state, item.source_card_id)
    if not card:
        return None
    for sentence in re.split(r"(?<=\.)\s+|\n", card.oracle_text or ""):
        clause = sentence.strip()
        if not re.match(patterns[event], clause, re.I):
            continue
        if item.effect_key == 'grant_flashback' and re.search(r'target instant or sorcery card in your graveyard gains flashback', clause, re.I):
            return clause
        if item.effect_key == 'cast_from_graveyard' and re.search(r'cast target (?:instant|sorcery) card from your graveyard', clause, re.I):
            return clause
        if item.effect_key == "deal_damage" and "any target" in clause.lower():
            return clause
        if item.payload.get("__targeted_life_loss") and re.search(r"\btarget (?:player|opponent) loses \d+ life\b", clause, re.I):
            return clause
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
    lki = item.payload.get('__source_lki')
    if lki:
        proxy.types = list(lki['types'])
        proxy.colors = list(lki.get('colors', []))
        proxy.card_faces = []
    proxy.oracle_text = clause
    hints = inspect_target_hints(state, proxy, item.controller)
    low = clause.lower()
    if item.effect_key in {'cast_from_graveyard', 'grant_flashback'}:
        return [{'target_card_id': target['id'], 'target_name': target['name']}
                for target in hints.get('graveyard_spell_targets', [])]
    if item.payload.get("__targeted_life_loss"):
        return [
            {"target_player": pid, "target_name": player.name}
            for pid, player in state.players.items()
            if (not item.payload.get("__target_opponent_only") or pid != item.controller)
            and validate_hexproof_shroud_targets(state, item.controller, {"target_player": pid})[0]
        ]
    if "any target" in low and item.effect_key == "deal_damage":
        options = [
            {"target_player": pid, "target_name": state.players[pid].name}
            for pid in state.players
            if validate_hexproof_shroud_targets(state, item.controller, {"target_player": pid})[0]
        ]
        for player in state.players.values():
            for cid in player.battlefield:
                target = state.cards[cid]
                if not {"Creature", "Planeswalker"}.intersection(effective_types(state, target)):
                    continue
                choice = {"target_card_id": cid}
                if validate_protection_targets(state, proxy, choice)[0] and validate_hexproof_shroud_targets(state, item.controller, choice, proxy)[0]:
                    options.append({**choice, "target_name": target.name})
        return options
    if "target artifact or enchantment" in low:
        key = "noncreature_permanent_targets"
    elif "target nonland permanent" in low or "target permanent" in low or "target noncreature permanent" in low:
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
        if validate_protection_targets(state, proxy, choice)[0] and validate_hexproof_shroud_targets(state, item.controller, choice, proxy)[0]:
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


def resume_trigger_target(state: MatchState, stack_id: str, target_card_id: str | None = None, target_player: int | None = None) -> bool:
    pending = state.pending_trigger_order or {}
    if pending.get("phase") != "targets" or pending.get("current_stack_id") != stack_id:
        return False
    item = next((item for item in state.stack if item.id == stack_id), None)
    if not item or (target_card_id is None) == (target_player is None):
        return False
    choice = next((option for option in trigger_target_options(state, item)
                   if option.get("target_card_id") == target_card_id and option.get("target_player") == target_player), None)
    if choice is None:
        return False
    item.payload.pop("target_card_id", None)
    item.payload.pop("target_player", None)
    item.payload.update({key: choice[key] for key in ("target_card_id", "target_player") if key in choice})
    item.payload["__trigger_target_choice"] = True
    from rules_engine.flashback_grants import remember_target
    remember_target(state, item)
    from rules_engine.ward import mark_stack_targets
    if not state.trigger_staging:
        state.trigger_staging = True
        state.trigger_staging_event = "becomes_target"
    mark_stack_targets(state, item)
    state.log.append(f"{state.players[item.controller].name} targets {choice['target_name']} with {item.label}.")
    _advance_trigger_target(state, str(pending["event"]), list(pending["stack_ids"])[1:])
    return True


def _collect_triggers(state: MatchState, event: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    from rules_engine.continuous import printed_abilities_suppressed
    from rules_engine.keyword_triggers import collect_keyword_triggers
    out: list[dict[str, Any]] = collect_keyword_triggers(state, event, payload)
    from rules_engine.foretell import collect_foretell_triggers
    out.extend(collect_foretell_triggers(state, event, payload))
    if event == 'damage_dealt':
        return out
    if event == 'surveilled':
        player_id = payload.get('player_id')
        if player_id not in state.players or payload.get('amount', 0) <= 0:
            return out
        state.surveils_this_turn[player_id] = state.surveils_this_turn.get(player_id, 0) + 1
    if event == 'saga_lore_added':
        from rules_engine.ability_model import build_ability_spec
        from rules_engine.oracle_effects import extract_saga_chapters
        saga = state.cards.get(payload.get('card_id'))
        if saga is None or saga.zone != Zone.BATTLEFIELD or 'Saga' not in saga.type_line:
            return out
        if printed_abilities_suppressed(state, saga.id):
            return out
        state.log.append(f"{saga.name} gets lore counters ({payload['new_lore']}).")
        for chapter in extract_saga_chapters(saga.oracle_text):
            if not payload['old_lore'] < chapter['number'] <= payload['new_lore']:
                continue
            if (saga.entered_turn == state.turn
                    and re.search(r'^read ahead\s*$', without_reminder_text(saga.oracle_text), re.I | re.M)
                    and chapter['number'] != payload['new_lore']):
                continue
            proxy = copy(saga)
            proxy.oracle_text = chapter['text']
            proxy.mana_cost = ''
            ability = build_ability_spec(state, proxy, saga.controller,
                                        action_targets={'source_card_id': saga.id, 'target_card_id': saga.id})
            out.append({'source_card_id': saga.id, 'controller': saga.controller,
                        'label': f"{saga.name} chapter {chapter['number']}",
                        'effect_key': ability.effect.key,
                        'payload': {**ability.effect.payload, '__chapter_number': chapter['number'],
                                    '__chapter_clause': chapter['text'],
                                    '__chapter_incarnation': object_incarnation(saga)}})
        return out
    if event == "attack_declared":
        attacker = state.cards.get(payload.get("card_id"))
        if attacker:
            from rules_engine.continuous import effective_power, has_keyword

            if attacker.id in state.attackers and has_keyword(state, attacker.id, "training"):
                power = effective_power(state, attacker.id)
                if any(
                    other_id != attacker.id
                    and state.cards[other_id].controller == attacker.controller
                    and effective_power(state, other_id) > power
                    for other_id in state.attackers
                ):
                    out.append({
                        "source_card_id": attacker.id, "controller": attacker.controller,
                        "label": f"{attacker.name} training", "effect_key": "add_counters",
                        "payload": {"target_card_id": attacker.id, "counter": "+1/+1", "amount": 1,
                                    "effect_timestamp": object_incarnation(attacker)},
                    })
            attack_oracle = '' if printed_abilities_suppressed(state, attacker.id) else attacker.oracle_text or ''
            for amount in re.findall(r"\bannihilator\s+(\d+)", without_reminder_text(attack_oracle), re.IGNORECASE):
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
        source_ids = list(pstate.battlefield)
        if event in {"permanent_dies", "creature_dies", "sacrifice"}:
            departed_ids = payload.get("__simultaneous_source_ids", [payload.get("card_id")])
            source_ids.extend(
                cid for cid in departed_ids
                if cid in state.cards
                and state.cards[cid].zone != Zone.BATTLEFIELD
                and state.cards[cid].last_known_battlefield
                and state.cards[cid].last_known_battlefield["controller"] == pid
            )
        for cid in dict.fromkeys(source_ids):
            card = _departed_card_view(state, cid)
            if (printed_abilities_suppressed(state, cid) if card.zone == Zone.BATTLEFIELD
                    else card.last_known_battlefield.get('printed_abilities_suppressed', False)):
                continue
            oracle = without_reminder_text((card.oracle_text or "").lower())
            from rules_engine.foretell import without_created_clauses
            oracle = without_created_clauses(oracle, card.name.lower())
            from rules_engine.kicker import kicked_cast_clauses
            kicker_clauses = kicked_cast_clauses(oracle)
            if (event == 'spell_cast' and payload.get('controller') == card.controller
                    and (payload.get('stack_payload') or {}).get('__kicked')):
                from rules_engine.oracle_effects import infer_effect_from_oracle
                for clause in kicker_clauses:
                    proxy = copy(card)
                    proxy.oracle_text, proxy.card_faces, proxy.types = clause['instruction'], [], []
                    stats = re.fullmatch(r'this creature has base power and toughness (\d+)/(\d+) until end of turn\.', clause['instruction'])
                    if stats:
                        key, data = 'set_base_stats', {'target_card_id': cid, 'base_power': int(stats[1]), 'base_toughness': int(stats[2])}
                    elif clause['instruction'].startswith('put '):
                        from rules_engine.spell_cost_clauses import NUMBERS
                        count = clause['instruction'].split()[1]
                        key, data = 'add_counters', {'target_card_id': cid, 'counter': '+1/+1',
                                                    'amount': int(count) if count.isdigit() else NUMBERS[count]}
                    else:
                        key, data = infer_effect_from_oracle(state, proxy, card.controller)
                    if key in {'add_counters', 'set_base_stats'}:
                        data['effect_timestamp'] = object_incarnation(card)
                    out.append({'source_card_id': cid, 'controller': card.controller,
                                'label': f'{card.name} kicked-cast trigger', 'effect_key': key, 'payload': data})
            oracle = '\n'.join(line for line in oracle.splitlines()
                               if line.strip() not in {entry['clause'] for entry in kicker_clauses})
            transform_draw = bool(TRANSFORM_DRAW_RE.search(oracle))
            once_each_turn = ("only once each turn" in oracle or "this ability triggers only once each turn" in oracle)
            if transform_draw and event in {"transformed", "enters_battlefield"}:
                once_each_turn = False
            trigger_key = f"{cid}:{object_incarnation(card)}:{event}"
            if once_each_turn and trigger_key in state.trigger_once_seen_this_turn:
                continue
            trigger_count_before = len(out)

            from rules_engine.player_counters import gain_triggers
            counter_triggers, oracle = gain_triggers(state, card, event, payload, oracle)
            out.extend(counter_triggers)

            if transform_draw and event in {"transformed", "enters_battlefield"}:
                changed = state.cards.get(payload.get("card_id"))
                transformed_entry = (
                    event == "enters_battlefield" and changed is not None
                    and changed.layout in {"transform", "double_faced_token"}
                    and changed.selected_face_index == 1
                )
                if (changed is not None and changed.controller == card.controller
                        and (event == "transformed" or transformed_entry)):
                    choice_key = f"{cid}:{object_incarnation(card)}:transform_draw"
                    if choice_key not in state.trigger_once_seen_this_turn:
                        out.append({
                            "source_card_id": cid, "controller": card.controller,
                            "label": f"{card.name} transform draw", "effect_key": "draw_cards",
                            "payload": {"target_player": card.controller, "amount": 1,
                                        "__may": True, "__may_choose": True,
                                        "__once_on_accept": choice_key},
                        })
                if event == "enters_battlefield":
                    oracle = TRANSFORM_DRAW_RE.sub("", oracle)

            if event == 'surveilled' and payload.get('player_id') == card.controller:
                from rules_engine.scry import surveil_payoff
                for line in oracle.splitlines():
                    payoff = surveil_payoff(line)
                    if not payoff:
                        continue
                    if payoff['once'] and state.surveils_this_turn[card.controller] != 1:
                        continue
                    if payoff['kind'] == 'counter':
                        key, data = 'add_counters', {'target_card_id': cid, 'counter': '+1/+1',
                            'amount': payoff['amount'], 'effect_timestamp': object_incarnation(card)}
                    elif payoff['kind'] == 'return':
                        key, data = 'return_permanent_to_hand', {'target_card_id': cid,
                            'effect_timestamp': object_incarnation(card)}
                    else:
                        key, data = 'effect_sequence', {'effects': [
                            {'effect_key': 'deal_damage', 'payload': {'target_player': 3-card.controller, 'amount': payoff['damage']}},
                            {'effect_key': 'gain_life', 'payload': {'amount': payoff['life']}},
                        ]}
                    out.append({'source_card_id': cid, 'controller': card.controller,
                                'label': f'{card.name} surveil trigger', 'effect_key': key, 'payload': data})
            elif event == 'proliferated' and payload.get('controller') == card.controller:
                for line in oracle.splitlines():
                    if re.fullmatch(r'whenever you proliferate, [^.]+\.', line.strip()):
                        out.append(_trigger_from_oracle(state, cid, card.controller, line.strip(),
                                   default_label=f'{card.name} proliferate trigger', event=event, payload=payload))
            elif event == "draw_card" and payload.get("player_id") == card.controller and "whenever you draw a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "draw_card" and payload.get("player_id") != card.controller and "whenever an opponent draws a card" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "life_gain" and payload.get("player_id") == card.controller and "whenever you gain life" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "life_paid" and payload.get("player_id") == card.controller and "whenever you pay life" in oracle:
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "creature_dies" and _matches_creature_dies_trigger(state, card, oracle, payload):
                death_payload = payload
                if cid == payload.get("card_id") and "power" not in payload and card.last_known_battlefield:
                    death_payload = {**payload, "power": card.last_known_battlefield["power"]}
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=death_payload))
            elif (event == 'permanent_dies' and cid == payload.get('card_id')
                  and any(re.fullmatch(
                      r"when (?:" + re.escape(card.name.lower())
                      + r"|this (?:aura|artifact|enchantment|creature|permanent))"
                      + r" is put into a graveyard from the battlefield, return (?:"
                      + re.escape(card.name.lower()) + r"|it) to its owner's hand\.",
                      line.strip()) for line in oracle.splitlines())):
                departed = state.cards[cid]
                out.append({
                    'source_card_id': cid, 'controller': card.controller,
                    'label': f'{card.name} graveyard return trigger',
                    'effect_key': 'return_from_graveyard',
                    'payload': {'target_card_id': cid, 'target_player': departed.owner,
                                '__graveyard_reference': {
                                    'incarnation': object_incarnation(departed),
                                    'zone_sequence': departed.zone_change_sequence}},
                })
            elif event == "permanent_dies" and _matches_permanent_dies_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "leaves_battlefield" and _matches_leaves_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "day_night_changed" and _matches_day_night_trigger(oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} trigger", event=event, payload=payload))
            elif event == "enters_battlefield" and _matches_enters_battlefield_trigger(state, card, oracle, payload):
                out.append(_trigger_from_oracle(state, cid, card.controller, oracle, default_label=f"{card.name} ETB", event=event, payload=payload))
            elif event == "transformed" and payload.get("card_id") in state.cards:
                transformed = state.cards[payload["card_id"]]
                counter_trigger = re.search(
                    r"whenever a permanent you control transforms into an? ([a-z-]+), put a \+1/\+1 counter on it",
                    oracle,
                )
                subtype_text = re.split(r"\s+[—–-]\s+", transformed.type_line or "", maxsplit=1)
                if (counter_trigger and transformed.controller == card.controller
                        and len(subtype_text) == 2
                        and counter_trigger.group(1) in subtype_text[1].lower().split()):
                    out.append({
                        "source_card_id": cid, "controller": card.controller,
                        "label": f"{card.name} transform trigger", "effect_key": "add_counters",
                        "payload": {"target_card_id": transformed.id, "counter": "+1/+1", "amount": 1},
                    })
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
                source_types = {t.lower() for t in (effective_types(state, source_card) or [])}
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
            if once_each_turn and len(out) > trigger_count_before:
                state.trigger_once_seen_this_turn.add(trigger_key)
    out.sort(key=lambda trig: (0 if trig["controller"] == state.active_player else 1, str(trig["source_card_id"]), str(trig["label"])))
    return out


def _creature_self_reference(card, oracle: str) -> str:
    name = (getattr(card, "name", "") or "").lower()
    return re.sub(rf"\b{re.escape(name)}\b", "this creature", oracle) if name else oracle


def _matches_creature_dies_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    oracle = _creature_self_reference(card, oracle)
    if "\n" in oracle:
        return any(_matches_creature_dies_trigger(state, card, line.strip(), payload) for line in oracle.splitlines())
    dead_id = payload.get("card_id")
    dead_card = _departed_card_view(state, dead_id)
    dead_types = set(effective_types(state, dead_card) or []) if dead_card else set()
    if "whenever this creature or another creature dies" in oracle:
        return "Creature" in dead_types
    if "whenever this creature or another creature you control dies" in oracle:
        return bool(dead_card) and "Creature" in dead_types and (dead_id == card.id or dead_card.controller == card.controller)
    if "whenever a creature an opponent controls dies" in oracle:
        return bool(dead_card) and dead_card.controller != card.controller and "Creature" in dead_types
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
    if "whenever another nontoken creature dies" in oracle:
        return dead_id != card.id and "Creature" in dead_types and not is_token_card(dead_card)
    if "whenever another creature dies" in oracle:
        return dead_id != card.id
    if "whenever a nontoken creature dies" in oracle:
        return "Creature" in dead_types and not is_token_card(dead_card)
    if "whenever a creature dies" in oracle:
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
    if "whenever an artifact you control is put into a graveyard from the battlefield" in oracle:
        return (
            "target opponent loses life equal to this creature's power" in oracle
            and dead_card.controller == card.controller
            and "Artifact" in (effective_types(state, dead_card) or [])
        )
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
        return "Artifact" in (effective_types(state, dead_card) or [])
    if "whenever an artifact you control dies" in oracle or "whenever another artifact you control dies" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (effective_types(state, dead_card) or [])
    if "whenever one or more artifacts you control die" in oracle:
        return dead_card.controller == card.controller and "Artifact" in (effective_types(state, dead_card) or [])
    if "whenever an enchantment dies" in oracle or "whenever another enchantment dies" in oracle:
        return "Enchantment" in (effective_types(state, dead_card) or [])
    if "whenever an enchantment you control dies" in oracle or "whenever another enchantment you control dies" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (effective_types(state, dead_card) or [])
    if "whenever one or more enchantments you control die" in oracle:
        return dead_card.controller == card.controller and "Enchantment" in (effective_types(state, dead_card) or [])
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
    leaving_types = {str(value).lower() for value in (effective_types(state, leaving) or [])}
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
    # Granted token abilities are not entry abilities of their creator. Keep
    # original text for effect parsing; only the match surface excludes quotes.
    oracle = re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', '', oracle)
    if re.search(r'\bif it was kicked\b', oracle, re.I) and not getattr(card, 'was_kicked', False):
        return False
    # Modern Oracle abbreviates battlefield entry to "enters".
    oracle = re.sub(r"\benters\b(?! the battlefield)", "enters the battlefield", oracle)
    entering_id = payload.get("card_id")
    if not entering_id or entering_id not in state.cards:
        return False
    entering_card = state.cards[entering_id]
    tribal_group = TRIBAL_GROUP_ENTRY_RE.search(oracle)
    if tribal_group:
        from rules_engine.card_types import creature_subtype_candidates
        from rules_engine.library_permissions import creature_types

        subtypes = creature_subtype_candidates(tribal_group.group(2))
        return (
            entering_card.controller == card.controller
            and (not tribal_group.group(1) or entering_id != card.id)
            and "Creature" in (effective_types(state, entering_card) or [])
            and (bool(subtypes & creature_types(entering_card))
                 or "changeling" in {keyword.lower() for keyword in (entering_card.keywords or [])})
        )
    # Check controller-scoped clauses before their broader prefixes. Without
    # this ordering, "a creature enters" also matches "under your control".
    entering_types = set(effective_types(state, entering_card) or [])
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
    self_names = {card.name.lower(), card.name.split(",", 1)[0].lower()}
    if any(f"when {name} enters the battlefield" in oracle for name in self_names):
        return entering_id == card.id
    if any(f"when this {subject} enters the battlefield" in oracle for subject in
           ("creature", "permanent", "artifact", "enchantment", "planeswalker",
            "aura", "equipment", "vehicle", "land", "battle", "token")):
        return entering_id == card.id
    if "whenever another creature enters the battlefield" in oracle:
        return "Creature" in (effective_types(state, entering_card) or []) and entering_id != card.id
    if "whenever a creature enters the battlefield" in oracle:
        return "Creature" in (effective_types(state, entering_card) or [])
    if "whenever a creature enters the battlefield under your control" in oracle:
        return "Creature" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield" in oracle:
        return entering_id != card.id
    if "whenever a permanent enters the battlefield" in oracle:
        return True
    if "whenever a permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller
    if "whenever another permanent enters the battlefield under your control" in oracle:
        return entering_card.controller == card.controller and entering_id != card.id
    if "whenever an artifact enters the battlefield" in oracle:
        return "Artifact" in (effective_types(state, entering_card) or [])
    if "whenever an artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller
    if "whenever another artifact enters the battlefield" in oracle:
        return "Artifact" in (effective_types(state, entering_card) or []) and entering_id != card.id
    if "whenever another artifact enters the battlefield under your control" in oracle:
        return "Artifact" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever an enchantment enters the battlefield" in oracle:
        return "Enchantment" in (effective_types(state, entering_card) or [])
    if "whenever an enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller
    if "whenever another enchantment enters the battlefield" in oracle:
        return "Enchantment" in (effective_types(state, entering_card) or []) and entering_id != card.id
    if "whenever another enchantment enters the battlefield under your control" in oracle:
        return "Enchantment" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller and entering_id != card.id
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
        return "Land" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller
    if "whenever a land enters the battlefield under your control" in oracle:
        return "Land" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller
    if "whenever another land enters the battlefield under your control" in oracle:
        return "Land" in (effective_types(state, entering_card) or []) and entering_card.controller == card.controller and entering_id != card.id
    if "whenever a land enters the battlefield" in oracle:
        return "Land" in (effective_types(state, entering_card) or [])
    return False


def _has_artifact_or_enchantment_type(card) -> bool:
    types = {str(t).lower() for t in (getattr(card, "types", []) or [])}
    return "artifact" in types or "enchantment" in types


def _matches_sacrifice_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    sac_id = payload.get("card_id")
    if not sac_id or sac_id not in state.cards:
        return False
    sac_card = state.cards[sac_id]
    if "whenever a player sacrifices another permanent" in oracle and TEAM_COUNTER_RE.search(oracle):
        return sac_id != card.id
    if "whenever a player sacrifices a permanent" in oracle and re.search(r"deals? \d+ damage to any target", oracle):
        return True
    if ("whenever a player sacrifices a permanent" in oracle
            and "put a +1/+1 counter on this creature" in oracle):
        return True
    if "whenever you sacrifice a permanent" in oracle:
        return sac_card.controller == card.controller
    if "whenever a permanent you control is sacrificed" in oracle or "whenever a permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller
    if "whenever you sacrifice a creature" in oracle:
        return sac_card.controller == card.controller and "Creature" in (effective_types(state, sac_card) or [])
    if "whenever a creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Creature" in (effective_types(state, sac_card) or [])
    if "whenever an artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Artifact" in (effective_types(state, sac_card) or [])
    if "whenever an enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and "Enchantment" in (effective_types(state, sac_card) or [])
    if "whenever an artifact or enchantment you control is sacrificed" in oracle or "whenever an enchantment or artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and _has_artifact_or_enchantment_type(sac_card)
    if "whenever a creature is sacrificed" in oracle:
        return "Creature" in (effective_types(state, sac_card) or [])
    if "whenever an artifact is sacrificed" in oracle:
        return "Artifact" in (effective_types(state, sac_card) or [])
    if "whenever an enchantment is sacrificed" in oracle:
        return "Enchantment" in (effective_types(state, sac_card) or [])
    if "whenever an artifact or enchantment is sacrificed" in oracle or "whenever an enchantment or artifact is sacrificed" in oracle:
        return _has_artifact_or_enchantment_type(sac_card)
    if "whenever a permanent is sacrificed" in oracle:
        return True
    if "whenever another permanent you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id
    if "whenever another creature you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Creature" in (effective_types(state, sac_card) or [])
    if "whenever another artifact you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Artifact" in (effective_types(state, sac_card) or [])
    if "whenever another enchantment you control is sacrificed" in oracle:
        return sac_card.controller == card.controller and sac_id != card.id and "Enchantment" in (effective_types(state, sac_card) or [])
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
            return "Creature" in (effective_types(state, source_card) or [])
    if target_card_id is not None:
        target_card = state.cards.get(target_card_id)
        if not target_card:
            return False
        if "deals combat damage to a creature" in oracle:
            return True
        if "whenever this creature deals combat damage to a creature" in oracle:
            return source_id == card.id
        if "whenever a creature you control deals combat damage to a creature" in oracle:
            return "Creature" in (effective_types(state, source_card) or [])
    return False


def _matches_attack_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    attacking_id = payload.get("card_id")
    if not attacking_id or attacking_id not in state.cards:
        return False
    attacking_card = state.cards[attacking_id]
    if attacking_card.controller != card.controller:
        return False
    if ("whenever you attack" in oracle or "whenever one or more creatures attack" in oracle) and not payload.get("attack_group_first", True):
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
        return attacking_card.controller == card.controller and "Creature" in (effective_types(state, attacking_card) or [])
    if "whenever you attack" in oracle:
        return attacking_card.controller == card.controller
    if "whenever one or more creatures attack" in oracle:
        return True
    return False


def _matches_block_trigger(state: MatchState, card, oracle: str, payload: dict[str, Any]) -> bool:
    if not payload.get('blocker_first_block', True) and 'blocks a creature' not in oracle:
        return False
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
        return "Creature" in (effective_types(state, blocker_card) or [])
    if "whenever another creature you control blocks" in oracle:
        return blocker_card.controller == card.controller and blocker_id != card.id and "Creature" in (effective_types(state, blocker_card) or [])
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
    source = state.cards.get(source_card_id)
    if event == 'enters_battlefield' and source is not None:
        from rules_engine.flashback_grants import grant_instruction
        for line in oracle.splitlines():
            entry = re.fullmatch(r'when (?:this (?:creature|artifact|enchantment|permanent|planeswalker|aura|equipment|vehicle|land|battle|token)|' + re.escape(source.name.lower())
                                 + r') enters(?: the battlefield)?, (.+)', line.strip().lower())
            if entry and grant_instruction(entry[1]) and _matches_enters_battlefield_trigger(state, source, line, payload):
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'grant_flashback', 'payload': {}}
        from rules_engine.keyword_triggers import next_turn_draw_instruction
        for line in oracle.splitlines():
            entry = re.fullmatch(r'(?:when|whenever) [^,]+, (.+)', line.strip(), re.I)
            instruction = next_turn_draw_instruction(entry[1]) if entry else None
            if instruction is not None and _matches_enters_battlefield_trigger(state, source, line, payload):
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'schedule_next_turn_draw',
                        'payload': {**instruction, 'source_card_id': source_card_id}}
        from rules_engine.devotion import devotion_instruction
        for line in oracle.splitlines():
            entry = re.fullmatch(r'when (?:this creature|' + re.escape(source.name.lower())
                                + r') enters(?: the battlefield)?, (.+)', line.strip().lower())
            devotion = devotion_instruction(entry[1], source.name) if entry else None
            if devotion is not None and _matches_enters_battlefield_trigger(state, source, line, payload):
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'devotion_effect',
                        'payload': {'devotion': devotion, 'source_incarnation': object_incarnation(source)}}
        from rules_engine.kicker import permanent_kicker
        kicker = permanent_kicker(source.oracle_text)
        if kicker and kicker.get('instruction'):
            from rules_engine.oracle_effects import infer_effect_from_oracle
            proxy = copy(source)
            proxy.oracle_text = kicker['instruction']
            proxy.card_faces = []
            proxy.types = []
            key, data = infer_effect_from_oracle(state, proxy, controller)
            if re.search(r'\btarget\b', kicker['instruction'], re.I):
                data.update(__trigger_resolution_text=kicker['instruction'],
                            __trigger_full_clause=kicker['clause'])
            return {'source_card_id': source_card_id, 'controller': controller,
                    'label': default_label, 'effect_key': key, 'payload': data}
    if event == 'spell_cast':
        from rules_engine.scry import cast_surveillance_clause
        for line in oracle.splitlines():
            amount = cast_surveillance_clause(line)
            if amount is not None:
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'surveil', 'payload': {'amount': amount}}
    matchers = {
        'enters_battlefield': _matches_enters_battlefield_trigger,
        'creature_dies': _matches_creature_dies_trigger,
        'combat_damage_dealt': _matches_combat_damage_trigger,
        'attack_declared': _matches_attack_trigger,
        'sacrifice': _matches_sacrifice_trigger,
    }
    if source:
        for line in oracle.splitlines():
            tap_loss = re.fullmatch(
                r'((?:when|whenever) [^,]+, (tap target creature(?: an opponent controls| you control)?\.'
                r' it loses all abilities until end of turn\.))', line.strip(),
            )
            if (tap_loss and event == 'enters_battlefield'
                    and _matches_enters_battlefield_trigger(state, source, line, payload)):
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'noop',
                        'payload': {'__trigger_resolution_text': tap_loss[2], '__trigger_full_clause': tap_loss[1]}}
            instruction = re.fullmatch(r'.+,\s*proliferate( twice)?\.', line.strip())
            if not instruction:
                continue
            matcher = matchers.get(event)
            matches = bool(matcher and matcher(state, source, line, payload))
            if event == 'spell_cast':
                matches = (payload.get('controller') == controller
                           and re.fullmatch(r'whenever you cast a spell, proliferate(?: twice)?\.', line.strip()))
            if matches:
                effects = [{'effect_key': 'proliferate', 'payload': {}} for _ in range(2 if instruction[1] else 1)]
                return {'source_card_id': source_card_id, 'controller': controller,
                        'label': default_label, 'effect_key': 'effect_sequence', 'payload': {'effects': effects}}
    if event in {"enters_battlefield", "creature_dies"}:
        matching_clauses = [
            line.strip() for line in oracle.splitlines()
            if (
                event == "enters_battlefield"
                and re.match(r"^(?:when|whenever)\b.*\benters?\b", line.strip())
            ) or (
                event == "creature_dies"
                and source_card_id in state.cards
                and _matches_creature_dies_trigger(state, state.cards[source_card_id], line.strip(), payload)
            )
        ]
        if len(matching_clauses) == 1:
            oracle = matching_clauses[0]
    opponent = 1 if controller == 2 else 2
    if event == 'draw_card':
        draw_mill = re.fullmatch(r'whenever you draw a card, (each opponent mills (?:one|two|three|four|five|six|seven|eight|nine|ten|\d+) cards?)\.', oracle.strip())
        if draw_mill:
            from rules_engine.oracle_effects import infer_effect_from_oracle
            proxy = copy(source)
            proxy.oracle_text = draw_mill[1]
            key, data = infer_effect_from_oracle(state, proxy, controller)
            return {'source_card_id': source_card_id, 'controller': controller,
                    'label': default_label, 'effect_key': key, 'payload': data}
    gain_amount = _first_number(oracle, r"gain (\d+) life")
    lose_amount = _first_number(oracle, r"lose (\d+) life")
    source_card = state.cards.get(source_card_id)
    if source_card is not None:
        if event == "begin_step" and payload.get("step") == "end_step":
            match = ATTACK_REWARD_RE.search(oracle)
            if match:
                from rules_engine.oracle_effects import infer_effect_from_oracle

                token_surface = copy(source_card)
                token_surface.oracle_text = match.group(4)
                token_surface.card_faces = []
                token_surface.selected_face_index = None
                token_surface.types = []
                token_key, token_payload = infer_effect_from_oracle(
                    state, token_surface, controller, report_unsupported=False,
                )
                if token_key == "create_token":
                    return {
                        "source_card_id": source_card_id,
                        "controller": controller,
                        "label": default_label,
                        "effect_key": "effect_sequence",
                        "payload": {"effects": [
                            {"effect_key": "add_counters", "payload": {
                                "target_card_id": source_card_id, "counter": match.group(2),
                                "amount": _number_token(match.group(1)),
                                "effect_timestamp": object_incarnation(source_card),
                            }},
                            {"effect_key": "attack_count_reward", "payload": {
                                "minimum_attackers": _number_token(match.group(3)),
                                "token_payload": token_payload,
                            }},
                            {"effect_key": "transform_if_counters", "payload": {
                                "target_card_id": source_card_id, "counter": match.group(2),
                                "minimum_counters": _number_token(match.group(5)),
                                "effect_timestamp": object_incarnation(source_card),
                            }},
                        ]},
                    }
        team_counter = TEAM_COUNTER_RE.search(oracle)
        if event == "sacrifice" and team_counter:
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "add_counters_each_creature",
                "payload": {"counter": team_counter.group(1), "amount": 1},
            }
        if event == "spell_cast" and re.search(
            r"whenever you cast a noncreature spell, incubate x, where x is that spell's mana value",
            oracle,
        ):
            spell = state.cards.get(payload.get("source_card_id"))
            if spell is not None:
                from rules_engine.mana import mana_value
                x_value = int((payload.get("stack_payload") or {}).get("x_value", 0) or 0)
                return {
                    "source_card_id": source_card_id, "controller": controller,
                    "label": default_label, "effect_key": "incubate",
                    "payload": {"counters": mana_value(spell.mana_cost, x_value=x_value)},
                }
        if event == "permanent_dies" and "target opponent loses life equal to this creature's power" in oracle:
            from rules_engine.continuous import effective_power
            amount = (effective_power(state, source_card_id) if source_card.zone == Zone.BATTLEFIELD
                      else source_card.last_known_battlefield.get("power", source_card.power or 0))
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "lose_life",
                "payload": {"target_player": opponent, "amount": max(0, int(amount))},
            }
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
                    if cid in state.cards and "Instant" in (effective_types(state, state.cards[cid]) or [])
                ),
                None,
            )
            return {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": default_label,
                "effect_key": "cast_from_graveyard",
                "payload": {"target_card_id": target, 'exile_after_cast':
                    bool(re.search(r'if that spell would be put into your graveyard, exile it instead', oracle))},
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
    opponent_drain = re.search(r"\btarget opponent loses (\d+) life and you gain (\d+) life\b", oracle)
    targeted_drain = re.search(r"\btarget player loses (\d+) life and you gain (\d+) life\b", oracle) or opponent_drain
    drain = re.search(r"\beach opponent loses (\d+) life and you gain (\d+) life\b", oracle)
    if event in {"creature_dies", "sacrifice"} and (targeted_drain or drain):
        amounts = targeted_drain or drain
        return {
            "source_card_id": source_card_id,
            "controller": controller,
            "label": default_label,
            "effect_key": "effect_sequence",
            "payload": {
                "__targeted_life_loss": bool(targeted_drain),
                "__target_opponent_only": bool(opponent_drain),
                "effects": [
                    {"effect_key": "lose_life", "payload": {"target_player": opponent, "amount": int(amounts.group(1))}},
                    {"effect_key": "gain_life", "payload": {"target_player": controller, "amount": int(amounts.group(2))}},
                ],
            },
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
            "exile each ",
            "exile a creature card they revealed this way",
            "tap target",
            "untap target",
            "search your library",
            "discard",
            "sacrifice",
            "return target",
            "incubate ",
            "add ",
            "lose ",
            "loses ",
            "counter target",
            "cast target",
            "reveals the top card",
            "reveal the top ",
            "gets -x/-x",
            "creatures you control get ",
        )
    ):
        from rules_engine.ability_model import build_ability_spec

        source_card = state.cards.get(source_card_id)
        if source_card is not None:
            parser_card = copy(source_card)
            parser_card.oracle_text = oracle
            parser_card.card_faces = []
            parser_card.selected_face_index = None
            parser_card.source_oracle_text = source_card.oracle_text
            parser_payload = dict(payload)
            # Cycle triggers need the permanent that owns the trigger as the
            # token/effect source. Other event payloads already use
            # source_card_id for the spell or permanent that caused the event.
            if event == "cycle":
                parser_payload["source_card_id"] = source_card_id
            ability = build_ability_spec(state, parser_card, controller, action_targets=parser_payload)
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
    if "you may" not in low or "for each card type, you may put" in low:
        return out
    out["__may"] = True
    # Conservative default: skip optional effects that only lose life; otherwise choose yes.
    if "lose life" in low and "gain life" not in low and "draw" not in low:
        out["__may_choose"] = False
    else:
        out["__may_choose"] = True
    return out
