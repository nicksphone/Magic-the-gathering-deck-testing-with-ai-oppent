from __future__ import annotations
from rules_engine.type_effects import effective_types


from effects.registry import resolve_effect
from game_state.state import MatchState, StackItem, Zone, assign_static_order_on_battlefield_entry
from rules_engine.attachments import attach_if_legal, is_aura
from rules_engine.events import emit_event
from rules_engine.library_permissions import choose_type_for_realmwalker
from rules_engine.replacement import replacement_options, replacement_source_used
from rules_engine.counter_placement import put_counters
from rules_engine.zone_actions import put_into_graveyard, move_spell_from_stack


def add_to_stack(state: MatchState, source_card_id: str, controller: int, label: str, effect_key: str, payload: dict, targets: list[str] | None = None, *, is_spell: bool = True) -> StackItem:
    if type(is_spell) is not bool:
        from rules_engine.action_validation import ActionRejected
        raise ActionRejected('Stack publication requires a native boolean kind')
    payload = {**payload, '__announced_stack_kind': 'spell' if is_spell else 'activated'}
    from rules_engine.bestow import is_bestowed
    from game_state.state import object_incarnation
    source = state.cards.get(source_card_id)
    target = state.cards.get((payload or {}).get('target_card_id'))
    if is_spell and source is not None and is_bestowed(source) and target is not None:
        payload = {**payload, '__bestow_target_incarnation': [object_incarnation(target), target.zone_change_sequence]}
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
        from rules_engine.turn_spell_protection import record_spell_colors
        record_spell_colors(state, source, controller)
        emit_event(
            state,
            "spell_cast",
            {
                "source_card_id": source_card_id,
                "source_stack_id": item.id,
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
    if key == 'conditional_instruction':
        from rules_engine.conditional_instructions import selected_instruction
        key, payload = selected_instruction(state, item.controller, payload)
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


def _legal_divided_damage_targets(state: MatchState, item: StackItem, card, announced: dict, *, hint_card=None) -> dict:
    """Recheck each announced recipient without reallocating its fixed damage."""
    from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
    from rules_engine.targeting import validate_hexproof_shroud_targets, validate_protection_targets, stack_object_kind

    hints = build_cast_hints(state, card if hint_card is None else hint_card, item.controller, announced)
    legal = {}
    for target_id, amount in (announced.get("target_distribution") or {}).items():
        single = {**announced, "target_distribution": {target_id: amount}, "divide_total": amount}
        if str(target_id) in {"1", "2"}:
            allowed = {str(target["id"]) for target in hints.get("player_targets", [])}
            if str(target_id) not in allowed or int(target_id) not in state.players:
                continue
        from rules_engine.targeting import announced_target_reference_matches
        current = (str(target_id) in {'1', '2'} or announced_target_reference_matches(
            state, (item.payload or {}).get('__announced_target_references'),
            ('target_distribution', target_id), target_id))
        if (current and validate_cast_choice(hints, single)[0]
                and validate_protection_targets(state, card, single, source_lki=(item.payload or {}).get('__source_lki'))[0]
                and validate_hexproof_shroud_targets(state, item.controller, single, card,
                    source_lki=(item.payload or {}).get('__source_lki'), source_kind=stack_object_kind(state, item))[0]):
            legal[target_id] = amount
    return legal


def _damage_replacement_source_context(state: MatchState, item: StackItem, selected_payload: dict):
    """Project query inputs without conflating ability control with source control."""
    from rules_engine.targeting import stack_object_kind
    source_lki = selected_payload.get('__source_lki', (item.payload or {}).get('__source_lki'))
    # A spell copy is a spell in its own right; its physical source may have departed.
    source_controller = item.controller if stack_object_kind(state, item) == 'spell' else None
    return source_lki, source_controller


def _validate_damage_activation_source(state: MatchState, item: StackItem) -> None:
    """Validate native battlefield damage provenance, not arbitrary storage authenticity."""
    payload = item.payload or {}
    from rules_engine.damage_results import validate_hand_payload
    context = validate_hand_payload(state, payload, source_card_id=item.source_card_id)
    if '__activation_source_origin' in payload and (
            type(payload['__activation_source_origin']) is not str
            or payload['__activation_source_origin'] not in {'hand', 'battlefield', 'graveyard'}):
        from rules_engine.action_validation import ActionRejected
        raise ActionRejected('Unknown native activation origin')
    if context is not None:
        if item.source_card_id not in state.cards:
            from rules_engine.action_validation import ActionRejected
            raise ActionRejected('HAND activation target hints require a real source instance')
        return
    if ('__activation_source_reference' not in payload or '__ability_target_text' not in payload
            or payload.get('__trigger_event') or payload.get('__stack_copy_kind') in ('spell', 'triggered')):
        return  # Legacy frames, spells and triggers have separate producer contracts.
    pending = [(item.effect_key, payload)]
    packets = []
    damage = False
    while pending:
        key, data = pending.pop()
        if not isinstance(data, dict):
            continue
        packets.append(data)
        if key == 'conditional_instruction':
            key = data.get('effect_key')
        damage |= key in {'deal_damage', 'deal_damage_multi', 'deal_damage_batch',
                         'deal_damage_to_controller', 'damage_each_creature',
                         'damage_each_creature_and_player', 'linked_landfall_damage'}
        if key == 'effect_sequence':
            pending.extend((effect.get('effect_key'), effect.get('payload'))
                           for effect in data.get('effects', []) if isinstance(effect, dict))
    if not damage:
        return
    from rules_engine.action_validation import ActionRejected
    from game_state.state import object_incarnation
    reference = payload['__activation_source_reference']
    if (not isinstance(reference, dict)
            or set(reference) != {'incarnation', 'zone_change_sequence'}
            or any(type(value) is not int or value < 0 for value in reference.values())):
        raise ActionRejected('Malformed native damage activation source reference')
    source = state.cards.get(item.source_card_id)
    if payload.get('__activation_source_origin') == 'graveyard':
        return  # Existing graveyard producer has a separate source contract.
    for packet in packets:
        if '__source_lki' not in packet:
            continue
        lki = packet['__source_lki']
        if (not isinstance(lki, dict)
                or type(lki.get('controller')) is not int or lki['controller'] not in state.players
                or type(lki.get('battlefield_incarnation')) is not int
                or lki['battlefield_incarnation'] < 0
                or lki['battlefield_incarnation'] != reference['incarnation']):
            raise ActionRejected('Malformed retained damage activation battlefield LKI')
    same_live_object = (source is not None and source.zone == Zone.BATTLEFIELD
                        and object_incarnation(source) == reference['incarnation']
                        and source.zone_change_sequence == reference['zone_change_sequence'])
    if not same_live_object and '__source_lki' not in payload:
        raise ActionRejected('Departed native damage activation source requires retained battlefield LKI')


def resolve_top_of_stack(state: MatchState) -> bool:
    if state.pending_mechanic_choice:
        return False
    if not state.stack:
        return False
    item = state.stack[-1]
    _validate_damage_activation_source(state, item)
    from rules_engine.prevention import has_numeric_prevention_instruction, validate_prevention_item
    prevention_frame_required = has_numeric_prevention_instruction(item.effect_key, item.payload or {})
    if prevention_frame_required:
        validate_prevention_item(state, item)
    control_frame_required = (
        item.effect_key == 'temporary_control_instruction'
        or item.effect_key == 'effect_sequence' and any(
            isinstance(effect, dict) and effect.get('effect_key') == 'temporary_control_instruction'
            for effect in (item.payload or {}).get('effects', [])))
    if control_frame_required:
        from rules_engine.action_validation import ActionRejected
        receipt = (item.payload or {}).get('__control_source_frame')
        if (not isinstance(receipt, dict)
                or set(receipt) != {'stack_id', 'source_card_id', 'cast_controller', 'label', 'source_reference'}
                or not isinstance(receipt['stack_id'], str) or not receipt['stack_id']
                or receipt['source_card_id'] != item.source_card_id
                or not isinstance(receipt['source_card_id'], str) or not receipt['source_card_id']
                or type(receipt['cast_controller']) is not int or receipt['cast_controller'] not in state.players
                or not isinstance(receipt['label'], str) or not receipt['label']):
            raise ActionRejected('Malformed retained control source frame')
        reference = receipt['source_reference']
        if (not isinstance(reference, dict)
                or set(reference) != {'incarnation', 'zone_change_sequence'}
                or any(type(value) is not int or value < 0 for value in reference.values())):
            raise ActionRejected('Malformed retained control source reference')
        copy_kind = (item.payload or {}).get('__stack_copy_kind')
        if copy_kind is not None and copy_kind != 'spell':
            raise ActionRejected('Unknown control source copy kind')
        # Copies retain announcing provenance, not their new resolving identity.
        if not (item.payload or {}).get('__stack_copy_kind') and (
                receipt['stack_id'] != item.id or receipt['cast_controller'] != item.controller):
            raise ActionRejected('Control source frame does not match announced item')
    from rules_engine.targeting import validate_announced_target_references, announced_target_reference_matches
    references = (item.payload or {}).get('__announced_target_references')
    if '__announced_target_references' in (item.payload or {}):
        validate_announced_target_references((item.payload or {}).get('__announced_targets') or {}, references)

    def same_targets(selected, prefix=()):
        return (selected.get('target_card_id') is None or announced_target_reference_matches(
            state, references, (*prefix, 'target_card_id'), selected['target_card_id']))

    from rules_engine.targeting import stack_source_card, stack_object_kind
    card = stack_source_card(state, item)
    if item.effect_key == 'conditional_instruction':
        from rules_engine.conditional_instructions import target_is_current
        if not target_is_current(state, item.payload):
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, '__failed_to_resolve': True})
    if (item.payload or {}).get("__trigger_target_choice"):
        from rules_engine.events import trigger_target_options
        from game_state.state import object_incarnation
        chosen_card = item.payload.get("target_card_id")
        chosen_player = item.payload.get("target_player")
        target = state.cards.get(chosen_card)
        reference = item.payload.get('__trigger_target_reference')
        stale = reference is not None and (target is None or reference != [object_incarnation(target), target.zone_change_sequence])
        if stale or not any(option.get("target_card_id") == chosen_card and option.get("target_player") == chosen_player
                   for option in trigger_target_options(state, item)):
            state.stack.pop()
            state.log.append(f"{item.label} does not resolve because its target is illegal.")
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    announced = (item.payload or {}).get("__announced_targets") or {}
    target_count = (len(announced.get("target_card_ids") or []) + len(announced.get("target_distribution") or {})
                    + sum(bool(announced.get(key)) for key in ("target_card_id", "target_player", "target_stack_id")))
    target_count += sum(sum(choice.get(key) is not None for key in ("target_card_id", "target_player", "target_stack_id"))
                        for choice in (announced.get("mode_targets") or {}).values())
    if (item.effect_key == 'effect_sequence' and target_count == 1
            and announced.get('target_card_id') and item.payload.get('target_restrictions')):
        from rules_engine.oracle_effects import _target_card_matches_restrictions
        target = state.cards.get(announced['target_card_id'])
        legal = (same_targets(announced) and target is not None and target.zone == Zone.BATTLEFIELD
                 and _target_card_matches_restrictions(state, target, item.payload['target_restrictions'],
                    item.controller, x_value=int(item.payload.get('x_value', 0) or 0)))
        if not legal:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, '__failed_to_resolve': True})
    from rules_engine.bestow import is_bestowed, end_bestow
    if card is not None and is_bestowed(card) and stack_object_kind(state, item) == 'spell':
        from game_state.state import object_incarnation
        from rules_engine.attachments import attachment_target_is_legal
        from rules_engine.targeting import validate_hexproof_shroud_targets
        target_id = item.payload.get('target_card_id')
        target = state.cards.get(target_id)
        incarnation = item.payload.get('__bestow_target_incarnation')
        legal = (attachment_target_is_legal(state, card, target_id)
                 and (incarnation is None or target is not None
                      and [object_incarnation(target), target.zone_change_sequence] == incarnation)
                 and validate_hexproof_shroud_targets(state, item.controller, {'target_card_id': target_id}, card, source_kind=stack_object_kind(state, item))[0])
        if not legal:
            end_bestow(card)
            item.payload.pop('target_card_id', None)
            item.payload.pop('__announced_targets', None)
            item.payload.pop('__announced_target_references', None)
            if item.payload.get('__copied_card'):
                item.payload['__copied_card'] = {**item.payload['__copied_card'],
                    'types': list(effective_types(state, card)), 'type_line': card.type_line, 'bestow_characteristics': {}}
            announced, target_count = {}, 0
            state.log.append(f'{item.label} ceases to be bestowed and resolves as a creature.')
    target_source = card
    source_lki = item.payload.get('__source_lki')
    if card and item.payload.get("__ability_target_text"):
        from copy import copy
        target_source = copy(card)
        target_source.oracle_text = item.payload["__ability_target_text"]
        target_source.mana_cost = ''
        if source_lki is not None:
            target_source.controller = int(source_lki["controller"])
            target_source.types = list(source_lki["types"])
            target_source.colors = list(source_lki.get("colors", []))
            target_source.card_faces = []
            # Nested hint filters must also use this receipt, never new-object layers.
            target_source._retained_source_lki = source_lki
    targeted_frame = card is not None and (stack_object_kind(state, item) == 'spell'
                                           or bool(item.payload.get('__ability_target_text')))
    if card and item.payload.get("__ability_target_text") and target_count == 1:
        from rules_engine.oracle_effects import inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_protection_targets, validate_hexproof_shroud_targets
        hints = inspect_target_hints(state, target_source, item.controller, announced, source_kind=stack_object_kind(state, item))
        # A captured source belongs to the old object, not a same-ID reentry.
        legal = (same_targets(announced) and validate_cast_targets(hints, announced)[0]
                 and validate_protection_targets(state, card, announced, source_lki=source_lki)[0]
                 and validate_hexproof_shroud_targets(state, item.controller, announced, card, source_lki=source_lki, source_kind=stack_object_kind(state, item))[0])
        if not legal:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    legal_distribution = None
    legal_effects = None
    if targeted_frame and item.effect_key == "deal_damage_multi" and announced.get("target_distribution"):
        legal_distribution = _legal_divided_damage_targets(state, item, card, announced, hint_card=target_source)
        if not legal_distribution:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif item.effect_key == 'linked_landfall_damage':
        from rules_engine.linked_targets import legal_linked_recipients
        legal_recipients = legal_linked_recipients(state, item)
        instances = item.payload['target_instances']
        paths = ([('target_card_ids', 0), ('target_card_ids', 1)]
                 if 'target_card_ids' in announced else [None, ('target_card_id',)])
        legal_recipients = [packet for packet in legal_recipients if packet['kind'] == 'player'
            or announced_target_reference_matches(state, references,
                paths[instances.index(packet)], packet['id'])]
        if not legal_recipients:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, '__failed_to_resolve': True})
    elif targeted_frame and (
            item.payload.get('__ordered_distinct_targets') or item.payload.get('__ordered_target_instances')):
        from game_state.state import object_incarnation
        from rules_engine.oracle_effects import inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets
        hints = inspect_target_hints(state, target_source, item.controller, announced, source_kind=stack_object_kind(state, item))
        hints.pop('required_distinct_target_count', None)
        hints.pop('required_target_instance_count', None)
        legal_effects = []
        for index, effect in enumerate(item.payload.get('effects', [])):
            packet = effect['payload']
            target = state.cards.get(packet['target_card_id'])
            selected = {'target_card_id': packet['target_card_id']}
            if (target is not None and target.zone == Zone.BATTLEFIELD
                    and announced_target_reference_matches(state, references,
                        ('target_card_ids', index), packet['target_card_id'])
                    and object_incarnation(target) == packet['__target_incarnation']
                    and target.zone_change_sequence == packet['__target_zone_sequence']
                    and validate_cast_targets(hints, selected)[0]
                    and validate_protection_targets(state, card, selected, source_lki=source_lki)[0]
                    and validate_hexproof_shroud_targets(state, item.controller, selected, card, source_lki=source_lki, source_kind=stack_object_kind(state, item))[0]):
                legal_effects.append(effect)
        if not legal_effects:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, '__failed_to_resolve': True})
    elif targeted_frame and target_count > 0 and item.effect_key == "effect_sequence" and announced.get("mode_texts") and (target_count > 1 or announced.get("mode_targets")):
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
            hints = inspect_target_hints(state, target_source, item.controller, targets, source_kind=stack_object_kind(state, item))
            prefix = ('mode_targets', mode_text) if announced.get('mode_targets') else ()
            legal = (same_targets(selected, prefix) and validate_cast_targets(hints, targets)[0]
                     and validate_protection_targets(state, card, targets, source_lki=source_lki)[0]
                     and validate_hexproof_shroud_targets(state, item.controller, targets, card, source_lki=source_lki, source_kind=stack_object_kind(state, item))[0])
            if legal:
                any_legal_target = True
                legal_effects.append(effect)
        if not any_legal_target:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif (targeted_frame and item.effect_key == "effect_sequence"
          and target_count > 1 and not announced.get("mode_texts")
          and not announced.get("target_card_ids") and not announced.get("target_distribution")):
        from rules_engine.oracle_effects import clause_target_assignments, inspect_target_hints
        from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

        effects = item.payload.get("effects", [])
        selections = clause_target_assignments(state, target_source, item.controller, announced, effects)
        if selections is not None and any(selections):
            hints = inspect_target_hints(state, target_source, item.controller, announced, source_kind=stack_object_kind(state, item))
            legal_effects = []
            any_legal_target = False
            for effect, selected in zip(effects, selections):
                if not selected:
                    legal_effects.append(effect)
                    continue
                legal = (same_targets(selected) and validate_cast_targets(hints, selected)[0]
                         and validate_protection_targets(state, card, selected, source_lki=source_lki)[0]
                         and validate_hexproof_shroud_targets(state, item.controller, selected, card, source_lki=source_lki, source_kind=stack_object_kind(state, item))[0])
                if legal:
                    any_legal_target = True
                    legal_effects.append(effect)
            if not any_legal_target:
                state.stack.pop()
                return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    elif card and card.zone == Zone.STACK and target_count == 1:
        from rules_engine.cast_choice import build_cast_hints, validate_cast_choice
        from rules_engine.targeting import validate_protection_targets, validate_hexproof_shroud_targets
        legal = (same_targets(announced)
                 and validate_cast_choice(build_cast_hints(state, card, item.controller, announced, source_kind=stack_object_kind(state, item)), announced)[0]
                 and validate_protection_targets(state, card, announced)[0]
                 and validate_hexproof_shroud_targets(state, item.controller, announced, card, source_kind=stack_object_kind(state, item))[0])
        if not legal:
            state.stack.pop()
            return finish_stack_resolution(state, item, {**item.payload, "__failed_to_resolve": True})
    if item.effect_key in {'landfall_alternative', 'linked_landfall_damage'}:
        from rules_engine.landfall import require_known_history
        require_known_history(state, item.controller)
    from rules_engine.prevention import validate_legacy_damage_boundary
    validate_legacy_damage_boundary(state, item)
    if item.effect_key == 'attached_token_payment':
        from rules_engine.attached_token_payment import prepare
        prepare(state, item)
    if (item.payload or {}).get("__may"):
        is_trigger = bool(item.payload.get("__trigger_event"))
        choice_players = set(getattr(state, "trigger_order_choice_players", set()) or set())
        paid_optional = bool(item.payload.get('__optional_payment_cost'))
        if is_trigger and (paid_optional or (getattr(state, "trigger_order_choice_required", False) and (not choice_players or item.controller in choice_players))) and not item.payload.get("__may_decided"):
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
        selected_payload = item.payload or {}
        if item.effect_key == 'conditional_instruction':
            from rules_engine.conditional_instructions import selected_instruction
            _, selected_payload = selected_instruction(state, item.controller, selected_payload)
        source_lki = selected_payload.get('__source_lki', (item.payload or {}).get('__source_lki'))
        source_controller = item.controller
        if event in {'damage_to_permanent', 'damage_to_player'}:
            source_lki, source_controller = _damage_replacement_source_context(state, item, selected_payload)
        options = replacement_options(
            state,
            event,
            target_player=target_player,
            target_card_id=target_card_id,
            source_card_id=item.source_card_id,
            amount=selected_payload.get('amount') if event == 'damage_to_permanent' else None,
            source_lki=source_lki,
            source_controller=source_controller, combat=False,
            source_context=selected_payload.get('__activation_source_context', (item.payload or {}).get('__activation_source_context')),
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
    if item.effect_key == 'linked_landfall_damage':
        payload['legal_recipients'] = legal_recipients
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
    if payload.get('__optional_payment_cost'):
        from rules_engine.paid_triggers import pay_optional
        from rules_engine.action_validation import ActionRejected
        if not pay_optional(state, item):
            raise ActionRejected('Cannot pay optional trigger cost')
        payload['__optional_payment_paid'] = item.payload['__optional_payment_paid']
    if payload.get("__once_on_accept"):
        state.trigger_once_seen_this_turn.add(str(payload["__once_on_accept"]))
    effect_key = item.effect_key
    if payload.get('__trigger_resolution_text'):
        from copy import copy
        from rules_engine.oracle_effects import infer_effect_from_oracle
        surface = copy(card)
        surface.oracle_text = payload['__trigger_resolution_text']
        surface.card_faces = []
        surface.types = []
        effect_key, instructions = infer_effect_from_oracle(state, surface, item.controller, payload)
        payload.update(instructions)
    if effect_key == 'conditional_instruction' and payload.get('__stack_copy_kind') == 'spell':
        from rules_engine.colors import card_color_names
        payload['__source_lki'] = {**(payload.get('__source_lki') or {}),
                                  'controller': item.controller,
                                  'color_names': sorted(card_color_names(card)),
                                  'keywords': list(card.keywords or [])}
    if effect_key in {'suspend_upkeep', 'suspend_cast_trigger'}:
        from rules_engine.suspend import resolve_trigger
        resolve_trigger(state, item.controller, effect_key, payload)
    else:
        if (control_frame_required or prevention_frame_required or effect_key in {'shuffle_graveyard_into_library', 'search_library', 'put_exiled_card_into_graveyard', 'set_next_creature_entry_counter', 'bind_creature_spell_entry_counter', 'loyalty_delay_return', 'loyalty_return'}
                or effect_key == 'effect_sequence' and any(
                    effect.get('effect_key') in {'shuffle_graveyard_into_library', 'search_library', 'set_next_creature_entry_counter', 'bind_creature_spell_entry_counter', 'loyalty_sacrifice_return'}
                    for effect in payload.get('effects', []))):
            from dataclasses import asdict
            # Transport the real popped item only where shuffle attribution needs it.
            frame = asdict(item)
            frame['payload'].pop('__resolving_item', None)
            payload['__resolving_item'] = frame
            if effect_key == 'effect_sequence':
                payload['effects'] = [
                    {**effect, 'payload': {**effect.get('payload', {}), '__one_shot_child_position': index}}
                    if effect.get('effect_key') == 'set_next_creature_entry_counter' else effect
                    for index, effect in enumerate(payload.get('effects', []))]
        resolve_effect(state, item.controller, effect_key, payload)
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
        if "Instant" in effective_types(state, card) or "Sorcery" in effective_types(state, card) or payload.get("__failed_to_resolve"):
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
            from rules_engine.entry_counters import next_entry_commit_matches
            if not next_entry_commit_matches(state, item, payload):
                from rules_engine.action_validation import ActionRejected
                raise ActionRejected('Stale retained next-creature entry packet')
            entry_staged_here = not state.trigger_staging
            if entry_staged_here:
                state.trigger_staging = True
                state.trigger_staging_event = 'permanent_entry'
            battlefield_player = state.players[item.controller]
            card.controller = item.controller
            from rules_engine.card_faces import apply_day_night_entry
            apply_day_night_entry(state, card)
            battlefield_player.battlefield.append(card.id)
            card.zone = Zone.BATTLEFIELD
            card.summoning_sick = True
            card.entered_turn = state.turn
            if "Planeswalker" in effective_types(state, card) and card.loyalty is not None:
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
            from rules_engine.source_linked_exile import commit_entry
            commit_entry(state, card)
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
    from copy import deepcopy
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters

    copied = payload["__copied_card"]
    kicker_count = None
    if '__kicker_count' in payload:
        from rules_engine.kicker import validate_kicker_count
        kicker_count = validate_kicker_count(payload['__kicker_count'], payload.get('__kicked', False))
    types = list(copied.get("types") or [])
    token = (CardInstance(**{**payload['__entry_candidates'][0], 'zone': Zone.BATTLEFIELD})
             if '__entry_candidates' in payload else CardInstance(
        id=state.allocate_object_id(), name=copied["name"], owner=item.controller,
        controller=item.controller, zone=Zone.BATTLEFIELD, is_token=True,
        types=list(dict.fromkeys([*types, "Token"])),
        mana_cost=copied.get("mana_cost") or "", type_line=copied.get("type_line") or "",
        oracle_text=copied.get("oracle_text") or "", power=copied.get("power"),
        toughness=copied.get("toughness"), loyalty=copied.get("loyalty"),
        printed_power=copied.get('printed_power'), printed_toughness=copied.get('printed_toughness'),
        keywords=list(copied.get("keywords") or []), colors=copied.get("colors"),
        image_uri=copied.get("image_uri"), layout=copied.get("layout") or "",
        card_faces=list(copied.get("card_faces") or []),
        selected_face_index=copied.get("selected_face_index"),
        bestow_characteristics=deepcopy(copied.get('bestow_characteristics') or {}),
        summoning_sick=True, entered_turn=state.turn,
        was_kicked=bool(payload.get('__kicked')),
        kicker_count=kicker_count,
    ))
    token.was_kicked = bool(payload.get('__kicked'))
    token.kicker_count = kicker_count
    completion = ({'entry_item': asdict(item), 'entry_payload': payload}
                  if '__entry_counters_by_id' not in payload else payload)
    if prepare_counter_entries(state, item.controller, [token], 'permanent_spell_copy_entry',
                               completion, entry_payload={'x_value': payload.get('x_value', 0),
                                                          '__kicked': bool(payload.get('__kicked')),
                                                          **({'__kicker_count': kicker_count} if kicker_count is not None else {})}):
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
