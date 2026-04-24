from __future__ import annotations

from effects.registry import resolve_effect
from game_state.state import MatchFactory


def test_draw_effect_handler() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 1})
    assert len(state.players[1].hand) == before + 1
