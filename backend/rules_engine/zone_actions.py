from __future__ import annotations

from game_state.state import Zone
from rules_engine.card_types import is_token_card
from rules_engine.events import emit_event_batch
from rules_engine.replacement import graveyard_entry_plans, select_graveyard_entry_plan


def prepare_graveyard_entry_causes(state, plans):
    """Validate the complete batch and prepare receipts before any departure."""
    from rules_engine.action_validation import ActionRejected
    from rules_engine.replacement import GraveyardEntryPlan
    from rules_engine.shuffle_actions import prepare_static_replacement_cause
    plans = tuple(plans)
    if (any(type(plan) is not GraveyardEntryPlan or plan.card_id not in state.cards
            or plan not in graveyard_entry_plans(state, plan.card_id) for plan in plans)
            or len({plan.card_id for plan in plans}) != len(plans)):
        raise ActionRejected('Graveyard entry batch is no longer available')
    return {plan.card_id: prepare_static_replacement_cause(state, plan)
            if plan.reveal_shuffle else None for plan in plans}


def execute_graveyard_entry(state, plan, *, prevalidated=False, resolving_item=None,
                           _prepared_cause=None) -> Zone:
    """Execute a retained entry plan after the caller has validated its selection."""
    from game_state.state import object_incarnation
    from rules_engine.action_validation import ActionRejected
    card = state.cards.get(plan.card_id)
    if (card is None or card.zone != plan.origin or card.owner != plan.owner
            or card.controller != plan.controller or object_incarnation(card) != plan.incarnation
            or card.zone_change_sequence != plan.sequence
            or not prevalidated and plan not in graveyard_entry_plans(state, card.id)):
        raise ActionRejected('Graveyard entry plan is no longer available')
    if plan.reveal_shuffle:
        from rules_engine.shuffle_actions import prepare_static_replacement_cause, StaticReplacementCause
        if _prepared_cause is None:
            _prepared_cause = prepare_static_replacement_cause(state, plan)
        if (type(_prepared_cause) is not StaticReplacementCause
                or (_prepared_cause.source_card_id, _prepared_cause.controller,
                    _prepared_cause.source_owner, _prepared_cause.source_zone,
                    _prepared_cause.incarnation, _prepared_cause.zone_change_sequence)
                != (plan.card_id, plan.controller, plan.owner, plan.origin,
                    plan.source_incarnation, plan.source_sequence)):
            raise ActionRejected('Prepared replacement cause does not match entry plan')
    elif _prepared_cause is not None:
        raise ActionRejected('Entry plan does not cause a replacement shuffle')
    holder = state.players[plan.controller if plan.origin == Zone.BATTLEFIELD else plan.owner]
    origin_ids = getattr(holder, plan.origin.value, [])
    if card.id in origin_ids:
        origin_ids.remove(card.id)
    if plan.reveal_shuffle:
        state.log.append(f'{state.players[plan.owner].name} reveals {card.name}.')
    destination = getattr(state.players[plan.owner], plan.destination.value)
    if card.id not in destination:
        destination.append(card.id)
    card.move_to_zone(plan.destination)
    if plan.reveal_shuffle:
        from rules_engine.shuffle_actions import shuffle_library
        # The printed replacement caused this shuffle, not an announcing spell.
        shuffle_library(state, plan.owner, cause=_prepared_cause)
    return plan.destination


def is_departed_token(card) -> bool:
    return card.zone != Zone.BATTLEFIELD and is_token_card(card)


