from __future__ import annotations

from sqlmodel import Session

from ai.agent import AIAgent, AIDecision
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


def test_autoplay_forces_ai_land_drop_on_own_main_phase() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0

    battlefield_before = len(p1.battlefield)
    hand_before = len(p1.hand)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: AIAgent(difficulty="strong", archetype="Control"), 2: AIAgent(difficulty="strong", archetype="Control")},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
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
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(p1.battlefield) == battlefield_before + 1
    assert len(p1.hand) == hand_before - 1
    assert p1.lands_played_this_turn == 1


def test_autoplay_land_guard_overrides_ai_pass_when_land_is_legal() -> None:
    class PassOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "pass_priority"}, reasoning="forced test pass")

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0
    battlefield_before = len(p1.battlefield)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: PassOnlyAI(), 2: PassOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
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
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(p1.battlefield) == battlefield_before + 1
    assert p1.lands_played_this_turn == 1


def test_autoplay_land_guard_overrides_ai_cast_when_land_is_legal() -> None:
    class CastOnlyAI:
        def choose_action(self, state, legal_moves, player_id):
            return AIDecision(action={"type": "cast_spell", "card_id": "fake-spell"}, reasoning="forced test cast")

    deck = [{"quantity": 60, "card_name": "Island"}]
    state = MatchFactory.from_decks(deck, deck)
    state.pregame_pending = False
    state.kept_hands = {1, 2}
    state.step = state.step.PRECOMBAT_MAIN
    state.active_player = 1
    state.priority_player = 1
    p1 = state.players[1]
    p1.lands_played_this_turn = 0
    battlefield_before = len(p1.battlefield)

    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "ai", 2: "ai"},
        ai={1: CastOnlyAI(), 2: CastOnlyAI()},
        mode="ai_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck, 2: deck},
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
            _ = autoplay_tick(state.id, ticks=1, repo=Repository(session))
    finally:
        ACTIVE_MATCHES.pop(state.id, None)

    assert len(p1.battlefield) == battlefield_before + 1
    assert p1.lands_played_this_turn == 1
