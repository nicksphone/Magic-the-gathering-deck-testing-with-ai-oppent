"""Standalone cold-start probe; run ONLY from a disposable source tree.

python -m tests.release_agent.offline_probe
Fails rather than deleting an existing database/cache. Socket connections are
blocked before application imports, including startup/bootstrap and media tests.
"""
import json
from pathlib import Path
import socket


def run():
    backend = Path(__file__).resolve().parents[2]
    assert not (backend / "mtg_lab.db").exists(), "probe requires absent source-local DB"
    cache = backend / "card_data" / "image_cache"
    assert not cache.exists() or not any(p.name != ".gitkeep" for p in cache.iterdir()), "probe requires empty image cache"
    attempts = []
    def blocked(*args, **kwargs):
        attempts.append("blocked connection")
        raise AssertionError("offline probe attempted a network connection")
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    try:
        from fastapi.testclient import TestClient
        from sqlmodel import Session
        import main
        from persistence.repository import Repository
        from card_data.hydration import ready_for_match
        from card_data.placeholders import ensure_placeholder_image
        from scripts.export_builtin_oracle_seed import shipped_names
        names = sorted(set(shipped_names()))
        with TestClient(main.app) as client:
            assert client.get("/health").json()["ok"]
            assert client.get("/card-images/generic-token-creature.svg").status_code == 200
            with Session(main.engine) as session:
                repo = Repository(session)
                cards = main._hydrate_deck_cards(repo, [{"card_name": n, "quantity": 1} for n in names])
                assert len(cards) == len(names)
                assert all(ready_for_match(card) for card in cards)
            for card in cards:
                uri = ensure_placeholder_image(card["card_name"], card.get("type_line", ""))
                response = client.get(uri)
                assert response.status_code == 200 and "<svg" in response.text
            deck = [{"card_name": "Island", "quantity": 60}]
            payload = {"deck_a": deck, "deck_b": deck, "controller_a": "human", "controller_b": "human", "mode": "human_vs_human", "seed": 8128}
            response = client.post("/matches/start", json=payload, headers={"Idempotency-Key": "cold-start"})
            assert response.status_code == 200, response.text
            mid = response.json()["id"]
            assert client.post("/matches/start", json=payload, headers={"Idempotency-Key": "cold-start"}).json()["id"] == mid
            main.ACTIVE_MATCHES.pop(mid)
            with Session(main.engine) as session:
                main._restore_active_matches(Repository(session), mid)
            assert main.ACTIVE_MATCHES[mid].root_seed == 8128
        assert attempts == []
        print(json.dumps({"ok": True, "initial_database": "absent", "initial_image_cache": "empty", "hydrated_names": len(names), "served_fallback_assets": len(names), "network_attempts": len(attempts), "seed": 8128, "restart_snapshot": "restored"}, sort_keys=True))
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create


if __name__ == "__main__":
    run()
