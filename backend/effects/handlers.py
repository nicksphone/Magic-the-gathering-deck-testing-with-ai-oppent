from __future__ import annotations
from rules_engine.type_effects import effective_types

import copy
import re

from game_state.state import MatchState, Zone, assign_static_order_on_battlefield_entry, draw_card, object_incarnation, allocate_effect_timestamp
from card_data.token_images import resolve_token_image_uri
from rules_engine.continuous import effective_keywords, effective_toughness, effective_combat_stats, has_keyword
from rules_engine.counter_placement import put_counters
from rules_engine.counter_replacements import counter_effect_amount
from rules_engine.entry import apply_entry_choice, pause_for_land_entries
from rules_engine.graveyard_permissions import battlefield_entry_prohibited
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
    select_graveyard_entry_plan,
    replace_draw_cards,
    replace_gain_life,
    replace_noncombat_damage_to_creature,
)
from rules_engine.zone_actions import (
    move_spell_from_stack, is_departed_token, put_into_graveyard,
    execute_graveyard_entry, prepare_graveyard_entry_causes,
)


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
        source_card_id=payload.get('__source_card_id'),
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


def set_combat_cost(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import allocate_effect_timestamp
    source = state.cards.get(payload.get('__source_card_id'))
    cost = payload['mana_cost']
    state.combat_cost_effects.append({
        'kind': payload['kind'], 'scope': 'all', 'mana_cost': cost,
        'amount': sum(int(symbol) for symbol in re.findall(r'\{(\d+)\}', cost)),
        'controller': controller, 'source_id': source.id if source else payload.get('__source_card_id'),
        'source_name': source.name if source else payload.get('source_name'),
        'timestamp': allocate_effect_timestamp(state), 'expires_turn': state.turn,
        'clause': payload['clause'], 'origin': 'resolution',
    })
    state.log.append(f"Combat {payload['kind']} cost {cost} applies to each declared creature this turn.")


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
    toughness = effective_combat_stats(state, card_id)[1]
    if toughness is None:
        return False
    if has_keyword(state, card_id, "indestructible"):
        return False
    marked = int(card.counters.get(DMG_MARK_KEY, 0))
    if marked >= toughness:
        return True
    if int(card.counters.get(DEATHTOUCH_MARK_KEY, 0)) > 0:
        return True
    return False


def _move_creature_to_graveyard(state: MatchState, card_id: str) -> None:
    card = state.cards[card_id]
    battlefield_owner = state.players[card.controller]
    if card_id in battlefield_owner.battlefield:
        plan = select_graveyard_entry_plan(state, card_id)
        cause = prepare_graveyard_entry_causes(state, [plan])[card_id]
        event = {"card_id": card_id, "controller": plan.controller}
        emit_event(state, "leaves_battlefield", event)
        destination = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=cause)
        if destination == Zone.EXILE:
            state.log.append(f"{card.name} is exiled instead of dying.")
        elif destination == Zone.GRAVEYARD:
            state.log.append(f"{card.name} dies.")
            emit_event(state, "permanent_dies", event)
            emit_event(state, "creature_dies", event)


