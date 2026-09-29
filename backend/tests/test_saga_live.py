"""Live Fable chapter resolution, including local snapshot recovery."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from game_state.state import Step, Zone
from main import ACTIVE_MATCHES, _persist_active_match, _restore_active_matches, app
from persistence.db import engine
from persistence.repository import Repository


def test_fable_final_chapter_survives_http_hydration_and_restart() -> None:
    deck_a = [
        {"quantity": 4, "card_name": "Fable of the Mirror-Breaker"},
        {"quantity": 56, "card_name": "Mountain"},
    ]
    deck_b = [{"quantity": 60, "card_name": "Island"}]
    with TestClient(app) as client:
        started = client.post("/matches/start", json={
            "deck_a": deck_a, "deck_b": deck_b, "controller_a": "human",
            "controller_b": "human", "mode": "human_vs_human", "seed": 919,
        })
        assert started.status_code == 200, started.text
        match_id = started.json()["id"]
        try:
            match = ACTIVE_MATCHES[match_id]
            state = match.state
            saga = next(card for card in state.cards.values() if card.owner == 1 and card.name.startswith("Fable of the Mirror-Breaker"))
            assert saga.layout == "transform" and len(saga.card_faces) == 2
            source_zone = getattr(state.players[1], saga.zone.value)
            source_zone.remove(saga.id)
            state.players[1].battlefield.append(saga.id)
            saga.zone = Zone.BATTLEFIELD
            saga.counters["__lore"] = 2
            state.pregame_pending = False
            state.kept_hands = {1, 2}
            state.turn = 4
            state.step = Step.PRECOMBAT_MAIN
            state.active_player = state.priority_player = 1
            match.rules._advance_sagas(state)
            assert state.stack[-1].effect_key == "exile_return_transformed"
            with Session(engine) as session:
                _persist_active_match(Repository(session), match)
            ACTIVE_MATCHES.pop(match_id)
            with Session(engine) as session:
                _restore_active_matches(Repository(session), match_id)
            assert ACTIVE_MATCHES[match_id].state.stack[-1].effect_key == "exile_return_transformed"

            for player_id in (1, 2):
                response = client.post(f"/matches/{match_id}/action", json={
                    "player_id": player_id, "action": {"type": "pass_priority"},
                })
                assert response.status_code == 200, response.text
            body = response.json()
            restored = ACTIVE_MATCHES[match_id].state
            card = restored.cards[saga.id]
            assert card.zone == Zone.BATTLEFIELD and card.selected_face_index == 1
            assert card.name == "Reflection of Kiki-Jiki"
            assert card.counters == {} and card.summoning_sick
            assert saga.id not in restored.players[1].exile
            assert saga.id in restored.players[1].battlefield
            view = next(view for view in body["players"]["1"]["battlefield"] if view["id"] == saga.id)
            assert view["name"] == "Reflection of Kiki-Jiki"
            assert view["selected_face_index"] == 1 and view["layout"] == "transform"
            assert view["power"] == 2 and view["toughness"] == 2
            assert view["type_line"] == "Enchantment Creature — Goblin Shaman"
        finally:
            ACTIVE_MATCHES.pop(match_id, None)
