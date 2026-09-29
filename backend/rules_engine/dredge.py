from __future__ import annotations

import re

from game_state.state import Zone
from rules_engine.zone_actions import is_departed_token, put_into_graveyard


def dredge_options(state, player_id: int) -> list[dict]:
    player = state.players[player_id]
    result = []
    for cid in player.graveyard:
        if is_departed_token(state.cards[cid]):
            continue
        match = re.search(r"\bdredge\s+(\d+)", state.cards[cid].oracle_text or "", re.IGNORECASE)
        if match and len(player.library) >= int(match.group(1)):
            result.append({"card_id": cid, "count": int(match.group(1))})
    return result


def resolve_dredge(state, controller: int, payload: dict) -> None:
    from rules_engine.events import emit_event
    player_id = int(payload.get("target_player", controller))
    card_id = payload["dredge_card_id"]
    option = next((option for option in dredge_options(state, player_id) if option["card_id"] == card_id), None)
    if option is None:
        return
    player = state.players[player_id]
    for _ in range(option["count"]):
        cid = player.library.pop()
        put_into_graveyard(state, cid)
        emit_event(state, "mill", {"card_id": cid, "controller": player_id})
    player.graveyard.remove(card_id)
    player.hand.append(card_id)
    state.cards[card_id].move_to_zone(Zone.HAND)
    state.log.append(f"{player.name} dredges {state.cards[card_id].name}, milling {option['count']} instead of drawing.")


def offer_dredge_choice(state, controller: int, payload: dict) -> bool:
    if payload.get("__replacement_source_id") or payload.get("__skip_dredge_choice"):
        return False
    player_id = int(payload.get("target_player", controller))
    options = dredge_options(state, player_id)
    if not options:
        return False
    state.pending_mechanic_choice = {"kind": "draw", "player_id": player_id, "options": ["draw"] + [option["card_id"] for option in options], "remaining_draws": 0, "draw_payload": {**payload, "amount": 1}, "controller": controller}
    state.priority_player = player_id
    state.passed_priority = set()
    return True


def complete_draw_choice(state, player_id: int, action: dict) -> bool:
    from effects.handlers import draw_cards
    pending = state.pending_mechanic_choice
    chosen = action.get("choice_id")
    if not pending or pending["kind"] != "draw" or pending["player_id"] != player_id or chosen not in pending["options"]:
        return False
    if chosen != "draw" and not any(option["card_id"] == chosen for option in dredge_options(state, player_id)):
        return False
    state.pending_mechanic_choice = None
    payload = dict(pending["draw_payload"])
    if chosen == "draw":
        payload["__skip_dredge_choice"] = True
    else:
        payload["__replacement_source_id"] = chosen
    draw_cards(state, pending["controller"], payload)
    from rules_engine.stack_engine import resume_paused_resolution
    resume_paused_resolution(state, pending)
    return True
