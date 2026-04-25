from __future__ import annotations

from game_state.state import MatchFactory, Zone
from rules_engine.events import emit_event
from rules_engine.stack_engine import resolve_top_of_stack


def _put_static_permanent_with_oracle(state, player_id: int, name: str, oracle: str) -> str:
    p = state.players[player_id]
    cid = p.hand[0]
    p.hand.remove(cid)
    p.battlefield.append(cid)
    c = state.cards[cid]
    c.zone = Zone.BATTLEFIELD
    c.types = ["Creature"]
    c.name = name
    c.oracle_text = oracle
    return cid


def test_sheoldred_you_draw_trigger_gains_life_not_draw() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    _put_static_permanent_with_oracle(
        state,
        1,
        "Sheoldred, the Apocalypse",
        "Whenever you draw a card, you gain 2 life. Whenever an opponent draws a card, they lose 2 life.",
    )

    hand_before = len(state.players[1].hand)
    life_before = state.players[1].life
    emit_event(state, "draw_card", {"player_id": 1, "card_id": "x"})
    assert state.stack[-1].effect_key == "gain_life"
    resolve_top_of_stack(state)
    assert state.players[1].life == life_before + 2
    assert len(state.players[1].hand) == hand_before


def test_sheoldred_opponent_draw_trigger_loses_life() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    _put_static_permanent_with_oracle(
        state,
        1,
        "Sheoldred, the Apocalypse",
        "Whenever you draw a card, you gain 2 life. Whenever an opponent draws a card, they lose 2 life.",
    )

    life_before = state.players[2].life
    emit_event(state, "draw_card", {"player_id": 2, "card_id": "y"})
    assert state.stack[-1].effect_key == "lose_life"
    resolve_top_of_stack(state)
    assert state.players[2].life == life_before - 2