def deal_damage_to_controller(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve the referenced object's current controller, not a cast-time seat."""
    target = state.cards.get(payload.get('target_card_id'))
    if target is None:
        return
    damage = dict(payload)
    damage.pop('target_card_id', None)
    damage['target_player'] = target.controller
    deal_damage(state, controller, damage)


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
    if target_card_id is not None and target_card_id in state.cards:
        card = state.cards[target_card_id]
        source = state.cards.get(source_card_id)
        if not prevention_locked:
            from rules_engine.protection import protection_match_reason
            reason = protection_match_reason(state, target_card_id, source, source_lki=source_lki)
            if reason is not None and (source is not None or source_lki is not None or reason == "everything"):
                state.log.append(f"{card.name} prevents damage from {reason} source due to protection.")
                return 0
        if card.zone == Zone.BATTLEFIELD and amount > 0:
            if replace_noncombat_damage_to_creature(state, source_card_id, target_card_id, amount, source_lki=source_lki) is not None:
                if not state.trigger_staging and not state.pending_replacement_choice and not payload.get("__defer_lethal") and "Creature" in effective_types(state, card) and _creature_is_lethally_damaged(state, target_card_id):
                    _move_creature_to_graveyard(state, target_card_id)
                return 0
            replaced_amount = apply_permanent_damage_replacements(
                state,
                target_card_id,
                amount,
                replacement_source_id=selected_source_id,
                max_replacements=1 if human_chain else None,
                used_source_ids=payload.get('__used_replacement_source_ids'),
                prevention_locked=prevention_locked,
            )
            if human_chain and _queue_human_damage_replacement_choice(state, controller, payload, replaced_amount, selected_source_id):
                return 0
            post, prevented = (replaced_amount, 0) if prevention_locked else consume_card_prevention_shield(card, replaced_amount)
            if prevented > 0:
                state.log.append(f"{card.name} prevents {prevented} damage.")
            if post <= 0:
                return 0
            from rules_engine.damage_results import apply_creature_damage
            if "Creature" in effective_types(state, card):
                apply_creature_damage(state, target_card_id, int(post), source_card_id, source_lki=source_lki,
                                      controller=controller, counter_is_effect=True)
                state.log.append(f"{card.name} takes {post} damage.")
            if "Planeswalker" in effective_types(state, card) and card.loyalty is not None:
                card.loyalty -= int(post)
                state.log.append(f"{card.name} loses {post} loyalty.")
            if not payload.get("__batch_damage"):
                _gain_lifelink_from_damage(state, source_card_id, int(post), source_lki)
            emit_event(state, 'damage_dealt', {'source_card_id': source_card_id,
                       'target_card_id': target_card_id, 'amount': int(post)})
            # A staged spell/ability finishes all instructions before its SBA check.
            if (not state.trigger_staging and not state.pending_replacement_choice
                    and not payload.get("__defer_lethal") and "Creature" in effective_types(state, card)
                    and _creature_is_lethally_damaged(state, target_card_id)):
                _move_creature_to_graveyard(state, target_card_id)
            return int(post)
    if target_player is not None:
        replaced_amount = apply_damage_replacements(
            state,
            int(target_player),
            amount,
            replacement_source_id=selected_source_id,
            max_replacements=1 if human_chain else None,
            used_source_ids=payload.get('__used_replacement_source_ids'),
            prevention_locked=prevention_locked,
        )
        if human_chain and _queue_human_damage_replacement_choice(state, controller, payload, replaced_amount, selected_source_id):
            return 0
        post, prevented = (replaced_amount, 0) if prevention_locked else consume_player_prevention_shield(state, int(target_player), replaced_amount)
        if prevented > 0:
            state.log.append(f"{state.players[target_player].name} prevents {prevented} damage.")
        if post <= 0:
            return 0
        from rules_engine.damage_results import apply_player_damage
        apply_player_damage(state, int(target_player), int(post), source_card_id, source_lki=source_lki,
                            controller=controller, counter_is_effect=True)
        state.log.append(f"{state.players[target_player].name} takes {post} damage.")
        if not payload.get("__batch_damage"):
            _gain_lifelink_from_damage(state, source_card_id, int(post), source_lki)
        emit_event(state, 'damage_dealt', {'source_card_id': source_card_id,
                   'target_player': int(target_player), 'amount': int(post)})
        return int(post)
    return 0


def _gain_lifelink_from_damage(state: MatchState, source_id: str | None, amount: int,
                               source_lki: dict | None = None) -> None:
    from rules_engine.damage_results import source_has_keyword
    if amount > 0 and source_has_keyword(state, source_id, "lifelink", source_lki):
        source_controller = int(source_lki["controller"]) if source_lki is not None else state.cards[source_id].controller
        payload = {
            "target_player": source_controller, "amount": amount, "__source_card_id": source_id,
        }
        pending = state.pending_replacement_choice or state.pending_mechanic_choice
        if pending:
            pending.setdefault('continuation_effects', []).append({'effect_key': 'gain_life', 'payload': payload})
        else:
            gain_life(state, source_controller, payload)


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
    from rules_engine.continuous import _has_subtype
    card_types = {'creature', 'artifact', 'enchantment', 'land', 'planeswalker', 'battle', 'instant', 'sorcery', 'kindred', 'tribal'}
    for cid in state.players[controller].battlefield:
        card = state.cards[cid]
        types = {str(value).lower().rstrip("s") for value in (effective_types(state, card) or [])}
        type_line = str(getattr(card, "type_line", "") or "").lower()
        # Printed type words cannot restore removed types or creature subtypes.
        subtype_match = (_has_subtype(card, needle, state=state) if 'Creature' in card.types
                         else needle in type_line.split())
        if needle in types or (needle not in card_types and subtype_match):
            count += 1
    return count


def destroy_permanent(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    battlefield_owner = state.players[card.controller]
    if target in battlefield_owner.battlefield:
        from rules_engine.named_counters import destruction_prevented
        # Prevented destruction needs no graveyard replacement choice.
        if has_keyword(state, target, "indestructible") or card.counters.get('shield', 0) > 0:
            destruction_prevented(state, target)
            return
        plan = select_graveyard_entry_plan(state, target, payload.get("__replacement_source_id"))
        cause = prepare_graveyard_entry_causes(state, [plan])[target]
        if destruction_prevented(state, target):
            return
        event = {"card_id": target, "controller": plan.controller}
        emit_event(state, "leaves_battlefield", event)
        destination = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=cause)
        if destination == Zone.EXILE:
            state.log.append(f"{card.name} is exiled instead of dying.")
            return
        if destination != Zone.GRAVEYARD:
            return
        state.log.append(f"{card.name} is destroyed.")
        emit_event(state, "permanent_dies", event)
        if was_creature_on_battlefield(card):
            emit_event(state, "creature_dies", event)


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
        card.summoning_sick = True
        card.entered_turn = state.turn
    if payload.get("until_end_of_turn"):
        state.temporary_control_changes[target_id] = {
            "controller": old_controller,
            "expires_turn": int(state.turn),
        }
    state.log.append(f"{state.players[new_controller].name} gains control of {card.name}.")
def destroy_all_creatures(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    _destroy_all_permanents_of_types(state, {"Creature"}, "All creatures are destroyed.")


def _destroy_all_permanents_of_types(state: MatchState, allowed_types: set[str], log_label: str) -> None:
    from rules_engine.named_counters import destruction_prevented
    from rules_engine.events import flush_staged_triggers
    targets = [cid for cid, card in state.cards.items()
               if allowed_types.intersection(set(effective_types(state, card) or []))
               and cid in state.players[card.controller].battlefield]
    # Shield consumption/logging is a mutation: preflight every actual death first.
    plans = {cid: select_graveyard_entry_plan(state, cid) for cid in targets
             if not has_keyword(state, cid, "indestructible")
             and state.cards[cid].counters.get('shield', 0) <= 0}
    causes = prepare_graveyard_entry_causes(state, plans.values())
    for cid in targets:
        destruction_prevented(state, cid)
    if not plans:
        return
    started_staging = not state.trigger_staging
    if started_staging:
        state.trigger_staging = True
        state.trigger_staging_event = "permanent_dies"
    leaves = [{"card_id": cid, "controller": plan.controller} for cid, plan in plans.items()]
    emit_event_batch(state, "leaves_battlefield", leaves)
    permanent_deaths = []
    creature_deaths = []
    entry_receipts = []
    for event in leaves:
        cid = event["card_id"]
        card = state.cards[cid]
        destination = execute_graveyard_entry(state, plans[cid], prevalidated=True,
                                              _prepared_cause=causes[cid], _entry_receipts=entry_receipts)
        if destination == Zone.EXILE:
            state.log.append(f"{card.name} is exiled instead of dying.")
        elif destination == Zone.GRAVEYARD:
            state.log.append(f"{card.name} is destroyed.")
            permanent_deaths.append(event)
            if was_creature_on_battlefield(card):
                creature_deaths.append(event)
    if entry_receipts:
        emit_event_batch(state, "enters_graveyard", entry_receipts)
    emit_event_batch(state, "permanent_dies", permanent_deaths)
    emit_event_batch(state, "creature_dies", creature_deaths)
    state.log.append(log_label)
    if started_staging and not state.pending_mechanic_choice:
        flush_staged_triggers(state)


def exile_all_graveyards(state: MatchState, controller: int, payload: dict) -> None:
    del controller, payload
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, [cid for player in state.players.values() for cid in player.graveyard])
    for player in state.players.values():
        for cid in list(player.graveyard):
            if is_departed_token(state.cards[cid]):
                continue
            player.graveyard.remove(cid)
            state.players[state.cards[cid].owner].exile.append(cid)
            state.cards[cid].move_to_zone(Zone.EXILE)
    state.log.append("All graveyards are exiled.")
    emit_graveyard_departures(state, departures)


def exile_all_creatures(state: MatchState, controller: int, payload: dict) -> int:
    """Exile every creature, preserving ownership and leave events."""
    moved = 0
    leaves: list[dict] = []
    for player in state.players.values():
        for cid in player.battlefield:
            if "Creature" in effective_types(state, state.cards[cid]):
                capture_last_known_battlefield(state, cid)
    for cid, card in list(state.cards.items()):
        if card.zone != Zone.BATTLEFIELD or "Creature" not in effective_types(state, card):
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


def exile_until_source_leaves(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.card_types import is_token_card
    from rules_engine.linked_exile import record_linked_exile, source_still_present
    source_id, timestamp = payload['source_card_id'], int(payload['source_timestamp'])
    target = state.cards.get(payload.get('target_card_id'))
    if not source_still_present(state, source_id, timestamp) or target is None or target.zone != Zone.BATTLEFIELD:
        return
    exile_permanent(state, controller, payload)
    if target.zone == Zone.EXILE and not is_token_card(target):
        record_linked_exile(state, source_id, timestamp, [target.id])


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
    from rules_engine.type_effects import copiable_types, rebase_type_effects
    for field in ("name", "mana_cost", "type_line", "types", "power", "toughness", "printed_power", "printed_toughness", "loyalty", "oracle_text", "keywords", "colors"):
        source.printed_characteristics.setdefault(field, copiable_types(source) if field == 'types' else copy(getattr(source, field)))
        setattr(source, field, copy(getattr(selected, field)))
    rebase_type_effects(source)
    state.log.append(f"{previous_name} becomes a copy of {selected.name}.")


def exile_all_creatures_incubate(state: MatchState, controller: int, payload: dict) -> None:
    moved = exile_all_creatures(state, controller, payload)
    incubate(state, controller, {"counters": moved})


def exile_colored_permanents_mana_value_at_most(state: MatchState, controller: int, payload: dict) -> None:
    del controller
    mv_max = int(payload["mv_max"])
    affected = [
        cid for player in state.players.values() for cid in player.battlefield
        if card_color_names(state.cards[cid], state) and mana_value(state.cards[cid].mana_cost or "") <= mv_max
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
    from rules_engine.targeting import spell_cant_be_countered, stack_object_kind, stack_source_card
    target_stack_id = payload.get("target_stack_id")
    for i, item in enumerate(state.stack):
        if item.id == target_stack_id:
            if stack_object_kind(state, item) != "spell":
                return
            source = stack_source_card(state, item)
            if payload.get("target_kind") == "noncreature" and source and "Creature" in (effective_types(state, source) or []):
                return
            restrictions = payload.get("target_restrictions") or {}
            if restrictions:
                from rules_engine.oracle_effects import _target_card_matches_restrictions
                if not _target_card_matches_restrictions(
                    state, source, restrictions, controller,
                    x_value=int((item.payload or {}).get("x_value", 0) or 0),
                ):
                    return
            if payload.get("uncounterable") or spell_cant_be_countered(state, item):
                state.log.append(f"{item.label} can't be countered.")
                return
            popped = state.stack.pop(i)
            card = state.cards.get(popped.source_card_id)
            if card and not (popped.payload or {}).get("__stack_copy_kind"):
                move_spell_from_stack(state, popped, Zone(payload.get('destination', 'graveyard')))
            state.log.append(f"{item.label} was countered.")
            return


def counter_spell_unless_pay(state: MatchState, controller: int, payload: dict) -> None:
    """Counter a spell unless its controller chooses and can pay the tax.

    Human target controllers receive a durable owned payment choice. Direct
    automated callers retain the optional legacy override and pay-if-legal
    default. Declared stack kinds distinguish spells and abilities.
    """
    target_stack_id = payload.get("target_stack_id")
    item = next((entry for entry in state.stack if entry.id == target_stack_id), None)
    if item is None:
        return
    from rules_engine.targeting import spell_cant_be_countered, stack_object_kind, stack_source_card
    kind = stack_object_kind(state, item)
    if kind not in payload.get('stack_kinds', ['spell']):
        return
    source = stack_source_card(state, item)
    if kind == 'spell' and payload.get("target_kind") == "noncreature" and source and "Creature" in (effective_types(state, source) or []):
        return
    if item.controller in state.mechanic_choice_players:
        from rules_engine.ward import can_pay
        cost = {'kind': 'mana', 'cost': str(payload.get('unless_cost') or '{2}')}
        state.pending_mechanic_choice = {
            'kind': 'counter_payment', 'player_id': item.controller, 'count': 1,
            'options': ['decline', 'pay'] if can_pay(state, item.controller, cost) else ['decline'],
            'option_labels': {'pay': f"Pay {cost['cost']}", 'decline': 'Decline payment'},
            'label': f"Pay {cost['cost']} to keep {item.label}?", 'ward_cost': cost,
            'effect_payload': {**payload, 'ward_cost': cost['cost']}, 'controller': controller,
        }
        state.priority_player = item.controller
        state.passed_priority = set()
        return
    if payload.get("uncounterable") or (spell_cant_be_countered(state, item) if kind == 'spell' else (item.payload or {}).get('uncounterable')):
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
    handler = counter_spell if kind == 'spell' else counter_ability
    handler(state, controller, {"target_stack_id": target_stack_id})


def counter_ability(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.targeting import stack_object_kind
    del controller
    target_stack_id = payload.get("target_stack_id")
    for i, item in enumerate(state.stack):
        if item.id == target_stack_id:
            kind = stack_object_kind(state, item)
            if kind == "spell" or (payload.get("target_kind") in {"activated", "triggered"} and payload["target_kind"] != kind):
                return
            if payload.get("uncounterable") or (item.payload or {}).get("uncounterable"):
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
    copied_payload.pop("__last_target_ids", None)
    from game_state.state import StackItem
    from rules_engine.targeting import stack_object_kind

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
                            "toughness", "printed_power", "printed_toughness", "loyalty", "keywords", "colors", "image_uri",
                            "layout", "card_faces", "selected_face_index", "bestow_characteristics")
            }
    copied_payload["__stack_copy_kind"] = kind
    copied_payload["__source_card_id"] = item.source_card_id
    copied_payload["__copied_from_stack_id"] = item.id
    copied_payload["__copied_targets"] = list(getattr(item, "targets", []) or [])
    copied_effect_key = item.effect_key
    if copied_effect_key == 'foretell_spell':
        branch = copied_payload['branches'][0]
        copied_effect_key = branch['effect_key']
        copied_payload = {**branch['payload'], **{key: value for key, value in copied_payload.items()
                          if key.startswith('__') or key in {'x_value', 'snow_mana_spent', 'snow_mana_colors'}}}
    copied_item = StackItem(
        id=state.allocate_object_id(), source_card_id=item.source_card_id,
        controller=controller, label=f"{item.label} (copy)",
        effect_key=copied_effect_key, payload=copied_payload,
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
    if is_spell and copied_payload.get('__linked_target_instances'):
        from rules_engine.linked_targets import offer_linked_copy_target_choice
        offer_linked_copy_target_choice(state, copied_item)
        return
    if is_spell and (copied_payload.get('__ordered_target_instances')
                     or copied_payload.get('__ordered_distinct_targets')):
        from rules_engine.ordered_targets import offer_ordered_copy_target_choice
        offer_ordered_copy_target_choice(state, copied_item)
        return
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
    if is_spell and copied_item.effect_key == "effect_sequence" and not announced.get("mode_texts"):
        _offer_clause_copy_target_choice(state, controller, copied_item)
        return
    target_keys = [key for key in ("target_player", "target_card_id", "target_stack_id") if announced.get(key) is not None]
    if (len(target_keys) != 1 or any(key in announced for key in ("mode_targets", "target_card_ids", "target_distribution"))
            or copied_item.effect_key == "effect_sequence"):
        return
    from rules_engine.targeting import stack_source_card
    copied_card = stack_source_card(state, copied_item)
    if copied_card is None:
        return
    copied_card = copy.copy(copied_card)
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


def _offer_clause_copy_target_choice(
    state: MatchState, controller: int, copied_item,
    remaining_indices: list[int] | None = None, slot_number: int = 1,
) -> None:
    from rules_engine.oracle_effects import clause_target_assignments, inspect_target_hints
    from rules_engine.targeting import validate_cast_targets, validate_hexproof_shroud_targets, validate_protection_targets

    from rules_engine.targeting import stack_source_card
    copied_card = stack_source_card(state, copied_item)
    if copied_card is None:
        return
    copied_card = copy.copy(copied_card)
    announced = copied_item.payload.get("__announced_targets") or {}
    effects = copied_item.payload.get("effects") or []
    assignments = clause_target_assignments(state, copied_card, controller, announced, effects)
    if assignments is None:
        return
    indices = list(remaining_indices) if remaining_indices is not None else [
        index for index, selected in enumerate(assignments) if selected
    ]
    if any(index >= len(assignments) or len(assignments[index]) != 1 for index in indices):
        return
    if len({next(iter(assignments[index])) for index in indices}) != len(indices):
        return
    surfaces = {
        "target_player": ("player_targets",),
        "target_card_id": ("creature_targets", "planeswalker_targets", "permanent_targets", "land_targets",
                           "artifact_targets", "enchantment_targets", "graveyard_creature_targets", "graveyard_permanent_targets"),
        "target_stack_id": ("stack_targets",),
    }
    for offset, index in enumerate(indices):
        selected = assignments[index]
        if len(selected) != 1:
            continue
        target_key, old_value = next(iter(selected.items()))
        clause_card = copy.copy(copied_card)
        clause_card.oracle_text = effects[index]["clause_text"]
        hints = inspect_target_hints(state, clause_card, controller, announced)
        options = ["keep"]
        labels = {"keep": f"Keep {old_value}"}
        for surface in surfaces[target_key]:
            for candidate in hints.get(surface, []):
                value = candidate["id"]
                if str(value) == str(old_value) or value == copied_item.id:
                    continue
                proposed = {target_key: value}
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
                "clause_effect_index": index, "clause_target_key": target_key,
                "remaining_clause_indices": indices[offset + 1:],
                "target_slot_number": slot_number + offset,
                "label": f"Choose target {slot_number + offset} for {copied_item.label}",
            }
            return


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
    from rules_engine.targeting import stack_source_card
    copied_card = stack_source_card(state, copied_item)
    if copied_card is None:
        return
    copied_card = copy.copy(copied_card)
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
    from rules_engine.targeting import stack_source_card
    copied_card = stack_source_card(state, copied_item)
    if copied_card is None:
        return
    copied_card = copy.copy(copied_card)
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


def exile_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get('target_card_id')
    card = state.cards.get(target)
    if card is None or card.zone != Zone.GRAVEYARD or is_departed_token(card):
        return
    owner = state.players[card.owner]
    if target not in owner.graveyard:
        return
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, [target])
    owner.graveyard.remove(target)
    owner.exile.append(target)
    card.move_to_zone(Zone.EXILE)
    state.log.append(f'{card.name} is exiled from the graveyard.')
    emit_graveyard_departures(state, departures)


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
    if 'effect_timestamp' in payload and object_incarnation(card) != payload['effect_timestamp']:
        return
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


def shuffle_graveyard_into_library(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import StackItem
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    from rules_engine.shuffle_actions import shuffle_library

    owner = payload.get('graveyard_owner')
    frame = payload.get('__resolving_item')
    if type(owner) is not int or owner not in state.players or not isinstance(frame, dict):
        raise ValueError('Graveyard shuffle requires an owner and actual resolving item')
    item = StackItem(**frame)
    if (type(controller) is not int or type(item.controller) is not int
            or item.source_card_id not in state.cards or item.controller != controller
            or controller not in state.players):
        raise ValueError('Graveyard shuffle requires its retained resolving source')
    player = state.players[owner]
    ids = list(player.graveyard)
    if (len(set(ids)) != len(ids) or any(cid not in state.cards
            or state.cards[cid].zone != Zone.GRAVEYARD or state.cards[cid].owner != owner
            or any(cid in getattr(other, zone.value, [])
                   for other in state.players.values() for zone in Zone
                   if other.id != owner or zone != Zone.GRAVEYARD) for cid in ids)):
        raise ValueError('Graveyard shuffle requires unique current graveyard membership')
    captured = capture_graveyard_departures(state, ids)
    for cid in ids:
        player.graveyard.remove(cid)
        player.library.append(cid)
        state.cards[cid].move_to_zone(Zone.LIBRARY)
    emit_graveyard_departures(state, captured)
    shuffle_library(state, owner, resolving_item=frame)


def mill_cards(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.replacement import select_graveyard_entry_plan
    player = state.players[int(payload.get('target_player', controller))]
    count = min(len(player.library), max(0, int(payload.get('amount', 0))))
    # Retain the simultaneous top set even if a replacement shuffles the library.
    ids = list(reversed(player.library[-count:])) if count else []
    plans = {cid: select_graveyard_entry_plan(state, cid) for cid in ids}
    causes = prepare_graveyard_entry_causes(state, plans.values())
    events = []
    entry_receipts = []
    for cid in ids:
        execute_graveyard_entry(state, plans[cid], prevalidated=True,
                               _prepared_cause=causes[cid], _entry_receipts=entry_receipts)
        events.append({'card_id': cid, 'controller': player.id})
        state.log.append(f'{player.name} mills {state.cards[cid].name}.')
    if entry_receipts:
        emit_event_batch(state, 'enters_graveyard', entry_receipts)
    emit_event_batch(state, 'mill', events)


def choose_graveyard_return(state: MatchState, controller: int, payload: dict) -> None:
    eligible = [cid for cid in state.players[controller].graveyard
                if not is_departed_token(state.cards[cid])
                and set(payload['allowed_types']).intersection(effective_types(state, state.cards[cid]))]
    if not eligible:
        return
    if controller in state.mechanic_choice_players and payload.get('selected_card_ids') is None:
        state.pending_mechanic_choice = {
            'kind': 'graveyard_return', 'player_id': controller, 'count': 1,
            'options': eligible, 'effect_payload': payload,
            'effect_key': 'choose_graveyard_return', 'label': 'Choose a graveyard card to return to hand',
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    selected = payload.get('selected_card_ids')
    if selected is not None and (len(selected) != 1 or selected[0] not in eligible):
        return
    cid = selected[0] if selected is not None else eligible[-1]
    return_from_graveyard(state, controller, {'target_card_id': cid})


def destroy_with_controller_search(state: MatchState, controller: int, payload: dict) -> None:
    source = state.cards.get(payload.get('target_card_id'))
    if source is None or source.zone != Zone.BATTLEFIELD:
        return
    target_controller = source.controller
    destroy_permanent(state, controller, payload)
    search_library(state, target_controller, payload['search_payload'])


def return_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    player = state.players[int(payload.get('target_player', controller))]
    requested = payload.get("target_card_id")
    if requested is not None:
        card_id = requested if requested in player.graveyard and not is_departed_token(state.cards[requested]) else None
    else:
        card_id = next((cid for cid in reversed(player.graveyard) if not is_departed_token(state.cards[cid])), None)
    if card_id is None:
        return
    card = state.cards[card_id]
    reference = payload.get('__graveyard_reference')
    if reference and (card.zone != Zone.GRAVEYARD
                      or object_incarnation(card) != reference['incarnation']
                      or card.zone_change_sequence != reference['zone_sequence']):
        return
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, [card_id])
    player.graveyard.remove(card_id)
    player.hand.append(card_id)
    card.move_to_zone(Zone.HAND)
    card.controller = card.owner
    state.log.append(f"{state.cards[card_id].name} returns from graveyard to hand.")
    emit_graveyard_departures(state, departures)


def put_land_from_hand(state: MatchState, controller: int, payload: dict) -> None:
    """Resolve an effect that puts a land from hand onto the battlefield.

    This is distinct from a normal land play: it does not consume the
    controller's land-play allowance and the effect may enter the land tapped.
    """
    player = state.players[controller]
    eligible = [cid for cid in player.hand if cid in state.cards and "Land" in effective_types(state, state.cards[cid]) and not is_departed_token(state.cards[cid])]
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
    land.summoning_sick = True
    land.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, land_id)
    emit_event(state, "enters_battlefield", {"card_id": land_id, "controller": controller})
    state.log.append(
        f"{player.name} puts {land.name} from hand onto the battlefield"
        f"{' tapped' if land.tapped else ''}."
    )


def cast_from_graveyard(state: MatchState, controller: int, payload: dict) -> None:
    """Cast with a mana-cost waiver, preserving taxes, targets and cast events.

    The enclosing resolution publishes staged triggers. Recognized permissions
    can replace the spell's eventual graveyard departure with exile.
    """
    target = payload.get("target_card_id")
    player = state.players[controller]
    if not target or target not in player.graveyard or target not in state.cards or is_departed_token(state.cards[target]):
        return
    card = state.cards[target]
    if not ({"Instant", "Sorcery"} & set(effective_types(state, card))):
        return
    if controller in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            'kind': 'effect_cast', 'player_id': controller, 'options': ['decline'], 'count': 1,
            'label': f'Cast {card.name} using its card controls, or decline',
            'effect_payload': dict(payload),
        }
        state.priority_player = controller
        state.passed_priority = set()
        return
    from rules_engine.effect_casts import materialize_cast, admit_cast
    try:
        action = materialize_cast(state, controller, target, payload.get('cast_targets'))
        admit_cast(state, controller, action, payload)
    except (ValueError, KeyError):
        state.log.append(f'{player.name} chooses not to cast {card.name}: no payable supported announcement.')


def return_creature_from_graveyard_to_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    reference = payload.get('__graveyard_reference')
    if reference and (object_incarnation(card) != reference['incarnation']
                      or card.zone_change_sequence != reference['zone_change_sequence']):
        return
    source_graveyard = None
    for player in state.players.values():
        if target in player.graveyard:
            source_graveyard = player
            break
    if source_graveyard is None or is_departed_token(card) or battlefield_entry_prohibited(state, target):
        return
    # Lock the graveyard characteristics before any resumable entry choice.
    if payload.get('lose_life_equal_to_mana_value'):
        payload.setdefault('__return_life_loss', mana_value(card.mana_cost or ''))
    if prepare_counter_entries(state, controller, [card], 'return_creature_from_graveyard_to_battlefield', payload):
        return
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, [target])
    source_graveyard.graveyard.remove(target)
    battlefield_owner = state.players[controller]
    battlefield_owner.battlefield.append(target)
    card.move_to_zone(Zone.BATTLEFIELD)
    card.controller = controller
    card.tapped = False
    card.summoning_sick = True
    card.entered_turn = state.turn
    state.log.append(f"{card.name} returns from graveyard to the battlefield under {state.players[controller].name}'s control.")
    assign_static_order_on_battlefield_entry(state, target)
    commit_entry_counters(state, card, payload)
    emit_graveyard_departures(state, departures)
    emit_event(state, 'enters_battlefield', {'card_id': target, 'controller': controller})
    if payload.get('lose_life_equal_to_mana_value'):
        lose_life(state, controller, {'target_player': controller, 'amount': payload['__return_life_loss']})


