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


def test_api_saved_deck_completeness_routes_return_structured_reports() -> None:
    with TestClient(app) as client:
        all_reports = client.get("/decks/completeness")
        decks = client.get("/decks").json()
        first_id = decks[0]["id"] if decks else None
        one_report = client.get(f"/decks/{first_id}/card-completeness") if first_id else None

    assert all_reports.status_code == 200
    if all_reports.json():
        assert "report" in all_reports.json()[0]
    if one_report is not None:
        assert one_report.status_code == 200
        assert "report" in one_report.json()
