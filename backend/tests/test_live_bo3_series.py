"""Natural seeded BO3 through the public match API, including a process-style restore."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from decks.builtin_decks import BUILTIN_DECKS
from main import ACTIVE_MATCHES, _restore_active_matches, app
from persistence.db import engine
from persistence.repository import Repository


def _built_in(name: str) -> list[dict]:
    return [
        {"quantity": int(quantity), "card_name": card_name}
        for quantity, card_name in (line.split(" ", 1) for line in BUILTIN_DECKS[name].strip().splitlines())
    ]


def test_seeded_live_ai_bo3_finishes_after_between_game_restore() -> None:
    payload = {
        "deck_a": _built_in("Mono Red Aggro"),
        "deck_b": _built_in("Burn"),
        "controller_a": "ai",
        "controller_b": "ai",
        "mode": "ai_vs_ai",
        "best_of": 3,
        "seed": 73,
    }
    with TestClient(app) as client:
        started = client.post("/matches/start", json=payload)
        assert started.status_code == 200, started.text
        state = started.json()
        match_id = state["id"]
        observed_games = {1}
        restored = False
        try:
            for _ in range(40):
                response = client.post(f"/matches/{match_id}/autoplay", params={"ticks": 100})
                assert response.status_code == 200, response.text
                state = response.json()
                observed_games.add(state["game_number"])
                if state["game_number"] >= 2 and not restored:
                    ACTIVE_MATCHES.pop(match_id)
                    with Session(engine) as session:
                        _restore_active_matches(Repository(session), match_id)
                    assert ACTIVE_MATCHES[match_id].root_seed == 73
                    assert client.get(f"/matches/{match_id}").json()["score"] == state["score"]
                    restored = True
                if state["match_complete"]:
                    break
            assert restored
            assert state["match_complete"], f"Live BO3 did not finish: game={state['game_number']} turn={state['turn']} score={state['score']}"
            assert max(state["score"].values()) == 2
            assert sum(state["score"].values()) == state["game_number"]
            assert observed_games == set(range(1, state["game_number"] + 1))
            assert state["game_number"] in {2, 3}
        finally:
            ACTIVE_MATCHES.pop(match_id, None)
