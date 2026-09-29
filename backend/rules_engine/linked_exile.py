from __future__ import annotations

from game_state.state import MatchState, Zone, assign_static_order_on_battlefield_entry
from rules_engine.events import emit_event_batch


def flush_linked_exile_returns(state: MatchState) -> None:
    """Finish 610.3 returns after the source's zone change, before the next SBA."""
    active = []
    returning = []
    for link in state.linked_exiles:
        source = state.cards.get(link["source_id"])
        present = [cid for cid in link["card_ids"]
                   if cid in state.cards and state.cards[cid].zone == Zone.EXILE
                   and cid in state.players[state.cards[cid].owner].exile
                   and state.cards[cid].effect_timestamp == link.get("card_timestamps", {}).get(cid, state.cards[cid].effect_timestamp)]
        if (source is not None and source.zone == Zone.BATTLEFIELD
                and source.id in state.players[source.controller].battlefield
                and source.effect_timestamp == link["source_timestamp"]):
            if present:
                active.append({**link, "card_ids": present})
            continue
        returning.extend(present)
    state.linked_exiles = active
    if not returning:
        return
    entries = []
    for cid in dict.fromkeys(returning):
        card = state.cards[cid]
        owner = state.players[card.owner]
        owner.exile.remove(cid)
        card.move_to_zone(Zone.BATTLEFIELD)
        card.controller = card.owner
        card.tapped = False
        card.summoning_sick = "Creature" in card.types
        card.entered_turn = state.turn
        owner.battlefield.append(cid)
        assign_static_order_on_battlefield_entry(state, cid)
        entries.append({"card_id": cid, "controller": card.owner})
        state.log.append(f"{card.name} returns from exile under its owner's control.")
    emit_event_batch(state, "enters_battlefield", entries)
