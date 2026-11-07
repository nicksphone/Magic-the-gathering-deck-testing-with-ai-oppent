from __future__ import annotations
from rules_engine.type_effects import effective_types

import re
from copy import copy

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


def _lands_enter_untapped(state, controller: int) -> bool:
    from rules_engine.continuous import printed_abilities_suppressed
    from game_state.state import Zone
    for cid in state.players[controller].battlefield:
        source = state.cards.get(cid)
        if (source is not None and source.zone == Zone.BATTLEFIELD and source.controller == controller
                and any(re.fullmatch(r'lands you control enter(?: the battlefield)? untapped\.',
                                     line.strip(), re.I) for line in (source.oracle_text or '').splitlines())
                and not printed_abilities_suppressed(state, cid)):
            return True
    return False


def land_entry_options(state, controller: int, card) -> list[str]:
    if 'Land' not in effective_types(state, card):
        return []
    shock = has_two_life_land_entry(card, state, controller)
    untapped = _lands_enter_untapped(state, controller)
    if not shock:
        manual = state.replacement_choice_required and controller in state.replacement_choice_players
        from rules_engine.land_types import printed_land_abilities_lost
        if (not untapped or not manual or 'Land' not in effective_types(state, card)
                or printed_land_abilities_lost(state, card, entering=True, controller=controller)):
            return []
        probe = copy(card)
        probe.tapped = False
        apply_land_entry(probe)
        return ['tapped', 'untapped'] if probe.tapped else []
    options = ['tapped']
    if can_pay_life(state, controller, 2):
        options.append('pay_two_life')
    if untapped:
        options.append('untapped')
    return options


def pause_for_land_entries(state, controller: int, card_ids: list[str], effect_key: str, payload: dict, *, controllers=None, projections=None) -> bool:
    choices = payload.get("__entry_choices") or {}
    for card_id in card_ids:
        card = projections[card_id] if card_id in (projections or {}) else state.cards[card_id]
        from rules_engine.card_faces import day_night_entry_face
        card = day_night_entry_face(state, card)
        recipient = (controllers or {}).get(card_id, controller)
        options = land_entry_options(state, recipient, card)
        if not options or card_id in choices:
            continue
        reserved_life = 2 * sum(value == "pay_two_life" and (controllers or {}).get(cid, controller) == recipient
                                for cid, value in choices.items())
        if state.players[recipient].life - reserved_life < 2:
            options = [option for option in options if option != "pay_two_life"]
        forced_tapped = bool(payload.get("tapped"))
        labels = {"tapped": "Enter tapped", "pay_two_life": "Pay 2 life (effect still makes it tapped)"
                  if forced_tapped and not _lands_enter_untapped(state, recipient)
                  else "Pay 2 life to enter untapped"}
        if 'untapped' in options:
            labels['untapped'] = 'Enter untapped (apply untapped-entry replacement last)'
        state.pending_mechanic_choice = {
            "kind": "land_entry", "player_id": recipient, "options": options,
            "option_labels": labels,
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
    options = land_entry_options(state, controller, card)
    if has_two_life_land_entry(card, state, controller):
        if choice not in options:
            raise ValueError("Unavailable land-entry payment choice")
        if choice == "pay_two_life":
            pay_life(state, controller, 2)
            state.log.append(f"{state.players[controller].name} pays 2 life as {card.name} enters.")
        card.tapped = effect_tapped or choice == "tapped"
    else:
        if choice == 'untapped' and choice not in options:
            raise ValueError('Unavailable untapped-entry choice')
        card.tapped = effect_tapped
        from rules_engine.land_types import printed_land_abilities_lost
        if "Land" in (effective_types(state, card) or []) and not printed_land_abilities_lost(state, card, entering=True, controller=controller):
            apply_land_entry(card)
    if ('Land' in effective_types(state, card) and _lands_enter_untapped(state, controller)
            and not ('untapped' in options and choice == 'tapped')):
        card.tapped = False
