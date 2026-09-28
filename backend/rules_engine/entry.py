from __future__ import annotations

import re

from rules_engine.land_rules import apply_land_entry
from rules_engine.replacement import can_pay_life


def has_two_life_land_entry(card) -> bool:
    if "Land" not in (card.types or []):
        return False
    subject = rf"(?:this land|{re.escape(card.name)})"
    return bool(re.search(
        rf"as {subject} enters(?: the battlefield)?, you may pay 2 life\.\s*if you don't, it enters tapped\.",
        card.oracle_text or "", re.IGNORECASE,
    ))


def land_entry_options(state, controller: int, card) -> list[str]:
    if not has_two_life_land_entry(card):
        return []
    options = ["tapped"]
    if can_pay_life(state, controller, 2):
        options.append("pay_two_life")
    return options


def pause_for_land_entries(state, controller: int, card_ids: list[str], effect_key: str, payload: dict) -> bool:
    choices = payload.get("__entry_choices") or {}
    for card_id in card_ids:
        card = state.cards[card_id]
        if not has_two_life_land_entry(card) or card_id in choices:
            continue
        options = land_entry_options(state, controller, card)
        reserved_life = 2 * sum(value == "pay_two_life" for value in choices.values())
        if state.players[controller].life - reserved_life < 2:
            options = [option for option in options if option != "pay_two_life"]
        forced_tapped = bool(payload.get("tapped"))
        state.pending_mechanic_choice = {
            "kind": "land_entry", "player_id": controller, "options": options,
            "option_labels": {"tapped": "Enter tapped", "pay_two_life": "Pay 2 life (effect still makes it tapped)" if forced_tapped else "Pay 2 life to enter untapped"},
            "entry_card_id": card_id, "effect_key": effect_key, "effect_payload": dict(payload),
            "label": f"Choose how {card.name} enters",
        }
        state.priority_player = controller
        state.passed_priority = set()
        return True
    return False


def apply_entry_choice(state, controller: int, card, *, choice: str = "tapped", effect_tapped: bool = False) -> None:
    if has_two_life_land_entry(card):
        if choice not in land_entry_options(state, controller, card):
            raise ValueError("Unavailable land-entry payment choice")
        if choice == "pay_two_life":
            state.players[controller].life -= 2
            state.log.append(f"{state.players[controller].name} pays 2 life as {card.name} enters.")
        card.tapped = effect_tapped or choice == "tapped"
    else:
        card.tapped = effect_tapped
        if "Land" in (card.types or []):
            apply_land_entry(card)
