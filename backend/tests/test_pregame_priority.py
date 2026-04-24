from __future__ import annotations

from game_state.state import MatchFactory
from rules_engine.engine import RulesEngine


def test_pregame_priority_passes_to_other_player_after_keep() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    assert state.pregame_pending is True
    assert state.priority_player == 1

    engine.take_action(state, 1, {"type": "keep_hand", "bottom_card_ids": []})
    assert state.pregame_pending is True
    assert state.priority_player == 2

    engine.take_action(state, 2, {"type": "keep_hand", "bottom_card_ids": []})
    assert state.pregame_pending is False
