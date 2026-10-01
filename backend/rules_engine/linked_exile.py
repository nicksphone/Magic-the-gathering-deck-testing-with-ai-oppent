from __future__ import annotations

from game_state.state import MatchState, Zone, assign_static_order_on_battlefield_entry, object_incarnation
from rules_engine.events import emit_event_batch


def linked_exiled_creatures(state: MatchState, source_id: str, timestamp: int) -> list[str]:
    return list(dict.fromkeys(
        cid for link in state.linked_exiles
        if link["source_id"] == source_id and link["source_timestamp"] == timestamp
        for cid in link["card_ids"]
        if cid in state.cards and state.cards[cid].zone == Zone.EXILE
        and cid in state.players[state.cards[cid].owner].exile
        and object_incarnation(state.cards[cid]) == link.get("card_timestamps", {}).get(cid, object_incarnation(state.cards[cid]))
        and "Creature" in state.cards[cid].types
    ))


def source_still_present(state: MatchState, source_id: str, timestamp: int) -> bool:
    source = state.cards.get(source_id)
    return bool(source and source.zone == Zone.BATTLEFIELD
                and source.id in state.players[source.controller].battlefield
                and object_incarnation(source) == timestamp)


def record_linked_exile(state: MatchState, source_id: str, timestamp: int,
                        card_ids: list[str], return_zone: Zone = Zone.BATTLEFIELD) -> None:
    if card_ids:
        state.linked_exiles.append({
            "source_id": source_id, "source_timestamp": timestamp,
            "card_ids": list(card_ids), "return_zone": return_zone.value,
            "card_timestamps": {cid: object_incarnation(state.cards[cid]) for cid in card_ids},
        })


def flush_linked_exile_returns(state: MatchState) -> None:
    """Finish 610.3 returns after the source's zone change, before the next SBA."""
    if state.pending_mechanic_choice or state.pending_replacement_choice:
        return
    active = []
    returning = []
    for link in state.linked_exiles:
        present = [cid for cid in link["card_ids"]
                   if cid in state.cards and state.cards[cid].zone == Zone.EXILE
                   and cid in state.players[state.cards[cid].owner].exile
                   and object_incarnation(state.cards[cid]) == link.get("card_timestamps", {}).get(cid, object_incarnation(state.cards[cid]))]
        if source_still_present(state, link["source_id"], link["source_timestamp"]):
            if present:
                active.append({**link, "card_ids": present})
            continue
        returning.extend((cid, Zone(link.get("return_zone", "battlefield"))) for cid in present)
    state.linked_exiles = active
    if not returning:
        return
    # Choice packets now own these expired links. No recipient changes zones
    # until all players have prepared this simultaneous return event.
    rows = [{'card_id': cid, 'destination': destination.value,
             'timestamp': object_incarnation(state.cards[cid])}
            for cid, destination in dict.fromkeys(returning)]
    rows.sort(key=lambda row: state.cards[row['card_id']].owner != state.active_player)
    return_linked_exiles(state, state.active_player, {'returning': rows})


def return_linked_exiles(state: MatchState, controller: int, payload: dict) -> None:
    from rules_engine.entry import pause_for_land_entries, apply_entry_choice
    from rules_engine.entry_counters import prepare_counter_entries, commit_entry_counters
    from rules_engine.zone_actions import is_departed_token

    rows = [row for row in payload['returning']
            if (card := state.cards.get(row['card_id'])) is not None
            and card.zone == Zone.EXILE and card.id in state.players[card.owner].exile
            and object_incarnation(card) == row['timestamp'] and not is_departed_token(card)]
    entering = [state.cards[row['card_id']] for row in rows if row['destination'] == Zone.BATTLEFIELD.value]
    controllers = {card.id: card.owner for card in entering}
    if pause_for_land_entries(state, controller, list(controllers), 'linked_exile_return', payload,
                              controllers=controllers):
        return
    if entering and prepare_counter_entries(state, controller, entering, 'linked_exile_return', payload,
                                            controllers=controllers):
        return
    entries = []
    for row in rows:
        cid, destination = row['card_id'], Zone(row['destination'])
        card = state.cards[cid]
        owner = state.players[card.owner]
        owner.exile.remove(cid)
        card.move_to_zone(destination)
        if destination == Zone.HAND:
            owner.hand.append(cid)
            state.log.append(f"{card.name} returns from exile to its owner's hand.")
        else:
            card.controller = card.owner
            apply_entry_choice(state, card.owner, card, choice=(payload.get('__entry_choices') or {}).get(cid, 'tapped'))
            card.summoning_sick = "Creature" in card.types
            card.entered_turn = state.turn
            owner.battlefield.append(cid)
            assign_static_order_on_battlefield_entry(state, cid)
            entries.append({"card_id": cid, "controller": card.owner})
            state.log.append(f"{card.name} returns from exile under its owner's control.")
    for entry in entries:
        commit_entry_counters(state, state.cards[entry['card_id']], payload)
    emit_event_batch(state, "enters_battlefield", entries)
