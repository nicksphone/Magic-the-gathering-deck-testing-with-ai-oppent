from __future__ import annotations

import json

from fastapi.testclient import TestClient

import main
from main import ACTIVE_MATCHES, app


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


def test_api_replacement_options_route_returns_choice_contract() -> None:
    deck = [{"quantity": 60, "card_name": "Island"}]
    with TestClient(app) as client:
        started = client.post(
            "/matches/start",
            json={
                "deck_a": deck,
                "deck_b": deck,
                "controller_a": "human",
                "controller_b": "human",
                "mode": "human_vs_human",
                "best_of": 3,
                "seed": 901,
            },
        )
        assert started.status_code == 200
        match_id = started.json()["id"]
        options = client.get(
            f"/matches/{match_id}/replacement-options",
            params={"event": "damage_to_player", "target_player": 1},
        )
        ACTIVE_MATCHES.pop(match_id, None)

    assert options.status_code == 200
    body = options.json()
    assert body["selection_key"] == "targets.replacement_source_id"
    assert body["default_policy"] == "latest_effect_timestamp"
    assert body["options"] == []


def test_api_diagnostic_run_routes_bound_artifact_reads(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run-20260721"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"matches": 20, "anomaly_count": 2}), encoding="utf-8")
    (run_dir / "anomaly-clusters.json").write_text(
        json.dumps([{"category": "stall", "count": index} for index in range(120)]),
        encoding="utf-8",
    )
    (run_dir / "anomaly_games.jsonl").write_text(
        "".join(json.dumps({"game": index}) + "\n" for index in range(30)),
        encoding="utf-8",
    )
    (run_dir / "games.jsonl").write_text(
        "".join(json.dumps({"game": index, "winner": 1, "log": list(range(100))}) + "\n" for index in range(30)),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DIAGNOSTICS_ROOT", tmp_path)

    with TestClient(app) as client:
        listing = client.get("/diagnostics/runs?limit=1")
        detail = client.get("/diagnostics/runs/run-20260721")
        missing = client.get("/diagnostics/runs/not-found")

    assert listing.status_code == 200
    assert len(listing.json()["runs"]) == 1
    assert detail.status_code == 200
    body = detail.json()
    assert body["summary"]["matches"] == 20
    assert body["anomaly_clusters"][0]["category"] == "stall"
    assert len(body["anomaly_clusters"]) == 100
    assert len(body["anomaly_samples"]) == 25
    assert len(body["games"]) == 20
    assert len(body["games"][0]["log_excerpt"]) == 80
    assert body["artifacts"]["anomaly_games"] == "anomaly_games.jsonl"
    assert body["artifacts"]["games"] == "games.jsonl"
    assert missing.status_code == 404


def test_api_diagnostic_compare_returns_numeric_deltas(tmp_path, monkeypatch) -> None:
    for name, matches, wins in (("left", 10, 4), ("right", 20, 13)):
        run_dir = tmp_path / name
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps({"matches": matches, "wins": {"deck_a": wins}, "label": name}),
            encoding="utf-8",
        )
    monkeypatch.setattr(main, "DIAGNOSTICS_ROOT", tmp_path)

    with TestClient(app) as client:
        response = client.get("/diagnostics/compare?left=left&right=right")
        bad = client.get("/diagnostics/compare?left=missing&right=right")

    assert response.status_code == 200
    assert response.json()["numeric_deltas"]["matches"]["delta_right_minus_left"] == 10
    assert response.json()["numeric_deltas"]["wins.deck_a"]["delta_right_minus_left"] == 9
    assert bad.status_code == 404


def test_api_diagnostic_replay_compare_returns_first_divergence(tmp_path, monkeypatch) -> None:
    for name, first_action in (("left", "Player A plays Island."), ("right", "Player A plays Mountain.")):
        run_dir = tmp_path / name
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(json.dumps({"matches": 1}), encoding="utf-8")
        (run_dir / "games.jsonl").write_text(
            json.dumps({"game": 1, "log": ["Game start.", f"Player A plays land {first_action}", "Player A passes priority."]}) + "\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(main, "DIAGNOSTICS_ROOT", tmp_path)

    with TestClient(app) as client:
        response = client.get("/diagnostics/compare/replay?left=left&right=right")
        identical = client.get("/diagnostics/compare/replay?left=left&right=left")
        bad_index = client.get("/diagnostics/compare/replay?left=left&right=right&left_game=20")

    assert response.status_code == 200
    assert response.json()["first_divergence"]["index"] == 1
    assert response.json()["first_divergence"]["category"] == "land_drop_mismatch"
    assert identical.json()["identical"] is True
    assert bad_index.status_code == 400
