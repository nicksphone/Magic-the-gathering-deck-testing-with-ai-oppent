from __future__ import annotations
from rules_engine.type_effects import effective_types

from game_state.state import MatchState, Zone
from rules_engine.card_types import is_token_card
from rules_engine.attachments import attached_to, attachment_target_is_legal, is_aura, is_equipment, is_fortification
from rules_engine.events import emit_event, emit_event_batch, was_creature_on_battlefield
from rules_engine.continuous import effective_toughness, effective_combat_stats, has_keyword
from rules_engine.replacement import replacement_options, select_graveyard_entry_plan
from rules_engine.zone_actions import put_into_graveyard, prepare_graveyard_entry_causes, execute_graveyard_entry
from rules_engine.query_context import rule_query_scope

DMG_MARK_KEY = "__damage_marked"
DEATHTOUCH_MARK_KEY = "__deathtouch_damaged"


def creature_has_lethal_state(state: MatchState, card_id: str) -> bool:
    card = state.cards[card_id]
    if card.zone != Zone.BATTLEFIELD or "Creature" not in effective_types(state, card):
        return False
    toughness = effective_combat_stats(state, card_id)[1]
    if toughness is None:
        return False
    if toughness <= 0:
        return True
    lethal_damage = (int(card.counters.get(DMG_MARK_KEY, 0)) >= toughness
                     or int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0)
    return lethal_damage and not has_keyword(state, card_id, "indestructible")


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
    if card_id not in battlefield_owner.battlefield:
        return
    plan = select_graveyard_entry_plan(state, card_id, replacement_source_id or None)
    causes = prepare_graveyard_entry_causes(state, [plan])
    emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
    was_creature = was_creature_on_battlefield(card)
    destination = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=causes[card_id])
    if destination != Zone.GRAVEYARD:
        state.log.append(f"State-based action: {card.name} {'is exiled' if destination == Zone.EXILE else f'is put into {destination.value}'} instead of dying.")
        return
    state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    if was_creature:
        emit_event(state, "creature_dies", {"card_id": card_id, "controller": plan.controller})


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
    plan = select_graveyard_entry_plan(state, card_id, replacement_source_id or None)
    causes = prepare_graveyard_entry_causes(state, [plan])
    if card_id in player.battlefield:
        emit_event(state, "leaves_battlefield", {"card_id": card_id, "controller": card.controller})
    was_creature = was_creature_on_battlefield(card)
    destination = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=causes[card_id])
    if destination != Zone.GRAVEYARD:
        state.log.append(
            f"State-based action: {state.players[player_id].name} keeps one {card.name}; the other {'is exiled' if destination == Zone.EXILE else f'is put into {destination.value}'} by a replacement effect (legend rule)."
        )
        return
    state.log.append(
        f"State-based action: {state.players[player_id].name} keeps one {card.name}; the other is put into graveyard (legend rule)."
    )
    emit_event(state, "permanent_dies", {"card_id": card_id, "controller": card.controller})
    if was_creature:
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
    plans = {
        cid: select_graveyard_entry_plan(state, cid)
        for cid in valid_ids
    }
    # Retain every replacement and receipt before any source leaves or loses abilities.
    causes = prepare_graveyard_entry_causes(state, plans.values())
    emit_event_batch(state, "leaves_battlefield", leave_events)
    creatures = {cid: was_creature_on_battlefield(state.cards[cid]) for cid in valid_ids}
    for cid in valid_ids:
        state.players[plans[cid].controller].battlefield.remove(cid)

    death_events: list[dict] = []
    creature_death_events: list[dict] = []
    entry_receipts: list[dict] = []
    for cid in valid_ids:
        card = state.cards[cid]
        destination = execute_graveyard_entry(state, plans[cid], prevalidated=True,
                                              _prepared_cause=causes[cid], _entry_receipts=entry_receipts)
        if destination != Zone.GRAVEYARD:
            state.log.append(f"State-based action: {card.name} {'is exiled' if destination == Zone.EXILE else f'is put into {destination.value}'} instead of dying.")
            continue
        state.log.append(f"State-based action: {card.name} is put into graveyard due to lethal damage or 0 toughness.")
        event = {"card_id": cid, "controller": card.controller}
        death_events.append(event)
        if creatures[cid]:
            creature_death_events.append(event)
    if entry_receipts:
        emit_event_batch(state, "enters_graveyard", entry_receipts)
    emit_event_batch(state, "permanent_dies", death_events)
    emit_event_batch(state, "creature_dies", creature_death_events)

