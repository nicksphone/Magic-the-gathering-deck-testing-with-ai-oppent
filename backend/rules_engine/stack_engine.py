from __future__ import annotations

import uuid

from effects.registry import resolve_effect
from game_state.state import MatchState, StackItem, Zone, assign_static_order_on_battlefield_entry
from rules_engine.attachments import attach_if_legal, is_aura
from rules_engine.events import emit_event
from rules_engine.library_permissions import choose_type_for_realmwalker
from rules_engine.replacement import replacement_options


def add_to_stack(state: MatchState, source_card_id: str, controller: int, label: str, effect_key: str, payload: dict, targets: list[str] | None = None) -> StackItem:
    item = StackItem(
        id=str(uuid.uuid4()),
        source_card_id=source_card_id,
        controller=controller,
        label=label,
        effect_key=effect_key,
        payload=payload,
        targets=targets or [],
    )
    state.stack.append(item)
    state.log.append(f"{state.players[controller].name} casts/activates {label}.")
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
    # MTG priority rule: after casting/activating, the same player receives priority first.
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
        return ("die_zone", int(target.controller) if target else None, target_id)
    return None


def resolve_top_of_stack(state: MatchState) -> bool:
    if not state.stack:
        return False
    item = state.stack[-1]
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
        options = [option for option in options if str(option.get("source_id")) not in used]
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
    is_trigger = bool(payload.get("__trigger_event"))
    if bool(payload.get("__may")) and not bool(payload.get("__may_choose", True)):
        state.log.append(f"{state.players[item.controller].name} declines optional effect: {item.label}.")
        return True
    payload["__source_card_id"] = item.source_card_id
    resolve_effect(state, item.controller, item.effect_key, payload)
    card = state.cards.get(item.source_card_id)
    if card and card.zone == Zone.STACK and not is_trigger:
        owner = state.players[getattr(card, "owner", card.controller)]
        if "Instant" in card.types or "Sorcery" in card.types:
            owner.graveyard.append(card.id)
            card.zone = Zone.GRAVEYARD
        else:
            owner.battlefield.append(card.id)
            card.zone = Zone.BATTLEFIELD
            card.summoning_sick = "Creature" in card.types
            card.entered_turn = state.turn
            assign_static_order_on_battlefield_entry(state, card.id)
            if "as this creature enters, choose a creature type" in (card.oracle_text or "").lower():
                selected = str(payload.get("chosen_creature_type") or "").strip().lower()
                card.chosen_creature_type = selected or choose_type_for_realmwalker(state, card.controller)
                state.log.append(f"{card.name} chooses creature type {card.chosen_creature_type}.")
            if "enters with x +1/+1 counters" in (card.oracle_text or "").lower():
                x_value = max(0, int(payload.get("x_value", 0) or 0))
                if x_value:
                    card.counters["+1/+1"] = int(card.counters.get("+1/+1", 0)) + x_value
            if is_aura(card):
                target_id = payload.get("target_card_id")
                if not attach_if_legal(state, card.id, target_id):
                    owner.battlefield.remove(card.id)
                    owner.graveyard.append(card.id)
                    card.zone = Zone.GRAVEYARD
                    state.log.append(f"{card.name} has no legal attachment target and is put into graveyard.")
                    state.log.append(f"{item.label} resolves.")
                    return True
            emit_event(state, "enters_battlefield", {"card_id": card.id, "controller": card.controller})
    state.log.append(f"{item.label} resolves.")
    return True
