from __future__ import annotations


from effects.registry import resolve_effect
from game_state.state import MatchState, StackItem, Zone, assign_static_order_on_battlefield_entry
from rules_engine.attachments import attach_if_legal, is_aura
from rules_engine.events import emit_event
from rules_engine.library_permissions import choose_type_for_realmwalker
from rules_engine.replacement import replacement_options, replacement_source_used
from rules_engine.counter_placement import put_counters
from rules_engine.zone_actions import put_into_graveyard, move_spell_from_stack


def add_to_stack(state: MatchState, source_card_id: str, controller: int, label: str, effect_key: str, payload: dict, targets: list[str] | None = None, *, is_spell: bool = True) -> StackItem:
    item = StackItem(
        id=state.allocate_object_id(),
        source_card_id=source_card_id,
        controller=controller,
        label=label,
        effect_key=effect_key,
        payload=payload,
        targets=targets or [],
    )
    state.stack.append(item)
    state.log.append(f"{state.players[controller].name} casts/activates {label}.")
    staged_here = not state.trigger_staging
    if staged_here:
        state.trigger_staging = True
        state.trigger_staging_event = "cast_or_activate"
    if is_spell:
        emit_event(
            state,
            "spell_cast",
            {
                "source_card_id": source_card_id,
                "controller": controller,
                "label": label,
                "stack_payload": dict(payload or {}),
            },
        )
    from rules_engine.ward import mark_stack_targets
    mark_stack_targets(state, item)
    if staged_here:
        from rules_engine.events import flush_staged_triggers
        flush_staged_triggers(state)
    # MTG priority rule: after casting/activating, the same player receives priority first.
    if not state.pending_trigger_order:
        state.priority_player = controller
    state.passed_priority = set()
    return item


def _replacement_context(state: MatchState, item: StackItem) -> tuple[str, int | None, str | None] | None:
    payload = item.payload or {}
    key = str(item.effect_key or "").lower()
    if key == "deal_damage":
        target_player = payload.get("target_player")
        target_card_id = payload.get("target_card_id")
        if target_player is not None:
            return ("damage_to_player", int(target_player), None)
        if target_card_id:
            target = state.cards.get(str(target_card_id))
            return ("damage_to_permanent", int(target.controller) if target else None, str(target_card_id))
    if key == "draw_cards":
        return ("card_draw", int(payload.get("target_player", item.controller)), None)
    if key == "gain_life":
        return ("life_gain", int(payload.get("target_player", item.controller)), None)
    if key in {"destroy_permanent", "destroy"} and payload.get("target_card_id"):
        target_id = str(payload["target_card_id"])
        target = state.cards.get(target_id)
        from rules_engine.continuous import has_keyword
        if target and (target.counters.get('shield', 0) > 0 or has_keyword(state, target_id, 'indestructible')):
            return None
        return ("die_zone", int(target.controller) if target else None, target_id)
    return None


def _legal_divided_damage_targets(state: MatchState, item: StackItem, card, announced: dict) -> dict:
    """Recheck each announced recipient without reallocating its fixed damage."""
    from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
    from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets

    hints = build_cast_hints(state, card, item.controller, announced)
    legal = {}
    for target_id, amount in (announced.get("target_distribution") or {}).items():
        single = {**announced, "target_distribution": {target_id: amount}, "divide_total": amount}
        if str(target_id) in {"1", "2"}:
            allowed = {str(target["id"]) for target in hints.get("player_targets", [])}
            if str(target_id) not in allowed or int(target_id) not in state.players:
                continue
        if (validate_cast_choice(hints, single)[0]
                and validate_protection_targets(state, card, single)[0]
                and validate_hexproof_shroud_targets(state, item.controller, single)[0]):
            legal[target_id] = amount
    return legal


