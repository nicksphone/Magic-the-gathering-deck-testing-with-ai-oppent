from __future__ import annotations

from ai.agent import AIAgent
from main import ACTIVE_MATCHES, MatchController, PriorityStopsRequest, _human_priority_pause, set_priority_stops
from game_state.state import MatchFactory, Step
from rules_engine.engine import RulesEngine


def _build_match() -> MatchController:
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = Step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    return MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "human", 2: "human"},
        ai={1: AIAgent(), 2: AIAgent()},
        mode="human_vs_human",
        deck_ids=(None, None),
        mainboards={1: deck_a, 2: deck_b},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )


def test_human_priority_pause_respects_configured_step_stops() -> None:
    match = _build_match()
    assert _human_priority_pause(match, 1) is True
    match.state.priority_stops[1] = set()
    assert _human_priority_pause(match, 1) is False


def test_set_priority_stops_updates_match_state() -> None:
    match = _build_match()
    ACTIVE_MATCHES[match.state.id] = match
    try:
        out = set_priority_stops(
            match.state.id,
            PriorityStopsRequest(player_id=1, stops=["upkeep", "end_step"]),
        )
    finally:
        ACTIVE_MATCHES.pop(match.state.id, None)
    assert out["priority_stops"]["1"] == ["upkeep", "end_step"]
