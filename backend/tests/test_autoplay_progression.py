from __future__ import annotations

from sqlmodel import Session

from ai.agent import AIAgent
from game_state.state import MatchFactory
from main import ACTIVE_MATCHES, MatchController, autoplay_tick
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine


def test_autoplay_advances_to_next_game_for_full_ai_match() -> None:
    deck_a = [{"quantity": 60, "card_name": "Lightning Bolt"}]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.winner = 1
    state.score = {1: 0, 2: 0}

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="strong"), 2: AIAgent(difficulty="strong")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck_a, 2: deck_b},
        sideboards={1: [], 2: []},
        game_number=1,
        current_game_recorded=False,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    init_db()
    try:
        with Session(engine) as session:
            out = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert out["game_number"] == 2
    assert out["winner"] is None
    score = {str(k): v for k, v in out["score"].items()}
    assert score == {"1": 1, "2": 0}
    assert out["pregame_pending"] is True
    assert any("Starting game 2" in line for line in out["log"])