def resolve_top_of_stack(state: MatchState) -> bool:
    if state.pending_mechanic_choice:
        return False
    if not state.stack:
        return False
    item = state.stack[-1]
    from rules_engine.targeting import stack_source_card
    card = stack_source_card(state, item)
    if (item.payload or {}).get("__trigger_target_choice"):
        from rules_engine.events import trigger_target_options
        chosen_card = item.payload.get("target_card_id")
        chosen_player = item.payload.get("target_player")
        if not any(option.get("target_card_id") == chosen_card and option.get("target_player") == chosen_player
                   for option in trigger_target_options(state, item)):
            state.stack.pop()
            state.log.append(f"{item.label} does not resolve because its target is illegal.")
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    announced = (item.payload or {}).get("__announced_targets") or {}
    target_count = (len(announced.get("target_card_ids") or []) + len(announced.get("target_distribution") or {})
                    + sum(bool(announced.get(key)) for key in ("target_card_id", "target_player", "target_stack_id")))
    target_count += sum(sum(choice.get(key) is not None for key in ("target_card_id", "target_player", "target_stack_id"))
                        for choice in (announced.get("mode_targets") or {}).values())
    if card and item.payload.get("__ability_target_text") and target_count == 1:
        from copy import copy
        from rules_engine.oracle_effects import inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_protection_targets, validate_hexproof_shroud_targets

        source = copy(card)
        source.oracle_text = item.payload["__ability_target_text"]
        source_lki = item.payload.get("__source_lki")
        if source_lki is not None:
            source.controller = int(source_lki["controller"])
            source.types = list(source_lki["types"])
            source.colors = list(source_lki.get("colors", []))
            source.card_faces = []
        hints = inspect_target_hints(state, source, item.controller, announced)
        legal = (validate_cast_targets(hints, announced)[0]
                 and validate_protection_targets(state, source, announced)[0]
                 and validate_hexproof_shroud_targets(state, item.controller, announced)[0])
        if not legal:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    legal_distribution = None
    legal_effects = None
    if card and card.zone == Zone.STACK and item.effect_key == "deal_damage_multi" and announced.get("target_distribution"):
        legal_distribution = _legal_divided_damage_targets(state, item, card, announced)
        if not legal_distribution:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif card and card.zone == Zone.STACK and target_count > 0 and item.effect_key == "effect_sequence" and announced.get("mode_texts") and (target_count > 1 or announced.get("mode_targets")):
        from rules_engine.oracle_effects import inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

        legal_effects = []
        any_legal_target = False
        for effect in item.payload.get("effects", []):
            selected = {key: effect.get("payload", {}).get(key) for key in ("target_card_id", "target_stack_id", "target_player")
                        if effect.get("payload", {}).get(key) is not None}
            mode_text = effect.get("mode_text")
            if not selected or not mode_text:
                legal_effects.append(effect)
                continue
            targets = {"mode_text": mode_text, **selected}
            hints = inspect_target_hints(state, card, item.controller, targets)
            legal = (validate_cast_targets(hints, targets)[0]
                     and validate_protection_targets(state, card, targets)[0]
                     and validate_hexproof_shroud_targets(state, item.controller, targets)[0])
            if legal:
                any_legal_target = True
                legal_effects.append(effect)
        if not any_legal_target:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif (card and card.zone == Zone.STACK and item.effect_key == "effect_sequence"
          and target_count > 1 and not announced.get("mode_texts")
          and not announced.get("target_card_ids") and not announced.get("target_distribution")):
        from rules_engine.oracle_effects import clause_target_assignments, inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

        effects = item.payload.get("effects", [])
        selections = clause_target_assignments(state, card, item.controller, announced, effects)
        if selections is not None and any(selections):
            hints = inspect_target_hints(state, card, item.controller, announced)
            legal_effects = []
            any_legal_target = False
            for effect, selected in zip(effects, selections):
                if not selected:
                    legal_effects.append(effect)
                    continue
                legal = (validate_cast_targets(hints, selected)[0]
                         and validate_protection_targets(state, card, selected)[0]
                         and validate_hexproof_shroud_targets(state, item.controller, selected)[0])
                if legal:
                    any_legal_target = True
                    legal_effects.append(effect)
            if not any_legal_target:
                state.stack.pop()
                return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif card and card.zone == Zone.STACK and target_count == 1:
        from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
        from rules_engine.targeting import validate_protection_targets, validate_hexproof_shroud_targets
        legal = (validate_cast_choice(build_cast_hints(state, card, item.controller, announced), announced)[0]
                 and validate_protection_targets(state, card, announced)[0]
                 and validate_hexproof_shroud_targets(state, item.controller, announced)[0])
        if not legal:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    if (item.payload or {}).get("__may"):
        is_trigger = bool(item.payload.get("__trigger_event"))
        choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
        if is_trigger and getattr(state, "trigger_order_choice_required", False) and (not choice_players or item.controller in choice_players) and not item.payload.get("__may_decided"):
            state.pending_trigger_order = {
                "phase": "optional", "event": item.payload["__trigger_event"],
                "current_stack_id": item.id, "current_controller": item.controller,
            }
            state.priority_player = item.controller
            state.passed_priority = set()
            state.log.append(f"{state.players[item.controller].name} must decide whether to apply {item.label}.")
            return False
        if not bool(item.payload.get("__may_choose", True)):
            state.stack.pop()
            state.log.append(f"{state.players[item.controller].name} declines optional effect: {item.label}.")
            return finish_stack_resolution(state, item, item.payload) if is_trigger else True
    context = _replacement_context(state, item)
    choice_players = set(getattr(state, "replacement_choice_players", set()) or set())
    requires_human_choice = (
        getattr(state, "replacement_choice_required", False)
        and (not choice_players or (context is not None and context[1] in choice_players))
    )
    if (
        requires_human_choice
        and not (item.payload or {}).get("__replacement_source_id")
        and context is not None
    ):
        event, target_player, target_card_id = context
        options = replacement_options(
            state,
            event,
            target_player=target_player,
            target_card_id=target_card_id,
            source_card_id=item.source_card_id,
        )
        used = {str(value) for value in ((item.payload or {}).get("__used_replacement_source_ids") or [])}
        options = [
            option for option in options
            if not replacement_source_used(used, event, str(option.get("source_id")))
        ]
        if len(options) > 1 and target_player is not None:
            state.pending_replacement_choice = {
                "stack_id": item.id,
                "player_id": target_player,
                "event": event,
                "target_card_id": target_card_id,
                "options": options,
            }
            state.priority_player = target_player
            state.passed_priority = set()
            state.log.append(
                f"Replacement choice required for {event}; "
                f"{state.players[target_player].name} must choose one of {len(options)} effects."
            )
            return False
    state.stack.pop()
    payload = dict(item.payload or {})
    if legal_effects is not None:
        payload["effects"] = legal_effects
    if legal_distribution is not None:
        payload["target_distribution"] = legal_distribution
        ignored = len(announced["target_distribution"]) - len(legal_distribution)
        if ignored:
            state.log.append(f"{item.label} ignores {ignored} illegal target(s).")
    is_trigger = bool(payload.get("__trigger_event"))
    payload["__source_card_id"] = item.source_card_id
    if not state.trigger_staging:
        state.trigger_staging = True
        state.trigger_staging_event = 'stack_resolution'
        item.payload['__resolution_stage_owned'] = True
        payload['__resolution_stage_owned'] = True
    if payload.get("__once_on_accept"):
        state.trigger_once_seen_this_turn.add(str(payload["__once_on_accept"]))
    resolve_effect(state, item.controller, item.effect_key, payload)
    pending_choice = state.pending_mechanic_choice or state.pending_replacement_choice
    if pending_choice:
        from dataclasses import asdict
        pending_choice["resolving_item"] = asdict(item)
        return False
    return finish_stack_resolution(state, item, payload)


