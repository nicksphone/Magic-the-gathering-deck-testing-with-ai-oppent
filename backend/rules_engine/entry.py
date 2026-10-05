from __future__ import annotations
from rules_engine.type_effects import effective_types

import re

from rules_engine.land_rules import apply_land_entry
from rules_engine.replacement import can_pay_life, pay_life


def has_two_life_land_entry(card, state=None, controller=None) -> bool:
    if "Land" not in (card.types or []):
        return False
    from rules_engine.land_types import printed_land_abilities_lost
    if printed_land_abilities_lost(state, card, entering=True, controller=controller):
        return False
    subject = rf"(?:this land|{re.escape(card.name)})"
    return bool(re.search(
        rf"as {subject} enters(?: the battlefield)?, you may pay 2 life\.\s*if you don't, it enters tapped\.",
        card.oracle_text or "", re.IGNORECASE,
    ))


def land_entry_options(state, controller: int, card) -> list[str]:
    if not has_two_life_land_entry(card, state, controller):
        return []
    options = ["tapped"]
    if can_pay_life(state, controller, 2):
        options.append("pay_two_life")
    return options


def pause_for_land_entries(state, controller: int, card_ids: list[str], effect_key: str, payload: dict, *, controllers=None, projections=None) -> bool:
    choices = payload.get("__entry_choices") or {}
    for card_id in card_ids:
        card = (projections or {}).get(card_id, state.cards[card_id])
        from rules_engine.card_faces import day_night_entry_face
        card = day_night_entry_face(state, card)
        recipient = (controllers or {}).get(card_id, controller)
        if not has_two_life_land_entry(card, state, recipient) or card_id in choices:
            continue
        options = land_entry_options(state, recipient, card)
        reserved_life = 2 * sum(value == "pay_two_life" and (controllers or {}).get(cid, controller) == recipient
                                for cid, value in choices.items())
        if state.players[recipient].life - reserved_life < 2:
            options = [option for option in options if option != "pay_two_life"]
        forced_tapped = bool(payload.get("tapped"))
        state.pending_mechanic_choice = {
            "kind": "land_entry", "player_id": recipient, "options": options,
            "option_labels": {"tapped": "Enter tapped", "pay_two_life": "Pay 2 life (effect still makes it tapped)" if forced_tapped else "Pay 2 life to enter untapped"},
            "entry_card_id": card_id, "effect_key": effect_key, "effect_payload": dict(payload),
            "label": f"Choose how {card.name} enters",
        }
        state.priority_player = recipient
        state.passed_priority = set()
        return True
    return False


def apply_entry_choice(state, controller: int, card, *, choice: str = "tapped", effect_tapped: bool = False) -> None:
    from rules_engine.card_faces import apply_day_night_entry
    apply_day_night_entry(state, card)
    if has_two_life_land_entry(card, state, controller):
        if choice not in land_entry_options(state, controller, card):
            raise ValueError("Unavailable land-entry payment choice")
        if choice == "pay_two_life":
            pay_life(state, controller, 2)
            state.log.append(f"{state.players[controller].name} pays 2 life as {card.name} enters.")
        card.tapped = effect_tapped or choice == "tapped"
    else:
        card.tapped = effect_tapped
        from rules_engine.land_types import printed_land_abilities_lost
        if "Land" in (effective_types(state, card) or []) and not printed_land_abilities_lost(state, card, entering=True, controller=controller):
            apply_land_entry(card)