def apply_state_based_actions(state: MatchState) -> None:
    if state.pending_mechanic_choice:
        return
    if state.pending_replacement_choice and state.pending_replacement_choice.get('resume_kind') == 'counter_event':
        return
    from rules_engine.linked_exile import flush_linked_exile_returns
    flush_linked_exile_returns(state)
    if state.pending_mechanic_choice or state.pending_replacement_choice:
        return
    if not state.trigger_staging:
        state.trigger_staging = True
        state.trigger_staging_event = "state_based_actions"
    # A source leaving the battlefield can make another permanent illegal or
    # lethal. No trigger gets a stack position until those waves stabilize.
    for _ in range(len(state.cards) + 1):
        with rule_query_scope(state):
            before = tuple((cid, card.zone, card.attached_to, tuple(effective_types(state, card)), bool(card.bestow_characteristics)) for cid, card in state.cards.items())
        _apply_state_based_actions_once(state)
        flush_linked_exile_returns(state)
        if state.pending_mechanic_choice or state.pending_replacement_choice:
            return
        with rule_query_scope(state):
            after = tuple((cid, card.zone, card.attached_to, tuple(effective_types(state, card)), bool(card.bestow_characteristics)) for cid, card in state.cards.items())
        if after == before:
            break
    from rules_engine.events import flush_staged_triggers
    flush_staged_triggers(state)
    from rules_engine.foretell import reveal_at_game_end
    reveal_at_game_end(state)


def _apply_state_based_actions_once(state: MatchState) -> None:
    from rules_engine.combat import remove_noncreatures_from_combat
    remove_noncreatures_from_combat(state)
    from rules_engine.alternative_casts import restore_printed_characteristics
    state.adventure_permissions = {cid: pid for cid, pid in state.adventure_permissions.items()
                                   if cid in state.cards and state.cards[cid].zone == Zone.EXILE}
    for card in state.cards.values():
        if card.zone not in {Zone.BATTLEFIELD, Zone.STACK}:
            from rules_engine.bestow import end_bestow
            end_bestow(card)
            restore_printed_characteristics(card)
    _cease_nonbattlefield_tokens(state)
    if state.winner is None:
        from rules_engine.replacement import player_cant_lose_game
        losing_players = set()
        for pid, player in state.players.items():
            if player_cant_lose_game(state, pid):
                # Failed draws are checked once; life/poison remain current state.
                state.failed_draw_players.discard(pid)
                continue
            if pid in state.failed_draw_players:
                losing_players.add(pid)
                state.log.append(f"{player.name} loses after attempting to draw from empty library.")
            if player.poison >= 10:
                losing_players.add(pid)
                state.log.append(f"{player.name} has ten or more poison counters and loses.")
            if player.life <= 0:
                losing_players.add(pid)
                state.log.append(f"{player.name} has 0 or less life and loses.")
        if losing_players:
            state.winner = 0 if len(losing_players) == 2 else (2 if 1 in losing_players else 1)
            if state.winner == 0:
                state.log.append("Both players lose simultaneously; the game is a draw.")

    # Reuse only this immutable scan; discard queries before any departures.
    with rule_query_scope(state):
        lethal_candidates = [cid for cid in state.cards if creature_has_lethal_state(state, cid)]
    lethal_ids: list[str] = []
    for cid in lethal_candidates:
        card = state.cards[cid]
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
        if card.zone == Zone.BATTLEFIELD and card.loyalty is not None and card.loyalty <= 0 and "Planeswalker" in effective_types(state, card):
            battlefield_owner = state.players[card.controller]
            if cid in battlefield_owner.battlefield:
                emit_event(state, "leaves_battlefield", {"card_id": cid, "controller": card.controller})
                battlefield_owner.battlefield.remove(cid)
                zone = put_into_graveyard(state, cid)
                state.log.append(f"State-based action: {card.name} is put into {zone.value} due to 0 loyalty.")
                if zone == Zone.GRAVEYARD:
                    emit_event(state, "permanent_dies", {"card_id": cid, "controller": card.controller})

    _apply_legend_rule(state)
    if state.pending_replacement_choice:
        return
    _apply_saga_state_actions(state)
    _apply_attachment_state_checks(state)