def finish_stack_resolution(state: MatchState, item: StackItem, payload: dict) -> bool:
    entry_staged_here = False
    from rules_engine.ward import mark_stack_targets
    for copied in list(state.stack):
        if copied.payload.get("__stack_copy_kind"):
            mark_stack_targets(state, copied)
    if payload.get("__stack_copy_kind"):
        if payload.get("__stack_copy_kind") == "spell" and not payload.get("__failed_to_resolve"):
            copied_card = payload.get("__copied_card") or {}
            if not {"Instant", "Sorcery"}.intersection(copied_card.get("types") or []):
                if not _finish_permanent_spell_copy(state, item, payload):
                    return not (state.pending_mechanic_choice or state.pending_replacement_choice)
        if payload.get('__resolution_stage_owned'):
            from rules_engine.state_based_actions import apply_state_based_actions
            apply_state_based_actions(state)
        state.log.append(
            f"{item.label} does not resolve because its target is illegal."
            if payload.get("__failed_to_resolve") else f"{item.label} resolves."
        )
        return True
    is_trigger = bool(payload.get("__trigger_event"))
    card = state.cards.get(item.source_card_id)
    if card and card.zone == Zone.STACK and not is_trigger:
        owner = state.players[getattr(card, "owner", card.controller)]
        if "Instant" in card.types or "Sorcery" in card.types or payload.get("__failed_to_resolve"):
            if payload.get("__flashback") or payload.get("__aftermath"):
                move_spell_from_stack(state, item)
            elif card.layout == "adventure" and (card.selected_face_index or 0) > 0 and not payload.get("__failed_to_resolve"):
                owner.exile.append(card.id)
                card.move_to_zone(Zone.EXILE)
                state.adventure_permissions[card.id] = item.controller
            else:
                move_spell_from_stack(state, item)
            from rules_engine.alternative_casts import restore_printed_characteristics
            restore_printed_characteristics(card)
        else:
            if '__entry_counters_ready' not in payload:
                from rules_engine.entry_counters import begin_spell_entry
                return begin_spell_entry(state, item, payload)
            entry_staged_here = not state.trigger_staging
            if entry_staged_here:
                state.trigger_staging = True
                state.trigger_staging_event = 'permanent_entry'
            battlefield_player = state.players[item.controller]
            card.controller = item.controller
            battlefield_player.battlefield.append(card.id)
            card.zone = Zone.BATTLEFIELD
            card.summoning_sick = True
            card.entered_turn = state.turn
            if "Planeswalker" in card.types and card.loyalty is not None:
                card.printed_characteristics.setdefault("loyalty", card.loyalty)
                card.loyalty = 0
            assign_static_order_on_battlefield_entry(state, card.id)
            if '__consume_entry_counter' in payload:
                state.pending_entry_counters.pop(payload['__consume_entry_counter'])
            for kind, amount in payload['__entry_counters_ready'].items():
                put_counters(state, kind, amount, target_card_id=card.id, placement_checked=True)
            if "as this creature enters, choose a creature type" in (card.oracle_text or "").lower():
                selected = str(payload.get("chosen_creature_type") or "").strip().lower()
                card.chosen_creature_type = selected or choose_type_for_realmwalker(state, card.controller)
                state.log.append(f"{card.name} chooses creature type {card.chosen_creature_type}.")
            if is_aura(card):
                target_id = payload.get("target_card_id")
                if not attach_if_legal(state, card.id, target_id):
                    battlefield_player.battlefield.remove(card.id)
                    zone = put_into_graveyard(state, card.id)
                    state.log.append(f"{card.name} has no legal attachment target and is put into {zone.value}.")
                    state.log.append(f"{item.label} resolves.")
                    if entry_staged_here or payload.get('__resolution_stage_owned'):
                        from rules_engine.state_based_actions import apply_state_based_actions
                        apply_state_based_actions(state)
                    return True
            emit_event(state, "enters_battlefield", {"card_id": card.id, "controller": card.controller, "x_value": max(0, int(payload.get("x_value", 0) or 0))})
    if entry_staged_here or payload.get('__resolution_stage_owned'):
        from rules_engine.state_based_actions import apply_state_based_actions
        apply_state_based_actions(state)
    if not state.pending_mechanic_choice:
        state.log.append(f"{item.label} does not resolve because its target is illegal." if payload.get("__failed_to_resolve") else f"{item.label} resolves.")
    return True


