from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def test_turn_progression_visits_postcombat_end_and_cleanup() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.turn = 1
    state.active_player = 1
    state.priority_player = 1
    state.step = Step.PRECOMBAT_MAIN
    engine = RulesEngine()

    seen = []
    for _ in range(20):
        seen.append(state.step)
        engine.next_step(state)
        if state.turn > 1 and state.step == Step.UNTAP:
            break

    assert Step.POSTCOMBAT_MAIN in seen
    assert Step.END_STEP in seen
    assert Step.CLEANUP in seen
    assert state.turn == 2
    assert state.step == Step.UNTAP
