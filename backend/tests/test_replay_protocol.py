"""Seat-balanced regression accounting must not manufacture balance evidence."""
import argparse
import json
from types import SimpleNamespace

import pytest

from scripts.regression_matrix_replay import _pair_outcomes, _pair_schedule, _positive_int, run_match
from scripts import regression_matrix_replay as replay


def test_schedule_balances_each_seed_without_mutating_decks():
    left, right = {"name": "Left"}, {"name": "Right"}
    rows = list(_pair_schedule(left, right, 3))
    assert len(rows) == 6
    for forward, reverse in zip(rows[::2], rows[1::2]):
        assert forward[0] == reverse[0]
        assert forward[1:] == (left, right, 1)
        assert reverse[1:] == (right, left, 2)
    assert len({row[0] for row in rows}) == 3
    assert rows == list(_pair_schedule(left, right, 3))
    assert len(list(_pair_schedule(left, right, 3, False))) == 3


def test_summary_maps_winners_back_to_deck_identity_and_excludes_unresolved():
    rows = [
        {"deck_a_seat": 1, "winner": 1, "termination_status": "resolved"},
        {"deck_a_seat": 2, "winner": 1, "termination_status": "resolved"},
        # A timeout in one game excludes the entire series, even if it has a winner.
        {"deck_a_seat": 1, "winner": 1, "termination_status": "timeout_rules_issue"},
        {"deck_a_seat": 2, "winner": None, "termination_status": "draw_cap"},
    ]
    result = _pair_outcomes(rows)
    assert result["wins"] == {"deck_a": 1, "deck_b": 1}
    assert result["scheduled_matches"] == 4
    assert result["completed_matches"] == 2
    assert result["deck_a_win_rate_completed"] == 0.5
    assert result["deck_a_seat_counts"] == {"1": 2, "2": 2}
    assert result["unresolved"] == {"timeout_rules_issue": 1, "draw_cap": 1}


def test_no_completed_series_has_no_win_rate():
    assert _pair_outcomes([])["deck_a_win_rate_completed"] is None
    row = {"deck_a_seat": 1, "winner": None, "termination_status": "resolved"}
    assert _pair_outcomes([row])["unresolved"] == {"no_series_winner": 1}


@pytest.mark.parametrize("value", ["0", "-1"])
def test_cli_rejects_nonpositive_workload(value):
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int(value)


def test_series_records_each_game_seed(monkeypatch):
    monkeypatch.setattr("scripts.regression_matrix_replay.run_game", lambda *args, **kwargs: {
        "winner": 1, "turn": 3, "log_hash": "same", "log": [], "timeout": False,
    })
    result = run_match([], [], 22, "master", 100, 3)
    assert [game["seed"] for game in result["games"]] == [22, 23]


@pytest.mark.parametrize("single_seat", [False, True])
@pytest.mark.parametrize("metadata_drift", [False, True])
def test_cli_report_counts_logical_samples_not_repeatability_runs(monkeypatch, tmp_path, single_seat, metadata_drift):
    class SessionStub:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    left = {"name": "Left", "mainboard": [{"card_name": "Island"}]}
    right = {"name": "Right", "mainboard": [{"card_name": "Mountain"}]}
    monkeypatch.setattr(replay, "Session", SessionStub)
    monkeypatch.setattr(replay, "Repository", lambda _: SimpleNamespace(list_decks=lambda: []))
    for name in ("init_db", "ensure_builtin_decks", "ensure_expansion_top_decks"):
        monkeypatch.setattr(replay, name, lambda *args: None)
    monkeypatch.setattr(replay, "select_representative_decks", lambda *args, **kwargs: [left, right])
    monkeypatch.setattr(replay, "hydrate_deck_cards", lambda repo, deck: deck)
    calls = []

    def fake_match(deck_a, deck_b, seed, *args):
        calls.append((deck_a, deck_b, seed))
        return {"winner": 1, "turns": 5, "games_played": 2,
                "wins": {"deck_a": 2, "deck_b": 0}, "timeout": False,
                "log": [], "log_hash": "identical", "games": [
                    {"seed": seed, "starting_player": 1, "play_draw_chooser": 1,
                     "ticks": 1 if not metadata_drift or len(calls) % 2 else 2},
                    {"seed": seed + 1, "starting_player": 2, "play_draw_chooser": 2}]}

    monkeypatch.setattr(replay, "run_match", fake_match)
    output = tmp_path / "matrix.json"
    args = ["replay", "--matches-per-pair", "1", "--output", str(output)]
    if single_seat:
        args.append("--single-seat")
    monkeypatch.setattr("sys.argv", args)
    replay.main()
    result = json.loads(output.read_text())
    samples = 1 if single_seat else 2
    assert len(calls) == samples * 2
    assert result["matches"] == samples
    assert result["games"] == samples * 2
    assert result["determinism_failures"] == (samples if metadata_drift else 0)
    assert result["protocol"]["seat_balanced"] is not single_seat
    pair = result["pair_results"][0]
    assert pair["games"][0]["diverging_result_fields"] == (["games"] if metadata_drift else [])
    assert pair["games"][0]["anomaly_trace"] == ([] if metadata_drift else None)
    assert pair["outcomes"]["wins"] == {"deck_a": 1, "deck_b": 0 if single_seat else 1}
    if not single_seat:
        reverse = pair["games"][1]
        assert reverse["winner_deck"] == "Right"
        assert reverse["wins"] == {"deck_a": 0, "deck_b": 2}
        assert reverse["game_seeds"] == [calls[2][2], calls[2][2] + 1]