def _cease_nonbattlefield_tokens(state: MatchState) -> None:
    for cid, card in state.cards.items():
        if not is_token_card(card) or card.zone in {Zone.BATTLEFIELD, Zone.STACK, Zone.CEASED}:
            continue
        for player in state.players.values():
            for zone in ("library", "hand", "graveyard", "exile"):
                cards = getattr(player, zone)
                if cid in cards:
                    cards.remove(cid)
        card.zone = Zone.CEASED


def _apply_saga_state_actions(state: MatchState) -> None:
    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD or "Saga" not in (card.type_line or ""):
            continue
        chapters = [int(item) for item in _saga_chapter_numbers(card.oracle_text)]
        if not chapters or int(card.counters.get("__lore", 0) or 0) < max(chapters):
            continue
        from game_state.state import object_incarnation
        def chapter_pending(source_id, payload):
            return (source_id == cid and '__chapter_number' in payload
                    and not payload.get('__stack_copy_kind')
                    and payload.get('__chapter_incarnation') == object_incarnation(card))
        if any(chapter_pending(item.source_card_id, item.payload)
               # Pre-metadata snapshots used this exact chapter label. They lack
               # enough provenance to distinguish old battlefield incarnations.
               or (item.source_card_id == cid and '__chapter_number' not in item.payload
                   and not item.payload.get('__stack_copy_kind')
                   and item.label in {f'{card.name} chapter {number}' for number in chapters})
               for item in state.stack):
            continue
        pending_triggers = list(state.staged_triggers) + list(state.cleanup_deferred_triggers)
        for group in (state.pending_trigger_order or {}).get('groups', {}).values():
            pending_triggers.extend(group)
        if any(chapter_pending(item.get('source_card_id'), item.get('payload', {})) for item in pending_triggers):
            continue
        battlefield = state.players[card.controller]
        if cid not in battlefield.battlefield:
            continue
        from effects.registry import resolve_effect
        resolve_effect(state, card.controller, 'sacrifice', {'target_card_id': cid})
        state.log.append(f"State-based action: {card.name} is sacrificed after its final chapter.")


def _saga_chapter_numbers(oracle_text: str) -> list[int]:
    from rules_engine.oracle_effects import extract_saga_chapters

    return [int(item["number"]) for item in extract_saga_chapters(oracle_text)]


def _apply_legend_rule(state: MatchState) -> None:
    groups = _legend_keeper_groups(state)
    humans = set(state.mechanic_choice_players or set())
    if any(group['player_id'] in humans for group in groups):
        context = {'groups': groups, 'keepers': {
            str(index): group['card_ids'][0] for index, group in enumerate(groups)
            if group['player_id'] not in humans}, 'plans': {}}
        _continue_legend_keeper(state, context)
        return
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


def _legend_keeper_groups(state: MatchState) -> list[dict]:
    from game_state.state import object_incarnation

    groups = []
    players = [state.active_player] + [pid for pid in state.players if pid != state.active_player]
    for pid in players:
        names = {}
        for cid in state.players[pid].battlefield:
            card = state.cards[cid]
            if card.zone == Zone.BATTLEFIELD and card.controller == pid and _is_legendary(card):
                names.setdefault(card.name.lower(), []).append(cid)
        for name, ids in names.items():
            if len(ids) > 1:
                groups.append({'player_id': pid, 'name': name, 'card_ids': ids,
                               'references': {cid: [object_incarnation(state.cards[cid]),
                                   state.cards[cid].zone_change_sequence, state.cards[cid].owner]
                                   for cid in ids}})
    return groups


