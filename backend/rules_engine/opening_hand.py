"""Printed opening-hand actions; never infer conditional costs or extra choices."""
import re

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.oracle_text import without_reminder_text
from rules_engine.events import emit_event


def can_begin_on_battlefield(card) -> bool:
    if not set(card.types).intersection({"Creature", "Enchantment", "Artifact", "Land", "Planeswalker"}):
        return False
    text = without_reminder_text(card.oracle_text or "")
    subject = rf"(?:this card|{re.escape(card.name)})"
    clause = rf"if {subject} is in your opening hand, you may begin the game with (?:it|{subject}) on the battlefield\."
    if not any(re.fullmatch(clause, paragraph.strip(), re.I) for paragraph in text.split("\n")):
        return False
    # Additional entry replacements/choices require their own supported handler.
    return not re.search(r"\bas .+ enters\b|\benters (?:the battlefield )?(?:with|tapped)\b", text, re.I)


def begin_opening_hand_choices(state, players=None) -> bool:
    remaining = list(players if players is not None else (state.active_player, 3 - state.active_player))
    while remaining:
        pid = remaining.pop(0)
        hand = state.players[pid].hand
        if not any("opening hand" in (state.cards[cid].oracle_text or "").lower() for cid in hand):
            continue
        options = [cid for cid in hand if can_begin_on_battlefield(state.cards[cid])]
        state.pending_mechanic_choice = {
            "kind": "opening_hand", "player_id": pid, "options": [*options, "__finish_opening__"],
            "count": 1, "min_count": 1, "remaining_players": remaining,
            "option_labels": {"__finish_opening__": "Finish opening-hand actions"},
            "label": "Use a supported opening-hand battlefield action, or finish. Conditional entry and reveal effects are not implemented.",
        }
        state.trigger_staging = True
        state.trigger_staging_event = "opening_hand"
        state.priority_player = pid
        return True
    state.pending_mechanic_choice = None
    return False


def finish_opening_hand_choice(state, player_id, action) -> bool:
    pending = state.pending_mechanic_choice
    ids = action.get("card_ids")
    if (pending["player_id"] != player_id or not isinstance(ids, list) or len(ids) != 1
            or not isinstance(ids[0], str) or ids[0] not in pending["options"]):
        return False
    cid = ids[0]
    if cid == "__finish_opening__":
        begin_opening_hand_choices(state, pending["remaining_players"])
        return True
    player = state.players[player_id]
    if cid not in player.hand or not can_begin_on_battlefield(state.cards[cid]):
        return False
    card = state.cards[cid]
    player.hand.remove(cid)
    player.battlefield.append(cid)
    card.move_to_zone(Zone.BATTLEFIELD)
    card.controller = player_id
    card.entered_turn = state.turn
    card.summoning_sick = False
    assign_static_order_on_battlefield_entry(state, cid)
    emit_event(state, "enters_battlefield", {"card_id": cid, "controller": player_id})
    state.log.append(f"{player.name} begins with {card.name} on the battlefield.")
    begin_opening_hand_choices(state, [player_id, *pending["remaining_players"]])
    return True