def _finish_permanent_spell_copy(state: MatchState, item: StackItem, payload: dict) -> bool:
    from game_state.state import CardInstance
    from dataclasses import asdict
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters

    copied = payload["__copied_card"]
    types = list(copied.get("types") or [])
    token = (CardInstance(**{**payload['__entry_candidates'][0], 'zone': Zone.BATTLEFIELD})
             if '__entry_candidates' in payload else CardInstance(
        id=state.allocate_object_id(), name=copied["name"], owner=item.controller,
        controller=item.controller, zone=Zone.BATTLEFIELD, is_token=True,
        types=list(dict.fromkeys([*types, "Token"])),
        mana_cost=copied.get("mana_cost") or "", type_line=copied.get("type_line") or "",
        oracle_text=copied.get("oracle_text") or "", power=copied.get("power"),
        toughness=copied.get("toughness"), loyalty=copied.get("loyalty"),
        keywords=list(copied.get("keywords") or []), colors=copied.get("colors"),
        image_uri=copied.get("image_uri"), layout=copied.get("layout") or "",
        card_faces=list(copied.get("card_faces") or []),
        selected_face_index=copied.get("selected_face_index"),
        summoning_sick=True, entered_turn=state.turn,
    ))
    completion = ({'entry_item': asdict(item), 'entry_payload': payload}
                  if '__entry_counters_by_id' not in payload else payload)
    if prepare_counter_entries(state, item.controller, [token], 'permanent_spell_copy_entry',
                               completion, entry_payload={'x_value': payload.get('x_value', 0)}):
        return False
    state.cards[token.id] = token
    state.players[item.controller].battlefield.append(token.id)
    if is_aura(token) and not attach_if_legal(state, token.id, payload.get("target_card_id")):
        state.players[item.controller].battlefield.remove(token.id)
        del state.cards[token.id]
        return True
    assign_static_order_on_battlefield_entry(state, token.id)
    commit_entry_counters(state, token, payload)
    emit_event(state, "enters_battlefield", {"card_id": token.id, "controller": item.controller,
                                            "x_value": max(0, int(payload.get("x_value", 0) or 0))})
    return True