def return_permanent_from_graveyard_to_battlefield(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    target = payload.get("target_card_id")
    if not target or target not in state.cards:
        return
    card = state.cards[target]
    source_graveyard = None
    for player in state.players.values():
        if target in player.graveyard:
            source_graveyard = player
            break
    if source_graveyard is None or is_departed_token(card) or battlefield_entry_prohibited(state, target):
        return
    if pause_for_land_entries(state, controller, [target], "return_permanent_from_graveyard_to_battlefield", payload):
        return
    if prepare_counter_entries(state, controller, [card], 'return_permanent_from_graveyard_to_battlefield', payload):
        return
    from rules_engine.resource_events import capture_graveyard_departures, emit_graveyard_departures
    departures = capture_graveyard_departures(state, [target])
    apply_entry_choice(state, controller, card, choice=(payload.get("__entry_choices") or {}).get(target, "tapped"))
    source_graveyard.graveyard.remove(target)
    battlefield_owner = state.players[controller]
    battlefield_owner.battlefield.append(target)
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, target)
    commit_entry_counters(state, card, payload)
    card.summoning_sick = True
    state.log.append(f"{card.name} returns from graveyard to the battlefield under {state.players[controller].name}'s control.")
    emit_graveyard_departures(state, departures)
    emit_event(state, "enters_battlefield", {"card_id": target, "controller": controller})