def _validate_legend_keeper_context(state: MatchState, context: dict) -> None:
    from rules_engine.action_validation import ActionRejected

    def references(groups):
        return {(group['player_id'], group['name']): group['references'] for group in groups}

    if references(_legend_keeper_groups(state)) != references(context['groups']):
        raise ActionRejected('Legend keeper group is no longer available')
    for index, keeper in context['keepers'].items():
        if keeper not in context['groups'][int(index)]['card_ids']:
            raise ActionRejected('Unavailable legend keeper')


def _continue_legend_keeper(state: MatchState, context: dict) -> None:
    from dataclasses import asdict
    from rules_engine.action_validation import ActionRejected
    from rules_engine.replacement import graveyard_entry_plans, select_graveyard_entry_plan
    from rules_engine.zone_actions import prepare_graveyard_entry_causes, execute_graveyard_entry

    _validate_legend_keeper_context(state, context)
    for index, group in enumerate(context['groups']):
        if str(index) not in context['keepers']:
            state.pending_replacement_choice = None
            state.pending_mechanic_choice = {
                'kind': 'legend_keeper', 'player_id': group['player_id'], 'count': 1,
                'options': list(group['card_ids']), 'label': 'Choose a legendary permanent to keep',
                'legend_group_index': index, 'legend_context': context}
            state.priority_player = group['player_id']
            state.passed_priority = set()
            return

    losers = [cid for index, group in enumerate(context['groups']) for cid in group['card_ids']
              if cid != context['keepers'][str(index)]]
    candidates = {cid: list(graveyard_entry_plans(state, cid)) for cid in losers}
    signatures = {cid: [asdict(plan) for plan in plans] for cid, plans in candidates.items()}
    if 'candidates' in context and context['candidates'] != signatures:
        raise ActionRejected('Legend replacement plans are no longer available')
    context['candidates'] = signatures
    selected = {}
    for cid, plans in candidates.items():
        retained = context['plans'].get(cid)
        if retained is not None:
            plan = next((plan for plan in plans if asdict(plan) == retained), None)
            if plan is None:
                raise ActionRejected('Legend replacement selection is no longer available')
        elif len(plans) > 1 and _human_die_choice_required(state, cid):
            state.pending_mechanic_choice = None
            state.pending_replacement_choice = {
                'resume_kind': 'legend_keeper_die', 'player_id': state.cards[cid].controller,
                'event': 'die_zone', 'target_card_id': cid, 'legend_context': context,
                'options': [{'source_id': plan.replacement_source_id,
                             'name': state.cards[plan.replacement_source_id].name}
                            for plan in plans]}
            state.priority_player = state.cards[cid].controller
            state.passed_priority = set()
            return
        else:
            if len(plans) > 1 and state.cards[cid].controller in set(state.mechanic_choice_players or set()):
                raise ActionRejected('Human legend replacement selection requires an enabled continuation')
            plan = select_graveyard_entry_plan(state, cid)
            context['plans'][cid] = asdict(plan)
        selected[cid] = plan

    # Retain the entire batch and every shuffle cause before the first departure.
    causes = prepare_graveyard_entry_causes(state, selected.values())
    state.pending_mechanic_choice = None
    state.pending_replacement_choice = None
    leave = [{'card_id': cid, 'controller': selected[cid].controller} for cid in losers]
    emit_event_batch(state, 'leaves_battlefield', leave)
    creatures = {cid for cid in losers if was_creature_on_battlefield(state.cards[cid])}
    for cid in losers:
        state.players[selected[cid].controller].battlefield.remove(cid)
    for cid in losers:
        execute_graveyard_entry(state, selected[cid], prevalidated=True, _prepared_cause=causes[cid])
        state.log.append(f'State-based action: {state.cards[cid].name} is put into {selected[cid].destination.value} (legend rule).')
    died = [event for event in leave if selected[event['card_id']].destination == Zone.GRAVEYARD]
    emit_event_batch(state, 'permanent_dies', died)
    emit_event_batch(state, 'creature_dies', [event for event in died if event['card_id'] in creatures])


