from __future__ import annotations

from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine
from rules_engine.action_validation import ActionRejected
import pytest


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
        if state.turn > 1 and state.step == Step.UPKEEP:
            break

    assert Step.POSTCOMBAT_MAIN in seen
    assert Step.END_STEP in seen
    assert Step.CLEANUP in seen
    assert state.turn == 2
    assert state.step == Step.UPKEEP


def test_untap_has_no_priority_and_advances_to_upkeep() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.UNTAP
    state.active_player = state.priority_player = 1
    engine = RulesEngine()

    assert engine.legal_moves(state, 1) == []
    with pytest.raises(ActionRejected, match="untap step"):
        engine.take_action(state, 1, {"type": "cycle_card", "card_id": "missing"}, reject_invalid=True)
    assert state.step == Step.UNTAP
    engine.next_step(state)
    assert state.step == Step.UPKEEP
    assert state.priority_player == 1
    assert engine.legal_moves(state, 1)


def test_pregame_untaps_without_offering_a_priority_window() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    engine = RulesEngine()
    engine.take_action(state, 1, {"type": "keep_hand"})
    engine.take_action(state, 2, {"type": "keep_hand"})
    assert state.step == Step.UPKEEP
    assert state.priority_player == state.active_player
    assert any("untaps" in line for line in state.log)
