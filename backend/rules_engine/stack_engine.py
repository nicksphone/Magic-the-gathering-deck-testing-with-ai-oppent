from __future__ import annotations

import uuid

from effects.registry import resolve_effect
from game_state.state import MatchState, StackItem, Zone
from rules_engine.attachments import attach_if_legal, is_aura
from rules_engine.events import emit_event


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
    # MTG priority rule: after casting/activating, the same player receives priority first.
    state.priority_player = controller
    state.passed_priority = set()
    return item


def resolve_top_of_stack(state: MatchState) -> None:
    if not state.stack:
        return
    item = state.stack.pop()
    payload = dict(item.payload or {})
    if bool(payload.get("__may")) and not bool(payload.get("__may_choose", True)):
        state.log.append(f"{state.players[item.controller].name} declines optional effect: {item.label}.")
        return
    payload["__source_card_id"] = item.source_card_id
    resolve_effect(state, item.controller, item.effect_key, payload)
    card = state.cards.get(item.source_card_id)
    if card and card.zone == Zone.STACK:
        owner = state.players[card.controller]
        if "Instant" in card.types or "Sorcery" in card.types:
            owner.graveyard.append(card.id)
            card.zone = Zone.GRAVEYARD
        else:
            owner.battlefield.append(card.id)
            card.zone = Zone.BATTLEFIELD
            card.summoning_sick = "Creature" in card.types
            card.entered_turn = state.turn
            if is_aura(card):
                target_id = payload.get("target_card_id")
                if not attach_if_legal(state, card.id, target_id):
                    owner.battlefield.remove(card.id)
                    owner.graveyard.append(card.id)
                    card.zone = Zone.GRAVEYARD
                    state.log.append(f"{card.name} has no legal attachment target and is put into graveyard.")
                    state.log.append(f"{item.label} resolves.")
                    return
            emit_event(state, "enters_battlefield", {"card_id": card.id, "controller": card.controller})
    state.log.append(f"{item.label} resolves.")
