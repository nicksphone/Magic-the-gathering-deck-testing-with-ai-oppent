"""Interactive BO3 play/draw choice and seed provenance."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.agent import AIAgent
from game_state.state import MatchFactory
from main import (
    ACTIVE_MATCHES, MatchController, NextGameRequest, _controller_snapshot,
    _restore_active_matches, _serialize_match_controller,
    _start_next_game_state, app, next_game,
)
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine


DECK = [{"quantity": 30, "card_name": "Island"}, {"quantity": 30, "card_name": "Mountain"}]


def _match(*, winner=1, controllers=None):
    game = MatchFactory.from_decks(DECK, DECK, seed=91)
    game.winner = winner
    return MatchController(
        state=game, rules=RulesEngine(), controllers=controllers or {1: "human", 2: "human"},
        ai={1: AIAgent(), 2: AIAgent()}, mode="human_vs_human",
        deck_ids=(None, None), mainboards={1: DECK, 2: DECK},
        sideboards={1: [], 2: []}, game_number=1,
        current_game_recorded=True, match_complete=False, best_of=3, root_seed=91,
    )


def _hands(game):
    return {
        pid: [game.cards[cid].name for cid in game.players[pid].hand]
        for pid in (1, 2)
    }


def test_loser_plays_game_two_with_replayable_seed():
    match = _match()
    _start_next_game_state(match, play_first=True)
    expected = MatchFactory.from_decks(DECK, DECK, seed=92)
    assert match.game_number == 2
    assert match.state.active_player == 2
    assert _hands(match.state) == _hands(expected)
    assert _serialize_match_controller(match)["game_seed"] is None
    assert _controller_snapshot(match)["root_seed"] == 91
    match.match_complete = True
    assert _serialize_match_controller(match)["game_seed"] == 92


def test_loser_may_choose_draw_and_choice_is_not_open_to_winner():
    init_db()
    match = _match()
    ACTIVE_MATCHES[match.state.id] = match
    try:
        with pytest.raises(HTTPException) as missing:
            next_game(match.state.id)
        assert missing.value.status_code == 422
        with pytest.raises(HTTPException) as wrong:
            next_game(match.state.id, payload=NextGameRequest(player_id=1, play_first=False))
        assert wrong.value.status_code == 422
        assert match.game_number == 1
        assert match.state.winner == 1
        result = next_game(match.state.id, payload=NextGameRequest(player_id=2, play_first=False))
        assert result["game_number"] == 2
        assert result["active_player"] == 1
        assert result["game_seed"] is None
    finally:
        ACTIVE_MATCHES.pop(match.state.id, None)


def test_ai_loser_chooses_play_without_human_payload():
    init_db()
    match = _match(controllers={1: "human", 2: "ai"})
    ACTIVE_MATCHES[match.state.id] = match
    try:
        result = next_game(match.state.id)
        assert result["active_player"] == 2
        assert result["next_play_draw_chooser"] is None
    finally:
        ACTIVE_MATCHES.pop(match.state.id, None)


def test_http_choice_and_restored_seed_provenance():
    match = _match()
    match_id = match.state.id
    with TestClient(app) as client:
        ACTIVE_MATCHES[match_id] = match
        try:
            rejected = client.post(f"/matches/{match_id}/next-game", json={"player_id": 1, "play_first": True})
            assert rejected.status_code == 422
            chosen = client.post(f"/matches/{match_id}/next-game", json={"player_id": 2, "play_first": False})
            assert chosen.status_code == 200, chosen.text
            assert (chosen.json()["active_player"], chosen.json()["game_seed"]) == (1, None)
            ACTIVE_MATCHES.pop(match_id)
            with Session(engine) as session:
                _restore_active_matches(Repository(session))
            restored = ACTIVE_MATCHES[match_id]
            assert restored.root_seed == 91
            assert _serialize_match_controller(restored)["game_seed"] is None
            assert _controller_snapshot(restored)["root_seed"] == 91
            assert _hands(restored.state) == _hands(match.state)
        finally:
            ACTIVE_MATCHES.pop(match_id, None)