def sacrifice_selected(state, controller, ids, *, replacement_choices=None):
    """Sacrifice a selected set simultaneously, preserving LKI and events."""
    from rules_engine.events import was_creature_on_battlefield, flush_staged_triggers
    if len(set(ids)) != len(ids) or any(cid not in state.players[controller].battlefield for cid in ids):
        return False
    if replacement_choices is not None and (not isinstance(replacement_choices, dict)
                                           or set(replacement_choices) - set(ids)):
        return False
    plans = {cid: select_graveyard_entry_plan(state, cid, (replacement_choices or {}).get(cid))
             for cid in ids}
    causes = prepare_graveyard_entry_causes(state, plans.values())
    staged_here = not state.trigger_staging
    if staged_here:
        state.trigger_staging = True
        state.trigger_staging_event = "sacrifice"
    events = [{"card_id": cid, "controller": controller} for cid in ids]
    emit_event_batch(state, "leaves_battlefield", events)
    for cid in ids:
        execute_graveyard_entry(state, plans[cid], prevalidated=True, _prepared_cause=causes[cid])
    emit_event_batch(state, "sacrifice", events)
    died = [event for event in events if state.cards[event["card_id"]].zone == Zone.GRAVEYARD]
    emit_event_batch(state, "permanent_dies", died)
    emit_event_batch(state, "creature_dies", [event for event in died if was_creature_on_battlefield(state.cards[event["card_id"]])])
    if staged_here and not state.pending_mechanic_choice:
        flush_staged_triggers(state)
    return True


def put_into_graveyard(state, cid: str, *, replacement_source_id=None, resolving_item=None) -> Zone:
    """Move an already-removed card to its actual destination after replacement."""
    card = state.cards[cid]
    if is_departed_token(card):
        return card.zone
    return execute_graveyard_entry(state, select_graveyard_entry_plan(state, cid, replacement_source_id),
                                  resolving_item=resolving_item)


def move_spell_from_stack(state, item, destination: Zone = Zone.GRAVEYARD) -> Zone | None:
    """Apply stack-departure replacements before restoring the physical card."""
    payload = item.payload or {}
    card = state.cards.get(item.source_card_id)
    if payload.get("__stack_copy_kind") or card is None or card.zone != Zone.STACK:
        return None
    if payload.get("__flashback") or payload.get("__aftermath"):
        destination = Zone.EXILE
    if destination == Zone.GRAVEYARD and payload.get('__exile_instead_of_graveyard'):
        destination = Zone.EXILE
    if destination == Zone.GRAVEYARD:
        destination = put_into_graveyard(state, card.id)
    else:
        zone_ids = getattr(state.players[card.owner], destination.value)
        if card.id not in zone_ids:
            zone_ids.append(card.id)
        card.move_to_zone(destination)
    from rules_engine.alternative_casts import restore_printed_characteristics
    restore_printed_characteristics(card)
    return destination


def discard_selected(state, player_id: int, card_ids: list[str]) -> bool:
    return discard_simultaneous(state, {player_id: card_ids})


def exile_selected_from_hand(state, player_id: int, card_ids: list[str]) -> bool:
    hand = state.players[player_id].hand
    if (len(set(card_ids)) != len(card_ids)
            or any(cid not in hand or state.cards[cid].zone != Zone.HAND for cid in card_ids)):
        return False
    for cid in card_ids:
        card = state.cards[cid]
        hand.remove(cid)
        state.players[card.owner].exile.append(cid)
        card.move_to_zone(Zone.EXILE)
        state.log.append(f"{state.players[player_id].name} exiles {card.name} from their hand.")
    return True


def discard_simultaneous(state, selections: dict[int, list[str]]) -> bool:
    """Validate every hand before any card moves, then emit one discard event batch."""
    for player_id, card_ids in selections.items():
        if player_id not in state.players or not isinstance(card_ids, list) or any(not isinstance(cid, str) for cid in card_ids) or len(set(card_ids)) != len(card_ids):
            return False
        hand = state.players[player_id].hand
        if any(cid not in hand or state.cards[cid].zone != Zone.HAND or is_departed_token(state.cards[cid]) for cid in card_ids):
            return False
    plans = {cid: select_graveyard_entry_plan(state, cid)
             for card_ids in selections.values() for cid in card_ids}
    causes = prepare_graveyard_entry_causes(state, plans.values())
    events = []
    for player_id, card_ids in selections.items():
        player = state.players[player_id]
        for cid in card_ids:
            card = state.cards[cid]
            player.hand.remove(cid)
            execute_graveyard_entry(state, plans[cid], prevalidated=True, _prepared_cause=causes[cid])
            state.log.append(f"{player.name} discards {card.name}.")
            events.append({"card_id": cid, "controller": player_id})
        state.discards_this_turn[player_id] = state.discards_this_turn.get(player_id, 0) + len(card_ids)
    if events:
        emit_event_batch(state, "discard", events)
    return True
