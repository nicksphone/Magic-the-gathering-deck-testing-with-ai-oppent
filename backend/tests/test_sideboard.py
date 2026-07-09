from __future__ import annotations

import pytest
from fastapi import HTTPException

from sqlmodel import Session

from game_state.state import MatchFactory
from decks.sideboard import apply_sideboard_swaps
from main import ACTIVE_MATCHES, MatchController, apply_sideboard, next_game
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine


def test_sideboard_swap_moves_cards_between_zones() -> None:
    main = [{"card_name": "Island", "quantity": 56}, {"card_name": "Counterspell", "quantity": 4}]
    side = [{"card_name": "Negate", "quantity": 3}, {"card_name": "Dispel", "quantity": 2}]

    new_main, new_side = apply_sideboard_swaps(
        main,
        side,
        cards_out=[{"card_name": "Counterspell", "quantity": 2}],
        cards_in=[{"card_name": "Negate", "quantity": 2}],
    )

    main_map = {x["card_name"]: x["quantity"] for x in new_main}
    side_map = {x["card_name"]: x["quantity"] for x in new_side}
    assert main_map["Counterspell"] == 2
    assert main_map["Negate"] == 2
    assert side_map["Negate"] == 1
    assert side_map["Counterspell"] == 2


def test_sideboard_can_only_be_applied_once_per_game() -> None:
    init_db()
    deck_a = [
        {"quantity": 56, "card_name": "Island"},
        {"quantity": 4, "card_name": "Counterspell"},
    ]
    side_a = [
        {"quantity": 2, "card_name": "Negate"},
        {"quantity": 2, "card_name": "Dispel"},
    ]
    deck_b = [{"quantity": 60, "card_name": "Mountain"}]
    state = MatchFactory.from_decks(deck_a, deck_b)
    state.winner = 1
    match = MatchController(
        state=state,
        rules=RulesEngine(),
        controllers={1: "human", 2: "human"},
        ai={1: object(), 2: object()},
        mode="player_vs_ai",
        deck_ids=(None, None),
        mainboards={1: deck_a, 2: deck_b},
        sideboards={1: side_a, 2: []},
        game_number=1,
        current_game_recorded=True,
        match_complete=False,
        best_of=3,
    )
    ACTIVE_MATCHES[state.id] = match
    try:
        with Session(engine) as session:
            repo = Repository(session)
            first = apply_sideboard(
                state.id,
                payload=type("SideboardPayload", (), {"player_id": 1, "cards_out": [{"card_name": "Counterspell", "quantity": 2}], "cards_in": [{"card_name": "Negate", "quantity": 2}]})(),
                repo=repo,
            )
            assert first["sideboard_sizes"]["1"] == 4

            with pytest.raises(HTTPException):
                apply_sideboard(
                    state.id,
                    payload=type("SideboardPayload", (), {"player_id": 1, "cards_out": [{"card_name": "Island", "quantity": 2}], "cards_in": [{"card_name": "Dispel", "quantity": 2}]})(),
                    repo=repo,
                )

            match.state.winner = 1
            next_game(state.id)
            assert match.sideboarded_players == set()
    finally:
        ACTIVE_MATCHES.pop(state.id, None)
