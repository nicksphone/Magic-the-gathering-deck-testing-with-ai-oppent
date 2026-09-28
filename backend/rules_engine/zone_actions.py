from __future__ import annotations

from game_state.state import Zone
from rules_engine.events import emit_event_batch
from rules_engine.replacement import graveyard_destination


def put_into_graveyard(state, cid: str) -> Zone:
    """Move an already-removed card to its actual destination after replacement."""
    card = state.cards[cid]
    zone = Zone(graveyard_destination(state, card))
    destination = getattr(state.players[card.owner], zone.value)
    if cid not in destination:
        destination.append(cid)
    card.zone = zone
    return zone


def discard_selected(state, player_id: int, card_ids: list[str]) -> bool:
    """Validate a simultaneous discard before moving any card or emitting events."""
    player = state.players[player_id]
    if not isinstance(card_ids, list) or any(not isinstance(cid, str) for cid in card_ids) or len(set(card_ids)) != len(card_ids) or any(cid not in player.hand or state.cards[cid].zone != Zone.HAND for cid in card_ids):
        return False
    for cid in card_ids:
        card = state.cards[cid]
        player.hand.remove(cid)
        put_into_graveyard(state, cid)
        state.log.append(f"{player.name} discards {card.name}.")
    emit_event_batch(state, "discard", [{"card_id": cid, "controller": player_id} for cid in card_ids])
    return True
