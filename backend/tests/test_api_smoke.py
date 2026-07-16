from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_api_health_and_builtin_deck_routes() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        builtins = client.get("/decks/builtin")

    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert builtins.status_code == 200
    assert "Tokens" in builtins.json()


def test_api_card_image_route_serves_local_fallback_asset() -> None:
    with TestClient(app) as client:
        response = client.get("/card-images/generic-token-creature.svg")

    assert response.status_code == 200
    assert "svg" in response.text[:200].lower()