def finish_legend_keeper_choice(state: MatchState, player_id: int, action: dict) -> bool:
    from copy import deepcopy

    pending = state.pending_mechanic_choice
    if (not pending or pending.get('kind') != 'legend_keeper' or player_id != pending['player_id']
            or action.get('type') != 'choose_mechanic' or len(action.get('card_ids', [])) != 1
            or action['card_ids'][0] not in pending['options']):
        return False
    context = deepcopy(pending['legend_context'])
    _validate_legend_keeper_context(state, context)
    context['keepers'][str(pending['legend_group_index'])] = action['card_ids'][0]
    _continue_legend_keeper(state, context)
    return True


def finish_legend_keeper_replacement(state: MatchState, player_id: int, source_id: str) -> bool:
    from copy import deepcopy
    from rules_engine.action_validation import ActionRejected

    pending = state.pending_replacement_choice
    if (not pending or pending.get('resume_kind') != 'legend_keeper_die'
            or player_id != pending['player_id']):
        return False
    context = deepcopy(pending['legend_context'])
    _validate_legend_keeper_context(state, context)
    cid = pending['target_card_id']
    chosen = next((plan for plan in context['candidates'][cid]
                   if plan['replacement_source_id'] == source_id), None)
    if chosen is None:
        raise ActionRejected('Unavailable legend replacement source')
    context['plans'][cid] = chosen
    _continue_legend_keeper(state, context)
    return True


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
    from rules_engine.replacement import select_graveyard_entry_plan
    from rules_engine.zone_actions import prepare_graveyard_entry_causes, execute_graveyard_entry

    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD:
            continue
        target_id = attached_to(card)
        from rules_engine.bestow import is_bestowed, end_bestow
        with rule_query_scope(state):
            aura, equipment, fortification = is_aura(card, state), is_equipment(card, state), is_fortification(card, state)
        if not (aura or equipment or fortification):
            if target_id:
                if is_bestowed(card):
                    end_bestow(card)
                else:
                    card.attached_to = None
                state.log.append(f'State-based action: {card.name} becomes unattached.')
            continue
        if is_bestowed(card) and not attachment_target_is_legal(state, card, target_id):
            end_bestow(card)
            state.log.append(f'State-based action: {card.name} ceases to be bestowed.')
            continue
        if not target_id:
            if aura:
                owner = state.players[card.controller]
                if cid in owner.battlefield:
                    plan = select_graveyard_entry_plan(state, cid)
                    cause = prepare_graveyard_entry_causes(state, [plan])[cid]
                    emit_event(state, 'leaves_battlefield', {'card_id': cid, 'controller': card.controller})
                    owner.battlefield.remove(cid)
                    zone = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=cause)
                    state.log.append(f"State-based action: {card.name} has no legal attachment and is put into {zone.value}.")
            continue
        target = state.cards.get(target_id)
        if not attachment_target_is_legal(state, card, target_id):
            if aura:
                owner = state.players[card.controller]
                if cid in owner.battlefield:
                    plan = select_graveyard_entry_plan(state, cid)
                    cause = prepare_graveyard_entry_causes(state, [plan])[cid]
                    emit_event(state, 'leaves_battlefield', {'card_id': cid, 'controller': card.controller})
                    owner.battlefield.remove(cid)
                    zone = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=cause)
                    state.log.append(f"State-based action: {card.name} loses attachment and is put into {zone.value}.")
            elif equipment or fortification:
                card.attached_to = None
                state.log.append(f"State-based action: {card.name} becomes unattached.")