def resume_paused_resolution(state: MatchState, pending: dict) -> None:
    from effects.handlers import draw_cards

    controller = int(
        pending.get('continuation_controller')
        or (pending.get("resolving_item") or {}).get("controller")
        or pending.get("controller")
        or pending["player_id"]
    )
    counter_queue = list(pending.get('counter_continuation_queue') or [])
    while counter_queue and not (state.pending_mechanic_choice or state.pending_replacement_choice):
        event = counter_queue.pop(0)
        resolve_effect(state, event['controller'], event['effect_key'], event['payload'])
    next_pending = state.pending_mechanic_choice or state.pending_replacement_choice
    if next_pending:
        if pending.get('continuation_controller'):
            next_pending['continuation_controller'] = pending['continuation_controller']
        next_pending.setdefault('counter_continuation_queue', []).extend(counter_queue)
    queue = list(pending.get("draw_continuation_queue") or [])
    if not queue and pending.get("remaining_draws"):
        queue = [pending.get("remaining_draw_payload") or {
            "target_player": pending["player_id"], "amount": pending["remaining_draws"],
        }]
    next_pending = state.pending_mechanic_choice or state.pending_replacement_choice
    while queue and not next_pending and state.winner is None:
        draw_cards(state, controller, queue.pop(0))
        next_pending = state.pending_mechanic_choice or state.pending_replacement_choice
    if next_pending:
        if pending.get('continuation_controller'):
            next_pending['continuation_controller'] = pending['continuation_controller']
        if pending.get('activation_controller'):
            next_pending['activation_controller'] = pending['activation_controller']
        next_pending.setdefault("draw_continuation_queue", []).extend(queue)
        if pending.get("combat_damage_needs_sba"):
            next_pending["combat_damage_needs_sba"] = True
        if pending.get("resolving_item"):
            next_pending["resolving_item"] = pending["resolving_item"]
        next_pending.setdefault("continuation_effects", []).extend(pending.get("continuation_effects", []))
        return
    if pending.get("continuation_effects") and state.winner is None:
        resolve_effect(state, controller, "effect_sequence", {"effects": pending["continuation_effects"]})
    next_pending = state.pending_mechanic_choice or state.pending_replacement_choice
    if next_pending:
        if pending.get('continuation_controller'):
            next_pending['continuation_controller'] = pending['continuation_controller']
        if pending.get("combat_damage_needs_sba"):
            next_pending["combat_damage_needs_sba"] = True
        if pending.get("resolving_item"):
            next_pending["resolving_item"] = pending["resolving_item"]
    elif pending.get("resolving_item"):
        item = StackItem(**pending["resolving_item"])
        finish_stack_resolution(state, item, {**item.payload, "__source_card_id": item.source_card_id})
    if pending.get("combat_damage_needs_sba") and not (state.pending_mechanic_choice or state.pending_replacement_choice):
        from rules_engine.state_based_actions import apply_state_based_actions
        apply_state_based_actions(state)
    if not state.pending_mechanic_choice and not state.pending_trigger_order and not state.pending_replacement_choice:
        state.priority_player = int(pending.get('activation_controller') or state.active_player)
        state.passed_priority = set()
