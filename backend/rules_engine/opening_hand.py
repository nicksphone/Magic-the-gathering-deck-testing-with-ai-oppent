"""Bounded printed opening actions with durable follow-up instructions."""
import re

from game_state.state import Zone, assign_static_order_on_battlefield_entry
from rules_engine.oracle_text import without_reminder_text
from rules_engine.events import emit_event


def opening_entry_spec(card) -> dict | None:
    if not set(card.types).intersection({"Creature", "Enchantment", "Artifact", "Land", "Planeswalker"}):
        return None
    text = without_reminder_text(card.oracle_text or "")
    subject = rf"(?:this card|{re.escape(card.name)})"
    clause = rf"if {subject} is in your opening hand, you may begin the game with (?:it|{subject}) on the battlefield\."
    paragraphs = text.split("\n")
    conditional = re.fullmatch(
        rf"if {subject} is in your opening hand and you['’]re not the starting player, "
        rf"you may begin the game with (?:it|{subject}) on the battlefield with a ([\w-]+) counter on it\. "
        r"if you do, exile a card from your hand\.",
        paragraphs[0].strip(), re.I,
    )
    if not conditional and not any(re.fullmatch(clause, paragraph.strip(), re.I) for paragraph in paragraphs):
        return None
    # Additional entry replacements/choices require their own supported handler.
    if re.search(r"\bas .+ enters\b|\benters (?:the battlefield )?(?:with|tapped)\b", text, re.I):
        return None
    return {"not_starting": True, "counter": conditional[1].lower(), "exile_hand": True} if conditional else {}


def can_begin_on_battlefield(card, state=None, player_id=None) -> bool:
    spec = opening_entry_spec(card)
    return spec is not None and (not spec.get("not_starting") or
                                (state is not None and player_id in state.players and player_id != state.active_player))


def begin_opening_hand_choices(state, players=None) -> bool:
    remaining = list(players if players is not None else (state.active_player, 3 - state.active_player))
    while remaining:
        pid = remaining.pop(0)
        hand = state.players[pid].hand
        if not any("opening hand" in (state.cards[cid].oracle_text or "").lower() for cid in hand):
            continue
        options = [cid for cid in hand if can_begin_on_battlefield(state.cards[cid], state, pid)]
        state.pending_mechanic_choice = {
            "kind": "opening_hand", "player_id": pid, "options": [*options, "__finish_opening__"],
            "count": 1, "min_count": 1, "remaining_players": remaining,
            "option_labels": {"__finish_opening__": "Finish opening-hand actions"},
            "label": "Use a supported opening-hand battlefield action, or finish. Other conditional entry, entry choices and reveal effects are not implemented.",
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
    if pending["kind"] == "opening_hand_exile":
        from rules_engine.zone_actions import exile_selected_from_hand
        if not exile_selected_from_hand(state, player_id, ids):
            return False
        begin_opening_hand_choices(state, [player_id, *pending["remaining_players"]])
        return True
    if cid == "__finish_opening__":
        begin_opening_hand_choices(state, pending["remaining_players"])
        return True
    player = state.players[player_id]
    if cid not in player.hand or not can_begin_on_battlefield(state.cards[cid], state, player_id):
        return False
    card = state.cards[cid]
    spec = opening_entry_spec(card)
    player.hand.remove(cid)
    player.battlefield.append(cid)
    card.move_to_zone(Zone.BATTLEFIELD)
    card.controller = player_id
    card.entered_turn = state.turn
    card.summoning_sick = False
    assign_static_order_on_battlefield_entry(state, cid)
    if spec.get("counter"):
        from rules_engine.counter_placement import put_counters
        put_counters(state, spec['counter'], 1, target_card_id=cid)
    emit_event(state, "enters_battlefield", {"card_id": cid, "controller": player_id})
    state.log.append(f"{player.name} begins with {card.name} on the battlefield.")
    if spec.get("exile_hand") and player.hand:
        state.pending_mechanic_choice = {
            "kind": "opening_hand_exile", "player_id": player_id,
            "options": list(player.hand), "count": 1, "min_count": 1,
            "remaining_players": pending["remaining_players"], "source_id": cid,
            "label": f"{card.name}: exile one card from your hand to finish the opening action",
        }
        return True
    begin_opening_hand_choices(state, [player_id, *pending["remaining_players"]])
    return True
