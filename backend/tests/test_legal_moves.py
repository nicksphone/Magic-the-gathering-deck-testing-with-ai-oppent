from __future__ import annotations

from game_state.state import MatchFactory
from rules_engine.engine import RulesEngine


def test_generates_basic_legal_moves() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    engine = RulesEngine()
    moves = engine.legal_moves(state, state.priority_player)
    move_types = {m["type"] for m in moves}
    assert "pass_priority" in move_types
