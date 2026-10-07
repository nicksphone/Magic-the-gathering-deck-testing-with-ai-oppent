"""Interactive BO3 play/draw choice and seed provenance."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.agent import AIAgent
from effects.registry import resolve_effect
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from game_state.state import MatchFactory, draw_card
from main import (
    ACTIVE_MATCHES, MatchController, NextGameRequest, _controller_snapshot,
    _post_step_finalize, _persist_active_match, _restore_active_matches, _serialize_match_controller,
    _start_next_game_state, app, next_game, apply_sideboard, SideboardRequest,
)
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from rules_engine.state_based_actions import apply_state_based_actions


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


def test_simultaneous_player_losses_are_a_draw():
    state = MatchFactory.from_decks(DECK, DECK, seed=101)
    state.players[1].life = 0
    state.players[2].poison = 10
    apply_state_based_actions(state)
    assert state.winner == 0
    assert sum("loses" in line for line in state.log) == 2
    assert any("game is a draw" in line for line in state.log)
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.winner == 0
    apply_state_based_actions(state)
    assert sum("game is a draw" in line for line in state.log) == 1


def test_empty_library_draw_loss_waits_for_state_based_actions():
    state = MatchFactory.from_decks(DECK, DECK, seed=102)
    state.players[1].library.clear()
    draw_card(state, 1)
    assert state.winner is None
    assert state.failed_draw_players == {1}
    restored = deserialize_match_snapshot(serialize_match_snapshot(state))
    assert restored.failed_draw_players == {1}
    apply_state_based_actions(restored)
    assert restored.winner == 2


def test_simultaneous_empty_library_draw_failures_are_a_draw():
    state = MatchFactory.from_decks(DECK, DECK, seed=103)
    for player in state.players.values():
        player.library.clear()
    draw_card(state, 1)
    draw_card(state, 2)
    assert state.winner is None
    apply_state_based_actions(state)
    assert state.winner == 0
    assert sum("loses after attempting to draw" in line for line in state.log) == 2


def test_multicard_draw_stops_after_first_empty_library_failure():
    state = MatchFactory.from_decks(DECK, DECK, seed=104)
    state.players[1].library = state.players[1].library[:1]
    before = len(state.players[1].hand)
    resolve_effect(state, 1, "draw_cards", {"amount": 3})
    assert len(state.players[1].hand) == before + 1
    assert state.failed_draw_players == {1}
    assert sum("attempted to draw from empty library" in line for line in state.log) == 1
    assert sum("draws 1" in line for line in state.log) == 1
    apply_state_based_actions(state)
    assert state.winner == 2


def test_drawn_game_keeps_score_and_previous_chooser_after_restore():
    init_db()
    match = _match(winner=0)
    match.play_draw_chooser = 2
    match.state.score = {1: 1, 2: 0}
    match.current_game_recorded = False
    with Session(engine) as session:
        repo = Repository(session)
        _post_step_finalize(match, repo)
        assert match.current_game_recorded and not match.match_complete
        assert match.state.score == {1: 1, 2: 0}
        _persist_active_match(repo, match)
        ACTIVE_MATCHES.pop(match.state.id, None)
        _restore_active_matches(repo, match.state.id)
    restored = ACTIVE_MATCHES[match.state.id]
    try:
        assert restored.play_draw_chooser == 2
        with TestClient(app) as client:
            url = f"/matches/{restored.state.id}"
            assert client.get(url).json()["next_play_draw_chooser"] == 2
            assert client.post(f"{url}/next-game", json={"player_id": 1, "play_first": True}).status_code == 422
            for pid in (1, 2):
                client.post(f"{url}/sideboard", json={"player_id": pid, "cards_out": [], "cards_in": []}).raise_for_status()
            result = client.post(f"{url}/next-game", json={"player_id": 2, "play_first": False})
            assert result.status_code == 200, result.text
            view = result.json()
            assert view["game_number"] == 2
            assert view["active_player"] == 1
            assert view["score"] == {"1": 1, "2": 0}
            assert restored.play_draw_chooser == 2
    finally:
        ACTIVE_MATCHES.pop(match.state.id, None)


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
        with Session(engine) as session:
            for pid in (1, 2):
                apply_sideboard(match.state.id, payload=SideboardRequest(player_id=pid, cards_out=[], cards_in=[]), repo=Repository(session))
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
        with Session(engine) as session:
            apply_sideboard(match.state.id, payload=SideboardRequest(player_id=1, cards_out=[], cards_in=[]), repo=Repository(session))
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
            for pid in (1, 2):
                client.post(f"/matches/{match_id}/sideboard", json={"player_id": pid, "cards_out": [], "cards_in": []}).raise_for_status()
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
