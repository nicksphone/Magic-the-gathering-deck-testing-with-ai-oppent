from __future__ import annotations

import pytest
from fastapi import HTTPException

from sqlmodel import Session

from game_state.state import MatchFactory
from decks.sideboard import apply_sideboard_swaps
from main import ACTIVE_MATCHES, MatchController, NextGameRequest, SideboardRequest, apply_sideboard, next_game
from main import _restore_active_matches
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from tests.test_api_input_contracts import game, persist, snapshot


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
                payload=SideboardRequest(player_id=1, cards_out=[{"card_name": "Counterspell", "quantity": 2}], cards_in=[{"card_name": "Negate", "quantity": 2}]),
                repo=repo,
            )
            assert first["sideboard_sizes"]["1"] == 4

            with pytest.raises(HTTPException):
                apply_sideboard(
                    state.id,
                    payload=SideboardRequest(player_id=1, cards_out=[{"card_name": "Island", "quantity": 2}], cards_in=[{"card_name": "Dispel", "quantity": 2}]),
                    repo=repo,
                )

            match.state.winner = 1
            apply_sideboard(state.id, payload=SideboardRequest(player_id=2, cards_out=[], cards_in=[]), repo=repo)
            next_game(state.id, payload=NextGameRequest(player_id=2, play_first=True))
            assert match.sideboarded_players == set()
    finally:
        ACTIVE_MATCHES.pop(state.id, None)


def test_http_sideboard_inventory_restore_and_next_game_deck(game) -> None:
    client, match = game
    match.mainboards[1] = [{"quantity": 45, "card_name": "Island"}, {"quantity": 15, "card_name": "Mountain"}]
    match.sideboards[1] = [{"quantity": 15, "card_name": "Forest"}]
    match.sideboards[2] = [{"quantity": 15, "card_name": "Swamp"}]
    match.controllers[2] = "ai"
    match.state.winner = 2
    match.state.score = {1: 0, 2: 1}
    match.current_game_recorded = True
    match.root_seed = 4
    persist(match)
    url = f"/matches/{match.state.id}"
    view = client.get(url).json()
    assert set(view["sideboarding"]) == {"1"}
    assert view["sideboarding"]["1"]["sideboard"] == [{"quantity": 15, "card_name": "Forest"}]

    before = snapshot(match)
    swap = {"player_id": 1, "cards_out": [{"quantity": 15, "card_name": "Mountain"}], "cards_in": [{"quantity": 15, "card_name": "Forest"}]}
    assert client.post(f"{url}/sideboard", json={**swap, "player_id": 2}).status_code == 403
    assert client.post(f"{url}/sideboard", json={**swap, "cards_out": [{"quantity": 14, "card_name": "Mountain"}]}).status_code == 400
    assert snapshot(match) == before

    accepted = client.post(f"{url}/sideboard", json=swap)
    assert accepted.status_code == 200, accepted.text
    inventory = accepted.json()["sideboarding"]["1"]
    assert inventory["applied"] is True
    assert inventory["sideboard"] == [{"quantity": 15, "card_name": "Mountain"}]
    assert {card["card_name"]: card["quantity"] for card in inventory["mainboard"]} == {"Island": 45, "Forest": 15}
    assert client.post(f"{url}/sideboard", json=swap).status_code == 400

    ACTIVE_MATCHES.pop(match.state.id)
    with Session(engine) as session:
        _restore_active_matches(Repository(session), match.state.id)
    restored = ACTIVE_MATCHES[match.state.id]
    assert client.get(url).json()["sideboarding"]["1"] == inventory
    started = client.post(f"{url}/next-game", json={"player_id": 1, "play_first": True})
    assert started.status_code == 200, started.text
    assert started.json()["game_number"] == 2
    assert "sideboarding" not in started.json()
    cards = restored.state.cards
    pool = restored.state.players[1].hand + restored.state.players[1].library
    assert len(pool) == 60
    assert {name: sum(cards[cid].name == name for cid in pool) for name in ("Island", "Forest", "Mountain")} == {"Island": 45, "Forest": 15, "Mountain": 0}

    restored.state.winner = 2
    restored.match_complete = True
    persist(restored)
    finished = snapshot(restored)
    assert client.post(f"{url}/sideboard", json={"player_id": 1, "cards_out": [], "cards_in": []}).status_code == 400
    assert snapshot(restored) == finished
