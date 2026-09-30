from __future__ import annotations

from game_state.state import Zone
from rules_engine.card_types import is_token_card
from rules_engine.events import emit_event_batch
from rules_engine.replacement import graveyard_destination


def is_departed_token(card) -> bool:
    return card.zone != Zone.BATTLEFIELD and is_token_card(card)


def put_into_graveyard(state, cid: str) -> Zone:
    """Move an already-removed card to its actual destination after replacement."""
    card = state.cards[cid]
    if is_departed_token(card):
        return card.zone
    zone = Zone(graveyard_destination(state, card))
    destination = getattr(state.players[card.owner], zone.value)
    if cid not in destination:
        destination.append(cid)
    card.move_to_zone(zone)
    return zone


def move_spell_from_stack(state, item, destination: Zone = Zone.GRAVEYARD) -> Zone | None:
    """Apply stack-departure replacements before restoring the physical card."""
    payload = item.payload or {}
    card = state.cards.get(item.source_card_id)
    if payload.get("__stack_copy_kind") or card is None or card.zone != Zone.STACK:
        return None
    if payload.get("__flashback") or payload.get("__aftermath"):
        destination = Zone.EXILE
    if destination == Zone.GRAVEYARD:
        destination = put_into_graveyard(state, card.id)
    else:
        zone_ids = getattr(state.players[card.owner], destination.value)
        if card.id not in zone_ids:
            zone_ids.append(card.id)
        card.move_to_zone(destination)
    from rules_engine.alternative_casts import restore_printed_characteristics
    restore_printed_characteristics(card)
    return destination


def discard_selected(state, player_id: int, card_ids: list[str]) -> bool:
    return discard_simultaneous(state, {player_id: card_ids})


def exile_selected_from_hand(state, player_id: int, card_ids: list[str]) -> bool:
    hand = state.players[player_id].hand
    if (len(set(card_ids)) != len(card_ids)
            or any(cid not in hand or state.cards[cid].zone != Zone.HAND for cid in card_ids)):
        return False
    for cid in card_ids:
        card = state.cards[cid]
        hand.remove(cid)
        state.players[card.owner].exile.append(cid)
        card.move_to_zone(Zone.EXILE)
        state.log.append(f"{state.players[player_id].name} exiles {card.name} from their hand.")
    return True


def discard_simultaneous(state, selections: dict[int, list[str]]) -> bool:
    """Validate every hand before any card moves, then emit one discard event batch."""
    for player_id, card_ids in selections.items():
        if player_id not in state.players or not isinstance(card_ids, list) or any(not isinstance(cid, str) for cid in card_ids) or len(set(card_ids)) != len(card_ids):
            return False
        hand = state.players[player_id].hand
        if any(cid not in hand or state.cards[cid].zone != Zone.HAND or is_departed_token(state.cards[cid]) for cid in card_ids):
            return False
    events = []
    for player_id, card_ids in selections.items():
        player = state.players[player_id]
        for cid in card_ids:
            card = state.cards[cid]
            player.hand.remove(cid)
            put_into_graveyard(state, cid)
            state.log.append(f"{player.name} discards {card.name}.")
            events.append({"card_id": cid, "controller": player_id})
    if events:
        emit_event_batch(state, "discard", events)
    return True
