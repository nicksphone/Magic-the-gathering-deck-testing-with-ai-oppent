"""QUEUED SQL lease: run only in a new full source root, never the live checkout."""
from copy import deepcopy
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event

import main
from game_state.state import pregame_actor
from persistence.db import engine
from tests.test_api_input_contracts import snapshot

PRODUCTION = "https://lab.example"
DEVELOPMENT = "http://127.0.0.1:12345"
LOOPBACK = "http://127.0.0.1:5173"


def start_payload():
    deck = [{"quantity": 60, "card_name": "Island"}]
    return {"deck_a": deck, "deck_b": deck, "controller_a": "human",
            "controller_b": "human", "mode": "human_vs_human", "seed": 8128}


@pytest.fixture
def supported_match():
    # Injected BEFORE main import by the leased runner, not modified after import.
    assert main.TRUSTED_BROWSER_ORIGINS == (PRODUCTION, DEVELOPMENT, LOOPBACK)
    original = dict(main.ACTIVE_MATCHES)
    try:
        with TestClient(main.app, base_url=PRODUCTION) as client:
            response = client.post("/matches/start", json=start_payload())
            assert response.status_code == 200, response.text
            match = main.ACTIVE_MATCHES[response.json()["id"]]
            assert match.state.pregame_pending
            yield client, match
    finally:
        main.ACTIVE_MATCHES.clear()
        main.ACTIVE_MATCHES.update(original)


def complete_root_snapshot():
    return {
        "matches": {mid: snapshot(match) for mid, match in main.ACTIVE_MATCHES.items()},
        "jobs": deepcopy(main.SIM_JOBS),
        "cancel_events": {key: signal.is_set() for key, signal in main.SIM_JOB_CANCEL_EVENTS.items()},
    }


def raw_rejection(path, origins, monkeypatch):
    observations = {"body": 0, "dependency": 0, "sql": 0, "action": 0, "sync": 0}
    messages = []

    def forbidden_dependency():
        observations["dependency"] += 1
        pytest.fail("Untrusted Origin entered a repository dependency")

    def forbidden_sql(*_args):
        observations["sql"] += 1
        pytest.fail("Untrusted Origin entered SQL")

    def forbidden_action(*_args, **_kwargs):
        observations["action"] += 1
        pytest.fail("Untrusted Origin entered checked action")

    def forbidden_sync(*_args, **_kwargs):
        observations["sync"] += 1
        pytest.fail("Untrusted Origin entered remote card sync")

    async def receive():
        observations["body"] += 1
        pytest.fail("Untrusted Origin consumed the request body")

    async def send(message):
        messages.append(message)

    original_overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.get_repo] = forbidden_dependency
    event.listen(engine, "before_cursor_execute", forbidden_sql)
    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(main, "checked_action", forbidden_action)
            patcher.setattr(main.ScryfallSyncService, "sync_card_by_name", forbidden_sync)
            scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                     "method": "POST", "scheme": "https", "path": path,
                     "raw_path": path.encode("ascii"), "root_path": "", "query_string": b"",
                     "client": ("127.0.0.1", 1000), "server": ("lab.example", 443),
                     "headers": [(b"host", b"lab.example"), (b"content-type", b"application/json")]
                                + [(b"origin", origin) for origin in origins]}
            # Actual full app path. Reject without a blocking await/body read.
            coroutine = main.app(scope, receive, send)
            with pytest.raises(StopIteration):
                coroutine.send(None)
    finally:
        event.remove(engine, "before_cursor_execute", forbidden_sql)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original_overrides)
    assert observations == {"body": 0, "dependency": 0, "sql": 0, "action": 0, "sync": 0}
    assert messages[0]["status"] == 403
    assert json.loads(messages[1]["body"])["detail"]["code"] == "untrusted_browser_origin"


@pytest.mark.parametrize("target", ["start", "action", "sync", "sync-bulk", "preflight"])
@pytest.mark.parametrize("origins", [
    [b"https://evil.example"], [b"null"], [b""],
    [PRODUCTION.encode("ascii"), PRODUCTION.encode("ascii")],
    [PRODUCTION.encode("ascii"), b"https://evil.example"],
])
def test_real_supported_start_then_rejection_preserves_complete_root_and_sql(
    supported_match, monkeypatch, target, origins,
):
    _, match = supported_match
    paths = {"start": "/matches/start", "action": f"/matches/{match.state.id}/action",
             "sync": "/cards/sync", "sync-bulk": "/cards/sync-bulk",
             "preflight": "/simulate/batch/preflight"}
    before = complete_root_snapshot()
    raw_rejection(paths[target], origins, monkeypatch)
    assert complete_root_snapshot() == before


@pytest.mark.parametrize("origin", [PRODUCTION, DEVELOPMENT, LOOPBACK, None])
def test_trusted_and_no_origin_native_start_preflight_and_recovery(supported_match, origin):
    client, _ = supported_match
    headers = {} if origin is None else {"Origin": origin}
    payload = start_payload()
    key = uuid4().hex
    preflight = client.post("/simulate/batch/preflight",
                            json={"deck_a": payload["deck_a"], "deck_b": payload["deck_b"]}, headers=headers)
    assert preflight.status_code == 200, preflight.text
    started = client.post("/matches/start", json=payload, headers={**headers, "Idempotency-Key": key})
    assert started.status_code == 200, started.text
    if origin:
        assert started.headers["access-control-allow-origin"] == origin
        assert started.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in started.headers
    mid = started.json()["id"]
    match = main.ACTIVE_MATCHES[mid]
    action = {"player_id": pregame_actor(match.state), "action": {"type": "keep_hand"}}
    write_headers = {**headers, "Idempotency-Key": key + "-keep", "X-Match-Revision": str(match.revision)}
    accepted = client.post(f"/matches/{mid}/action", json=action, headers=write_headers)
    assert accepted.status_code == 200, accepted.text
    before = snapshot(main.ACTIVE_MATCHES[mid])
    main.ACTIVE_MATCHES.pop(mid)
    restored = client.get(f"/matches/{mid}", headers=headers)
    assert restored.status_code == 200, restored.text
    replay = client.post(f"/matches/{mid}/action", json=action, headers=write_headers)
    assert replay.status_code == 200, replay.text
    assert snapshot(main.ACTIVE_MATCHES[mid]) == before


@pytest.mark.parametrize("origin, status", [(PRODUCTION, 200), (DEVELOPMENT, 200),
                                          ("https://evil.example", 400), ("null", 400)])
def test_real_cors_preflight_does_not_enter_dependencies(supported_match, origin, status):
    client, _ = supported_match
    before = complete_root_snapshot()

    def forbidden_dependency():
        pytest.fail("CORS preflight entered repository dependency")

    original = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.get_repo] = forbidden_dependency
    try:
        response = client.options("/matches/start", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key,x-match-revision",
        })
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original)
    assert response.status_code == status
    if status == 200:
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers
    assert complete_root_snapshot() == before
