from __future__ import annotations

from game_state.state import MatchFactory, Zone
from rules_engine.events import emit_event


def _put_trigger_creature(state, player_id: int, oracle: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.types = ["Creature"]
    c.oracle_text = oracle
    c.name = f"T{player_id}-{cid[:4]}"
    return cid


def test_apnap_trigger_order_on_shared_event() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.active_player = 1

    _put_trigger_creature(state, 1, "Whenever a creature dies, draw a card.")
    _put_trigger_creature(state, 2, "Whenever a creature dies, draw a card.")

    emit_event(state, "creature_dies", {"card_id": "x"})
    assert len(state.stack) >= 2
    assert state.stack[0].controller == 1
    assert state.stack[1].controller == 2
