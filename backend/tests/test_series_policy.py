import pytest

from game_state.series_policy import game_seed, next_play_draw_chooser
from scripts import regression_matrix_replay as replay


@pytest.mark.parametrize("winner,chooser,expected", [(1, 1, 2), (2, 2, 1), (0, 1, 1), (0, 2, 2)])
def test_next_game_choice_matches_loser_and_draw_rules(winner, chooser, expected):
    assert next_play_draw_chooser(winner, chooser) == expected


def test_seed_schedule_preserves_legacy_none_and_one_based_provenance():
    assert [game_seed(44, number) for number in (1, 2, 3)] == [44, 45, 46]
    assert game_seed(None, 2) is None
    with pytest.raises(ValueError):
        game_seed(44, 0)
    with pytest.raises(ValueError):
        next_play_draw_chooser(None, 1)


def test_replay_retains_chooser_after_draw_not_last_starting_seat(monkeypatch):
    winners = iter((1, 0, 2, 1))
    starts = []

    def fake_game(*args, starting_player):
        starts.append(starting_player)
        return {"winner": next(winners), "turn": 5, "log": [], "log_hash": str(args[2]), "timeout": False}

    monkeypatch.setattr(replay, "run_game", fake_game)
    result = replay.run_match([], [], 80, "strong", 100, 3)
    assert starts == [1, 2, 2, 1]
    assert [game["play_draw_chooser"] for game in result["games"]] == starts
    assert [game["seed"] for game in result["games"]] == [80, 81, 82, 83]
    assert result["winner"] == 1


def test_replay_does_not_play_next_game_after_unresolved_timeout(monkeypatch):
    calls = []

    def fake_game(*args, **kwargs):
        calls.append(args[2])
        return {"winner": None, "turn": 40, "log": [], "log_hash": "timeout", "timeout": True}

    monkeypatch.setattr(replay, "run_game", fake_game)
    result = replay.run_match([], [], 80, "strong", 100, 3)
    assert calls == [80]
    assert result["winner"] is None
    assert result["timeout"]
    assert result["games_played"] == 1


def test_replay_can_start_player_two_with_real_engine_and_skip_their_first_draw(monkeypatch):
    from ai.agent import AIAgent, AIDecision

    monkeypatch.setattr(AIAgent, "choose_action", lambda self, state, moves, pid: AIDecision(
        {"type": "keep_hand"} if state.pregame_pending else {"type": "pass_priority"}, "fixture"))
    deck = [{"quantity": 60, "card_name": "Island"}]
    result = replay.run_game(deck, deck, 17, "strong", 40, starting_player=2)
    assert result["starting_player"] == 2
    first_untap = next(line for line in result["log"] if "untaps." in line)
    first_draw = next(line for line in result["log"] if "draws a card." in line)
    assert first_untap == "Player B untaps."
    assert first_draw.startswith("Player A draws a card.")