def search_library(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.oracle_effects import search_card_matches
    from rules_engine.entry_counters import prepare_counter_entries

    subtype = payload.get("contains")
    destination = str(payload.get("destination", "hand") or "hand").strip().lower()
    limit = int(payload.get("count", 0) or 0)
    mv_max = payload.get("mv_max")
    mv_max = int(mv_max) if mv_max is not None else None
    player = state.players[controller]
    if payload.get('optional') and not payload.get('__search_accepted'):
        if controller in state.mechanic_choice_players:
            state.pending_mechanic_choice = {
                'kind': 'optional_search', 'player_id': controller, 'count': 1,
                'options': ['search', 'decline'], 'option_labels': {'search': 'Search library', 'decline': 'Decline search'},
                'effect_payload': payload, 'label': 'You may search your library',
            }
            state.priority_player = controller
            state.passed_priority = set()
            return
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
    entering = [cid for cid in entering if not battlefield_entry_prohibited(state, cid)]
    if pause_for_land_entries(state, controller, entering, "search_library", {**payload, "selected_card_ids": chosen}):
        return
    if entering and prepare_counter_entries(state, controller, [state.cards[cid] for cid in entering],
                                           'search_library', {**payload, 'selected_card_ids': chosen}):
        return
    found: list[str] = []
    entry_events = []
    placed = []
    for index, cid in enumerate(chosen):
        zone = ("battlefield" if index == 0 else "hand") if destination == "split_battlefield_hand" else destination
        if zone == 'battlefield' and battlefield_entry_prohibited(state, cid):
            continue
        choice = (payload.get("__entry_choices") or {}).get(cid, "tapped")
        player.library.remove(cid)
        _place_searched_card(state, controller, cid, zone, tapped=bool(payload.get("tapped")),
                             entry_choice=choice, emit_entry=destination != "battlefield", entry_payload=payload)
        if destination == "battlefield":
            entry_events.append({"card_id": cid, "controller": controller})
        found.append(state.cards[cid].name)
        placed.append(cid)
    if entry_events:
        emit_event_batch(state, "enters_battlefield", entry_events)
    if chosen and payload.get('reveal'):
        from game_state.observations import observe_cards
        observe_cards(state, chosen)
    if found:
        public_names = bool(payload.get("reveal")) or destination in {"battlefield", "graveyard", "exile"}
        if public_names:
            from game_state.observations import observe_cards
            observe_cards(state, placed)
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
    emit_entry: bool = True,
    entry_payload: dict | None = None,
) -> None:
    card = state.cards[card_id]
    player = state.players[controller]
    if destination == "graveyard":
        put_into_graveyard(state, card_id)
        return
    if destination == "battlefield":
        if "Land" in effective_types(state, card):
            apply_entry_choice(state, controller, card, choice=entry_choice, effect_tapped=tapped)
        player.battlefield.append(card_id)
        card.zone = Zone.BATTLEFIELD
        card.controller = controller
        if "Land" not in effective_types(state, card):
            card.tapped = tapped
        card.summoning_sick = True
        card.entered_turn = state.turn
        assign_static_order_on_battlefield_entry(state, card_id)
        if entry_payload is not None:
            from rules_engine.entry_counters import commit_entry_counters
            commit_entry_counters(state, card, entry_payload)
        if emit_entry:
            emit_event(state, "enters_battlefield", {"card_id": card_id, "controller": controller})
        return
    player.hand.append(card_id)
    card.move_to_zone(Zone.HAND)


