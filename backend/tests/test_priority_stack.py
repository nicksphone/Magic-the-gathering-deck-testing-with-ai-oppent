from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def test_stack_resolves_after_priority_passes() -> None:
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    engine = RulesEngine()
    state.pregame_pending = False
    state.kept_hands = {1, 2}

    state.step = Step.PRECOMBAT_MAIN
    state.priority_player = 1
    cid = state.players[1].hand[0]
    engine.take_action(state, 1, {"type": "cast_spell", "card_id": cid})
    assert len(state.stack) >= 1
    engine.take_action(state, 2, {"type": "pass_priority"})
    engine.take_action(state, 1, {"type": "pass_priority"})
    assert len(state.stack) == 0
