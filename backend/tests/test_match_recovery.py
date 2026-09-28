"""Source-local database: execute these tests only from disposable source."""
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlmodel import Session
from sqlalchemy.exc import OperationalError

import main
from persistence.db import engine
from persistence.repository import Repository
from tests.test_api_input_contracts import game, persist, snapshot


def headers(revision=0, key="retry-key"):
    return {"X-Match-Revision": str(revision), "Idempotency-Key": key}


def test_retry_reconciles_without_duplicate_land_and_conflicts_are_safe(game):
    client, match = game
    path = f"/matches/{match.state.id}/action"
    payload = {"player_id": 1, "action": {"type": "play_land", "card_id": match.state.players[1].hand[0]}}
    def write():
        return client.post(path, json=payload, headers=headers())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert [response.status_code for response in results] == [200, 200]
    assert match.revision == 1
    assert len(match.state.players[1].battlefield) == 1
    before = snapshot(match)
    conflict = client.post(path, json={"player_id": 1, "action": {"type": "pass_priority"}}, headers=headers())
    assert conflict.status_code == 409
    stale = client.post(path, json={"player_id": 1, "action": {"type": "pass_priority"}}, headers=headers(key="new-key"))
    assert stale.status_code == 409
    assert snapshot(match) == before
    assert client.get("/matches").status_code == 200
    assert match.state.id in {row["id"] for row in client.get("/matches").json()}


def test_receipt_revision_and_state_survive_restoration(game):
    client, match = game
    mid = match.state.id
    payload = {"player_id": 1, "action": {"type": "play_land", "card_id": match.state.players[1].hand[0]}}
    assert client.post(f"/matches/{mid}/action", json=payload, headers=headers()).status_code == 200
    main.ACTIVE_MATCHES.pop(mid)
    with Session(engine) as session:
        main._restore_active_matches(Repository(session))
    restored = main.ACTIVE_MATCHES[mid]
    assert restored.revision == 1
    response = client.post(f"/matches/{mid}/action", json=payload, headers=headers())
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert len(restored.state.players[1].battlefield) == 1


def test_snapshot_failure_rolls_back_memory_and_pending_history(game, monkeypatch):
    client, match = game
    with Session(engine) as session:
        repo = Repository(session)
        decks = repo.list_decks()
        match.deck_ids = (decks[0].id, decks[1].id)
    match.state.winner = 1
    match.current_game_recorded = False
    persist(match)
    before = snapshot(match)
    def fail(self, *args):
        raise OperationalError("injected storage failure", {}, Exception("test"))
    monkeypatch.setattr(Repository, "save_active_match", fail)
    # Autoplay first finalizes the game/history; failed snapshot must undo both.
    response = client.post(f"/matches/{match.state.id}/autoplay", headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "match_storage_unavailable"
    assert snapshot(match) == before


def test_commit_failure_rolls_back_action_and_receipt(game, monkeypatch):
    client, match = game
    before = snapshot(match)
    monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(OperationalError("commit", {}, Exception("test"))))
    response = client.post(f"/matches/{match.state.id}/action", json={"player_id": 1, "action": {"type": "play_land", "card_id": match.state.players[1].hand[0]}}, headers=headers())
    assert response.status_code == 503
    assert snapshot(match) == before


@pytest.mark.parametrize("extra", [{"Idempotency-Key": "only"}, {"X-Match-Revision": "0"}, headers(revision="not-a-number"), headers(revision="9"*100), headers(key="x"*101)])
def test_malformed_write_headers_do_not_mutate(game, extra):
    client, match = game
    before = snapshot(match)
    response = client.post(f"/matches/{match.state.id}/autoplay", headers=extra)
    assert response.status_code in (409, 422)
    assert snapshot(match) == before


def test_locked_read_result_does_not_alias_later_live_mutations(game):
    _, match = game
    view = main.get_match(match.state.id)
    logs = list(view["log"])
    match.state.log.append("test-only later mutation")
    assert view["log"] == logs
    assert view["log"] is not match.state.log


def test_start_key_retries_one_durable_match_without_replacing_other_controllers(game):
    client, original = game
    deck = [{"quantity": 60, "card_name": "Island"}]
    payload = {"deck_a": deck, "deck_b": deck, "mode": "human_vs_human", "controller_b": "human"}
    key = f"start-{uuid4()}"

    def start():
        return client.post("/matches/start", json=payload, headers={"Idempotency-Key": key})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: start(), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    match_id = responses[0].json()["id"]
    assert responses[1].json()["id"] == match_id
    assert main.ACTIVE_MATCHES[original.state.id] is original

    conflict = client.post("/matches/start", json={**payload, "best_of": 5}, headers={"Idempotency-Key": key})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"

    created = main.ACTIVE_MATCHES.pop(match_id)
    assert created.revision == 0
    restored = start()
    assert restored.status_code == 200
    assert restored.json()["id"] == match_id
    assert main.ACTIVE_MATCHES[original.state.id] is original


def test_start_receipt_storage_failure_leaves_no_match_or_receipt(game, monkeypatch):
    client, original = game
    before = snapshot(original)
    ids_before = set(main.ACTIVE_MATCHES)
    deck = [{"quantity": 60, "card_name": "Island"}]
    key = f"failing-start-{uuid4()}"

    def fail(self, *_args):
        raise OperationalError("injected", {}, Exception("test"))

    monkeypatch.setattr(Repository, "save_match_start_receipt", fail)
    response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck}, headers={"Idempotency-Key": key})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "match_storage_unavailable"
    assert set(main.ACTIVE_MATCHES) == ids_before
    assert snapshot(original) == before
    with Session(engine) as session:
        assert Repository(session).get_match_start_receipt(key) is None
        assert {row.id for row in Repository(session).list_active_matches()} == ids_before


@pytest.mark.parametrize("key", ["", "x" * 101])
def test_invalid_start_key_rejected_before_creation(game, key):
    client, original = game
    before = snapshot(original)
    deck = [{"quantity": 60, "card_name": "Island"}]
    response = client.post("/matches/start", json={"deck_a": deck, "deck_b": deck}, headers={"Idempotency-Key": key})
    assert response.status_code == 422
    assert snapshot(original) == before