def create_token(state: MatchState, controller: int, payload: dict) -> None:
    from game_state.state import CardInstance
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    from rules_engine.domain import basic_land_type_count
    from copy import deepcopy

    name = payload.get("name", "Token")
    p = int(payload['power']) if payload.get('power') is not None else None if 'power' in payload else 1
    t = int(payload['toughness']) if payload.get('toughness') is not None else None if 'toughness' in payload else 1
    token_controller = int(payload.get("controller", controller))
    amount = (basic_land_type_count(state, token_controller) if payload.get("per_basic_land_type")
              else max(0, int(payload.get("amount", 1))))
    if not payload.get('__token_creation_modified'):
        from rules_engine.token_replacements import token_creation_amount
        amount = token_creation_amount(state, token_controller, amount)
        payload = {**payload, 'amount': amount, 'per_basic_land_type': False,
                   '__token_creation_modified': True}
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
    candidates = []
    for raw in payload.get('__entry_candidates', []):
        candidates.append(CardInstance(**{**raw, 'zone': Zone(raw['zone'])}))
    for index in range(amount if '__entry_candidates' not in payload else 0):
        cid = state.allocate_object_id()
        token = CardInstance(
            id=cid,
            name=name,
            owner=token_controller,
            controller=token_controller,
            zone=Zone.BATTLEFIELD,
            types=types,
            is_token=True,
            mana_cost=payload.get("mana_cost", ""),
            power=p if "Creature" in types or payload.get('printed_power') is not None else None,
            toughness=t if "Creature" in types or payload.get('printed_toughness') is not None else None,
            printed_power=payload.get('printed_power', str(p) if p is not None else None),
            printed_toughness=payload.get('printed_toughness', str(t) if t is not None else None),
            loyalty=payload.get('loyalty'),
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
        candidates.append(token)
    if prepare_counter_entries(state, token_controller, candidates, 'create_token', payload):
        return
    for index, token in enumerate(candidates):
        cid = token.id
        state.cards[cid] = token
        state.players[token_controller].battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
    for index, token in enumerate(candidates):
        cid = token.id
        if payload.get('tapped'):
            token.tapped = True
        if tapped_and_attacking:
            token.tapped = True
            state.attackers.append(cid)
            state.attack_targets[cid] = attack_targets[index] if attack_targets is not None else attack_target
        commit_entry_counters(state, token, payload)
        entry_events.append({"card_id": cid, "controller": token_controller})
        if sac_next_end:
            token.counters["__sac_next_end_step"] = 1
        if payload.get('temporary_keywords'):
            from rules_engine.keyword_effects import add_keyword_effect
            add_keyword_effect(state, cid, payload['temporary_keywords'], until_end_of_turn=True,
                               source_card_id=payload.get('__source_card_id'))
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
            or target.controller != controller or "Creature" not in effective_types(state, target)
            or "Legendary" in effective_types(state, target) or "legendary" in (target.type_line or "").lower()):
        state.log.append("Copy token ability has no legal target at resolution.")
        return
    keywords = list(target.keywords or [])
    if payload.get("grant_haste") and "haste" not in {value.lower() for value in keywords}:
        keywords.append("haste")
    from rules_engine.type_effects import copiable_types
    create_token(state, controller, {
        "name": target.name, "types": list(dict.fromkeys([*copiable_types(target), "Token"])),
        "mana_cost": target.mana_cost, "type_line": target.type_line,
        "power": target.power, "toughness": target.toughness,
        "printed_power": target.printed_power, "printed_toughness": target.printed_toughness,
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
    top_n = max(0, int(payload.get("top_n", payload.get("mana_spent_to_cast", 0)) or 0))
    top_slice = player.library[-top_n:] if top_n else []
    if not top_slice:
        return
    count = min(len(top_slice), max(0, int(payload.get("hand_count", 0) or 0)))
    if payload.get("selected_card_ids") is None:
        state.pending_mechanic_choice = {
            "kind": "look_top_select_hand", "player_id": controller,
            "options": list(reversed(top_slice)), "count": count,
            "inspected_card_ids": list(reversed(top_slice)),
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
    if payload.get("choose_bottom_order") and len(rest) > 1:
        state.pending_mechanic_choice = {
            "kind": "topdeck_bottom_order", "player_id": controller,
            "options": rest, "bottom_ids": rest, "count": len(rest),
            "label": "Choose bottom order, bottommost first",
        }
        state.priority_player = controller
        state.passed_priority = set()


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
    if payload.get('optional_reveal'):
        from rules_engine.optional_reveal import begin_reveal
        begin_reveal(state, controller, payload)
        return
    target_id = payload.get("target_card_id")
    player = state.players[controller]
    if not target_id or target_id not in state.cards or not player.library:
        return
    top_id = player.library[-1]
    top_card = state.cards[top_id]
    required = {str(value).lower() for value in (payload.get("required_types") or [])}
    state.log.append(f"{player.name} reveals {top_card.name} for {state.cards[target_id].name}.")
    if not required.intersection({str(value).lower() for value in (effective_types(state, top_card) or [])}):
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
    loyalty_counters = int(card.loyalty or 0) if 'Planeswalker' in effective_types(state, card) else int(card.counters.pop('loyalty', 0))
    apply_transform_face(card, index)
    # Transforming is not entering: preserve physical loyalty counters instead
    # of replacing them with the newly displayed face's printed starting value.
    if 'Planeswalker' in effective_types(state, card):
        card.loyalty = loyalty_counters
    else:
        card.loyalty = None
        if loyalty_counters:
            card.counters['loyalty'] = loyalty_counters
    state.log.append(f"{card.name} transforms.")
    if not payload.get("__defer_transform_event"):
        emit_event(state, "transformed", {
            "card_id": target_id, "controller": card.controller,
            "from_face_index": previous_face, "to_face_index": index,
        })


def exile_return_transformed(state: MatchState, controller: int, payload: dict) -> None:
    """Prepare a new back-face permanent while its actual card stays exiled."""
    from rules_engine.entry import pause_for_land_entries, apply_entry_choice
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    from rules_engine.card_faces import apply_transform_face, select_cast_face
    from game_state.state import object_incarnation

    target_id = payload.get("target_card_id")
    card = state.cards.get(target_id) if target_id else None
    if card is None:
        return
    if not payload.get('__return_from_exile'):
        if card.zone != Zone.BATTLEFIELD or target_id not in state.players[card.controller].battlefield:
            return
        exile_permanent(state, controller, {"target_card_id": target_id})
        payload = {**payload, '__return_from_exile': True, '__return_incarnation': object_incarnation(card)}
    owner_exile = state.players[card.owner].exile
    if card.zone != Zone.EXILE or target_id not in owner_exile:
        return
    if (card.layout != "transform" or len(card.card_faces) < 2 or is_departed_token(card)
            or object_incarnation(card) != payload['__return_incarnation']):
        return
    projections = {card.id: select_cast_face(card, 1)}
    if pause_for_land_entries(state, controller, [card.id], 'exile_return_transformed', payload,
                              projections=projections):
        return
    if prepare_counter_entries(state, controller, [card], 'exile_return_transformed', payload,
                               projections=projections):
        return

    owner_exile.remove(target_id)
    apply_transform_face(card, 1)
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    apply_entry_choice(state, controller, card, choice=(payload.get('__entry_choices') or {}).get(card.id, 'tapped'))
    card.summoning_sick = True
    card.entered_turn = state.turn
    state.players[controller].battlefield.append(target_id)
    assign_static_order_on_battlefield_entry(state, target_id)
    commit_entry_counters(state, card, payload)
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
    if "Land" in effective_types(state, card):
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
            and object_incarnation(card) == payload["effect_timestamp"]
            and card.counters.get(payload["counter"], 0) >= int(payload["minimum_counters"])):
        transform_card(state, controller, {"target_card_id": target_id, "face_index": 1})


def add_player_counters(state: MatchState, controller: int, payload: dict) -> None:
    player = payload.get('target_player', controller)
    kind = str(payload.get('counter', '')).strip().lower()
    amount = max(0, int(payload.get('amount', 1)))
    if player not in state.players or not re.fullmatch(r'[a-z]+(?:-[a-z]+)*', kind) or not amount:
        return
    if payload.get('requires_departure') and player not in state.players_with_permanent_departure:
        return
    amount = counter_effect_amount(state, controller, 'add_player_counters',
                                   {**payload, 'target_player': player, 'counter': kind, 'amount': amount})
    if amount is None:
        return
    target = state.players[player]
    amount = put_counters(state, kind, amount, target_player=player)
    if not amount:
        return
    reason = payload.get('__counter_reason')
    if reason in {'infect', 'toxic', 'infect/toxic'}:
        state.log.append(f'{target.name} gets {amount} {kind} counters from {reason}.')
    else:
        state.log.append(f'{target.name} gets {amount} {kind} counter(s).')
    emit_event(state, 'player_counters_added', {'player_id': player, 'controller': controller,
                                              'counter': kind, 'amount': amount})


def add_counters(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    counter = payload.get("counter", "+1/+1")
    amount = int(payload.get("amount", 1))
    if target in state.cards and state.cards[target].zone == Zone.BATTLEFIELD:
        card = state.cards[target]
        if "effect_timestamp" in payload and object_incarnation(card) != payload["effect_timestamp"]:
            return
        amount = counter_effect_amount(state, controller, 'add_counters',
                                       {**payload, 'counter': counter, 'amount': amount})
        if amount is None:
            return
        put_counters(state, counter, amount, target_card_id=target)
        if payload.get("animate_land") and "Land" in effective_types(state, card):
            from rules_engine.type_effects import add_type_effect
            from rules_engine.keyword_effects import add_keyword_effect
            stamp = payload.get('resolution_timestamp') or allocate_effect_timestamp(state)
            source_id = payload.get('__source_card_id')
            add_type_effect(state, card.id, ['Creature', 'Elemental'], timestamp=stamp, source_card_id=source_id)
            set_base_stats(state, controller, {'target_card_id': card.id, 'base_power': 0, 'base_toughness': 0,
                                             'until_end_of_turn': False, 'resolution_timestamp': stamp,
                                             '__source_card_id': source_id})
            if payload.get("animate_untap"):
                from rules_engine.named_counters import untap_permanent
                untap_permanent(state, card.id)
            add_keyword_effect(state, card.id, payload.get('animate_keywords', []),
                               timestamp=stamp, source_card_id=source_id)
            state.log.append(f"{card.name} becomes a 0/0 Elemental creature.")
        # PT delta from counters is computed dynamically by effective_power/toughness


def add_counters_each_creature(state: MatchState, controller: int, payload: dict) -> None:
    from effects.registry import resolve_effect
    recipients = payload.get('recipients', 'controller')
    if recipients not in {'controller', 'opponents'}:
        return
    player_ids = [controller] if recipients == 'controller' else [pid for pid in state.players if pid != controller]
    resolve_effect(state, controller, 'effect_sequence', {'effects': [
        {'effect_key': 'add_counters', 'payload': {**payload, 'target_card_id': cid,
                                                'effect_timestamp': object_incarnation(state.cards[cid])}}
        for pid in player_ids for cid in list(state.players[pid].battlefield)
        if cid in state.cards and 'Creature' in effective_types(state, state.cards[cid])
    ]})


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
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    player = state.players[controller]
    target = next(
        (
            cid
            for cid in player.hand
            if cid in state.cards
            and not is_departed_token(state.cards[cid])
            and "Creature" in effective_types(state, state.cards[cid])
            and "{G}" in (state.cards[cid].mana_cost or "").upper()
        ),
        None,
    )
    if not target:
        return
    if prepare_counter_entries(state, controller, [state.cards[target]], 'put_green_creature_from_hand', payload):
        return
    player.hand.remove(target)
    player.battlefield.append(target)
    card = state.cards[target]
    card.zone = Zone.BATTLEFIELD
    card.controller = controller
    card.summoning_sick = True
    card.entered_turn = state.turn
    assign_static_order_on_battlefield_entry(state, target)
    commit_entry_counters(state, card, payload)
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
            f"{card.name} gets {power:+d}/{toughness:+d} until end of turn."
        )


def temporary_pt_buff_all(state: MatchState, controller: int, payload: dict) -> None:
    power = int(payload.get("power", 0))
    toughness = int(payload.get("toughness", 0))
    keyword = payload.get("keyword")
    if not power and not toughness and not keyword:
        return
    players = [state.players[controller]] if payload.get("controller_only") else state.players.values()
    required_subtypes = set(payload.get("creature_subtypes") or [])
    keyword_timestamp = allocate_effect_timestamp(state) if keyword else None
    for player in players:
        for card_id in list(player.battlefield):
            card = state.cards[card_id]
            if "Creature" not in effective_types(state, card):
                continue
            if required_subtypes:
                from rules_engine.library_permissions import creature_types

                if (not required_subtypes.intersection(creature_types(card))
                        and "changeling" not in {keyword.lower() for keyword in (card.keywords or [])}):
                    continue
            card.counters["__eot_power"] = int(card.counters.get("__eot_power", 0)) + power
            card.counters["__eot_toughness"] = int(card.counters.get("__eot_toughness", 0)) + toughness
            if keyword:
                from rules_engine.keyword_effects import add_keyword_effect
                add_keyword_effect(state,card_id,[keyword],until_end_of_turn=True,timestamp=keyword_timestamp,
                                   source_card_id=payload.get('__source_card_id'))
    scope = (f"{payload['creature_subtype_label']} you control" if payload.get("creature_subtype_label")
             else "Creatures you control" if payload.get("controller_only") else "All creatures")
    state.log.append(f"{scope} get {power:+d}/{toughness:+d} until end of turn.")


def sacrifice(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    if target in state.cards and target in state.players[controller].battlefield:
        from rules_engine.events import flush_staged_triggers
        plan = select_graveyard_entry_plan(state, target)
        cause = prepare_graveyard_entry_causes(state, [plan])[target]
        started_staging = not state.trigger_staging
        if started_staging:
            state.trigger_staging = True
            state.trigger_staging_event = "sacrifice"
        card = state.cards[target]
        emit_event(state, "leaves_battlefield", {"card_id": target, "controller": controller})
        destination = execute_graveyard_entry(state, plan, prevalidated=True, _prepared_cause=cause)
        if destination == Zone.EXILE:
            state.log.append(f"{card.name} is exiled instead of dying.")
        elif destination == Zone.GRAVEYARD:
            emit_event(state, "permanent_dies", {"card_id": target, "controller": controller})
            if was_creature_on_battlefield(card):
                emit_event(state, "creature_dies", {"card_id": target, "controller": controller})
        emit_event(state, "sacrifice", {"card_id": target, "controller": controller})
        card.reset_zone_counters(destination)
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
        if "Creature" in effective_types(state, state.cards[cid])
    ]
    recipients.extend({"target_player": pid, "amount": amount} for pid in state.players)
    deal_damage_batch(state, controller, {"recipients": recipients, "__source_card_id": payload.get("__source_card_id"),
                                          "__source_lki": payload.get("__source_lki")})


def deal_damage_batch(state: MatchState, controller: int, payload: dict) -> None:
    source_id = payload.get("__source_card_id")
    source_lki = payload.get("__source_lki")
    lifelink_total = max(0, int(payload.get("lifelink_total", 0)))
    recipients = []
    grouped = {}
    # One source deals a simultaneous total to each recipient before prevention.
    # Only packets with identical metadata share replacement/prevention semantics.
    for raw in payload.get('recipients') or []:
        recipient = dict(raw)
        target_keys = [key for key in ('target_player', 'target_card_id') if recipient.get(key) is not None]
        if len(target_keys) == 1:
            key = (target_keys[0], recipient[target_keys[0]])
            signature = {name: value for name, value in recipient.items() if name != 'amount'}
            variants = grouped.setdefault(key, [])
            existing = next((packet for metadata, packet in variants if metadata == signature), None)
            if existing is not None:
                existing['amount'] += int(recipient['amount'])
                continue
            recipient['amount'] = int(recipient['amount'])
            variants.append((signature, recipient))
        recipients.append(recipient)
    for index, recipient in enumerate(recipients):
        recipient = {**recipient, "__source_card_id": source_id, "__source_lki": source_lki,
                     "__defer_lethal": True, "__batch_damage": True}
        target_id = recipient.get("target_card_id")
        affected = state.cards[target_id].controller if target_id else recipient.get("target_player")
        event = "damage_to_permanent" if target_id else "damage_to_player"
        humans = set(getattr(state, "replacement_choice_players", set()) or set())
        if state.replacement_choice_required and (not humans or affected in humans):
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
        from rules_engine.damage_results import source_has_keyword
        if source_has_keyword(state, source_id, "lifelink", source_lki):
            lifelink_total += dealt
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
    _gain_lifelink_from_damage(state, source_id, lifelink_total, source_lki)


def emit_combat_damage_events(state: MatchState, controller: int, payload: dict) -> None:
    emit_event_batch(state, 'combat_damage_dealt', payload.get('events') or [])


def tap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    from rules_engine.resource_events import tap_permanents
    tap_permanents(state, [target])


def tap_all_opponent_creatures(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.resource_events import tap_permanents
    tap_permanents(state, [cid for pid, player in state.players.items() if pid != controller
                          for cid in player.battlefield if 'Creature' in effective_types(state, state.cards[cid])])


def untap_card(state: MatchState, controller: int, payload: dict) -> None:
    target = payload.get("target_card_id")
    from rules_engine.named_counters import untap_permanent
    untap_permanent(state, target)


def equip_attachment(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.attachments import attach_if_legal, is_equipment
    source = state.cards.get(payload.get("equipment_id"))
    target = state.cards.get(payload.get("target_card_id"))
    if (source is None or target is None or source.zone != Zone.BATTLEFIELD
            or target.zone != Zone.BATTLEFIELD or target.controller != controller
            or "Creature" not in effective_types(state, target) or "Creature" in effective_types(state, source)
            or not is_equipment(source)
            or object_incarnation(source) != payload.get("source_timestamp")
            or object_incarnation(target) != payload.get("target_timestamp")):
        return
    if attach_if_legal(state, source.id, target.id):
        state.log.append(f"{state.players[controller].name} equips {source.name} to {target.name}.")


def crew_vehicle(state: MatchState, controller: int, payload: dict) -> None:
    vehicle_id = payload.get("card_id")
    vehicle = state.cards.get(vehicle_id) if vehicle_id else None
    if (vehicle is None or vehicle.zone != Zone.BATTLEFIELD
            or object_incarnation(vehicle) != payload.get("effect_timestamp", object_incarnation(vehicle))):
        return
    from rules_engine.type_effects import add_type_effect
    add_type_effect(state, vehicle.id, ['Artifact', 'Creature'], until_end_of_turn=True,
                    source_card_id=vehicle.id)
    state.log.append(f"{state.players[controller].name} crews {vehicle.name} with {len(payload.get('crew_card_ids') or [])} creature(s).")


def continuous_buff(state: MatchState, controller: int, payload: dict) -> None:
    # No-op — continuous PT bonuses are computed dynamically by
    # effective_power() / effective_toughness() which scan all battlefield
    # permanents for anthem-like oracle text via _continuous_pt_delta().
    # Permanently mutating base stats here caused buffs to persist after
    # the source left the battlefield (Bug #7).
    pass


def set_base_stats(state: MatchState, controller: int, payload: dict) -> None:
    card = state.cards.get(payload.get('target_card_id'))
    if (card is None or card.zone != Zone.BATTLEFIELD
            or payload.get('effect_timestamp', object_incarnation(card)) != object_incarnation(card)):
        return
    source_id = payload.get('__source_card_id')
    source = state.cards.get(source_id)
    card.base_stat_effects.append({
        'power': payload['base_power'], 'toughness': payload['base_toughness'],
        'timestamp': payload.get('resolution_timestamp') or allocate_effect_timestamp(state),
        'incarnation': object_incarnation(card), 'until_end_of_turn': bool(payload.get('until_end_of_turn', True)),
        'timestamp_origin': 'resolution', 'source_card_id': source_id,
        'source_name': source.name if source else None,
    })


def temporary_ability_loss(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.keyword_effects import add_keyword_effect
    player_id = payload.get('target_player')
    card_ids = list(state.players[player_id].battlefield) if player_id in state.players else [payload.get('target_card_id')]
    stamp = allocate_effect_timestamp(state)
    source_id = payload.get('__source_card_id')
    source = state.cards.get(source_id)
    for card_id in card_ids:
        card = state.cards.get(card_id)
        if card is None or card.zone != Zone.BATTLEFIELD or (player_id in state.players and 'Creature' not in effective_types(state, card)):
            continue
        add_keyword_effect(state, card_id, ['all abilities'], operation='remove', until_end_of_turn=True,
                           timestamp=stamp, source_card_id=source_id)
        if 'base_power' in payload and 'base_toughness' in payload:
            set_base_stats(state, controller, {**payload, 'target_card_id': card_id, 'resolution_timestamp': stamp})


def grant_keyword(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.keyword_effects import add_keyword_effect
    keywords = payload.get('keywords') or ([payload['keyword']] if payload.get('keyword') else [])
    if payload.get('recipient_kind') in {'creatures', 'permanents'}:
        from game_state.state import allocate_effect_timestamp
        from rules_engine.type_effects import effective_types
        # Resolution locks in recipients; later entrants do not inherit this grant.
        stamp = allocate_effect_timestamp(state)
        for player_id, player in state.players.items():
            scope = payload.get('recipients')
            if scope == 'controller' and player_id != controller or scope == 'opponents' and player_id == controller:
                continue
            for card_id in list(player.battlefield):
                card = state.cards[card_id]
                if payload['recipient_kind'] == 'creatures' and 'Creature' not in effective_types(state, card):
                    continue
                add_keyword_effect(state, card_id, keywords,
                                   operation=payload.get('operation', 'grant'),
                                   until_end_of_turn=bool(payload.get('until_end_of_turn')),
                                   timestamp=stamp, source_card_id=payload.get('__source_card_id'))
        return
    add_keyword_effect(state,payload.get('target_card_id'),keywords,
                       operation=payload.get('operation','grant'),until_end_of_turn=bool(payload.get('until_end_of_turn')),
                       source_card_id=payload.get('__source_card_id'))


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
    target_player = controller if payload.get('self_discard') else int(payload.get("target_player", 1 if controller == 2 else 2))
    amount = int(payload.get("amount", 1))
    player = state.players[target_player]
    from rules_engine.zone_actions import discard_selected, is_departed_token
    available = [cid for cid in player.hand if not is_departed_token(state.cards[cid])]
    if payload.get('all_hand') or (payload.get('up_to') and 'amount' not in payload):
        amount = len(available)
    count = min(max(0, amount), len(available))
    if count and not payload.get("random") and target_player in state.mechanic_choice_players:
        state.pending_mechanic_choice = {
            "kind": "discard", "player_id": target_player, "options": available,
            "count": count, "label": "Choose cards to discard",
        }
        if payload.get('up_to'):
            state.pending_mechanic_choice['min_count'] = 0
            state.pending_mechanic_choice['label'] = 'Choose any number of cards to discard'
        if payload.get('followup_effect'):
            state.pending_mechanic_choice['followup_effect'] = payload['followup_effect']
            state.pending_mechanic_choice['effect_controller'] = controller
        state.priority_player = target_player
        state.passed_priority = set()
        return
    selected = state.rng.sample(available, count) if payload.get("random") else [] if payload.get('up_to') else available[:count]
    discard_selected(state, target_player, selected)
    discarded = len(selected)
    state.log.append(f"{player.name} discards {discarded}.")
    resolve_discard_followup(state, controller, payload.get('followup_effect'), discarded)


def resolve_discard_followup(state, controller, followup, discarded):
    if not followup:
        return
    from effects.registry import resolve_effect
    data = dict(followup.get('payload') or {})
    if followup.get('count_field'):
        data[followup['count_field']] = discarded
    if followup.get('count_history') == 'discards_this_turn':
        data['amount'] = state.discards_this_turn.get(controller, 0)
    if followup['effect_key'] == 'search_library' and discarded == 0:
        # Search's legacy zero limit means unbounded; a zero-card linked search
        # must still shuffle, but must not offer or find any cards.
        data['selected_card_ids'] = []
    resolve_effect(state, controller, followup['effect_key'], data)


def each_player_discard(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.zone_actions import discard_simultaneous, is_departed_token

    amount = max(0, int(payload.get("amount", 1)))
    selected = {str(pid): list(ids) for pid, ids in payload.get("selected_cards", {}).items()}
    for pid in (state.active_player, 1 if state.active_player == 2 else 2):
        key = str(pid)
        if key in selected:
            continue
        options = [cid for cid in state.players[pid].hand if not is_departed_token(state.cards[cid])]
        count = len(options) if payload.get('all_hand') else min(amount, len(options))
        if count and pid in state.mechanic_choice_players and not payload.get("random") and not payload.get('all_hand'):
            state.pending_mechanic_choice = {
                "kind": "each_player_discard", "player_id": pid, "options": options,
                "count": count, "effect_payload": {**payload, "amount": amount, "selected_cards": selected},
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
    if payload.get('draw_followup'):
        from effects.registry import resolve_effect
        from rules_engine.linked_discard import wheel_draw_counts
        counts = wheel_draw_counts(payload['draw_followup'], {int(pid): len(ids) for pid, ids in selected.items()})
        resolve_effect(state, controller, 'effect_sequence', {
            **{key: payload[key] for key in ['__source_card_id', '__source_lki', 'snow_mana_spent'] if key in payload},
            'effects': [{'effect_key': 'draw_cards', 'payload': {'target_player': pid, 'amount': counts[pid]}}
                        for pid in (state.active_player, 3-state.active_player)],
        })


def choose_revealed_hand_card(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.card_types import is_land_card
    from rules_engine.zone_actions import discard_selected, is_departed_token

    target = int(payload["target_player"])
    excluded = set(payload.get("excluded_types") or [])
    allowed = set(payload.get("allowed_types") or [])
    destination = payload.get("destination", "discard")
    revealed = [cid for cid in state.players[target].hand if not is_departed_token(state.cards[cid])]
    from game_state.observations import observe_cards
    observe_cards(state, revealed)
    options = [cid for cid in revealed
               if ("Land" not in excluded or not is_land_card(state.cards[cid]))
               and ("Creature" not in excluded or "Creature" not in effective_types(state, state.cards[cid]))
               and (not allowed or allowed.intersection(effective_types(state, state.cards[cid])))
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
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
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
        if "Creature" not in effective_types(state, card) or battlefield_entry_prohibited(state, cid):
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

    if chosen and prepare_counter_entries(state, controller, [state.cards[cid] for cid in chosen],
                                         'topdeck_put_creatures_battlefield', {**payload, 'selected_card_ids': chosen}):
        return

    # Remove inspected cards from library in top-to-bottom order.
    inspected_set = set(top_slice)
    remaining_library = [cid for cid in player.library if cid not in inspected_set]
    player.library = remaining_library

    # Put chosen creatures onto battlefield.
    entry_events = []
    for cid in chosen:
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.summoning_sick = True
        card.entered_turn = state.turn
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        commit_entry_counters(state, card, payload)
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
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
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
        if set(effective_types(state, state.cards[cid])).intersection(permanent_types)
        and not battlefield_entry_prohibited(state, cid)
        and (not payload.get("allowed_type") or payload["allowed_type"] in effective_types(state, state.cards[cid]))
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
    if chosen and prepare_counter_entries(state, controller, [state.cards[cid] for cid in chosen],
                                         'topdeck_put_permanents_battlefield', {**payload, 'selected_card_ids': chosen}):
        return
    chosen_set = set(chosen)
    player.library = [cid for cid in player.library if cid not in set(top_slice)]
    entry_events = []
    for cid in chosen:
        card = state.cards[cid]
        card.zone = Zone.BATTLEFIELD
        card.controller = controller
        if "Land" in effective_types(state, card):
            apply_entry_choice(state, controller, card, choice=(payload.get("__entry_choices") or {}).get(cid, "tapped"), effect_tapped=bool(payload.get("tapped")))
        else:
            card.tapped = False
        card.summoning_sick = True
        card.entered_turn = state.turn
        player.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        commit_entry_counters(state, card, payload)
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
    if not top_slice:
        return
    eligible = []
    for cid in top_slice:
        card = state.cards[cid]
        if "Creature" not in effective_types(state, card):
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
    if (controller in state.mechanic_choice_players
            or (state.replacement_choice_required and controller in state.replacement_choice_players)):
        options = list(eligible)
        if payload.get("optional") or not eligible:
            options.append("__none__")
        state.pending_mechanic_choice = {
            "kind": "topdeck_reveal_creature", "player_id": controller,
            "options": options, "count": 1, "top_ids": top_slice,
            "inspected_card_ids": list(reversed(top_slice)),
            "bottom_random": bool(payload.get("bottom_random")),
            "bottom_any_order": bool(payload.get("bottom_any_order")),
            "option_labels": {"__none__": "Reveal none" if eligible else "Acknowledge inspected cards"},
            "label": "Reveal a qualifying creature" if eligible else "No qualifying creature; inspect then continue",
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
    finish_topdeck_reveal_creature(state, controller, top_slice, chosen,
                                  bool(payload.get("bottom_random")), bool(payload.get("bottom_any_order")))


def finish_topdeck_reveal_creature(state: MatchState, controller: int, top_ids: list[str], chosen: str | None,
                                  bottom_random: bool, bottom_any_order: bool = False) -> bool:
    player = state.players[controller]
    if not top_ids or player.library[-len(top_ids):] != top_ids or (chosen is not None and chosen not in top_ids):
        return False
    del player.library[-len(top_ids):]
    remaining = [cid for cid in top_ids if cid != chosen]
    if chosen is not None:
        state.cards[chosen].move_to_zone(Zone.HAND)
        player.hand.append(chosen)
        from game_state.observations import observe_cards
        observe_cards(state, [chosen])
    if bottom_random:
        state.rng.shuffle(remaining)
    player.library[:0] = remaining
    if bottom_any_order and not bottom_random and len(remaining) > 1:
        state.pending_mechanic_choice = {
            "kind": "topdeck_bottom_order", "player_id": controller,
            "options": remaining, "bottom_ids": remaining, "count": len(remaining),
            "inspected_card_ids": remaining,
            "label": "Choose bottom order, bottommost first",
        }
        state.priority_player = controller
        state.passed_priority = set()
    if chosen is not None:
        state.log.append(f"{player.name} reveals and puts {state.cards[chosen].name} into hand.")
    else:
        state.log.append(f"{player.name} looks at the top {len(top_ids)} cards and reveals none.")
    return True
