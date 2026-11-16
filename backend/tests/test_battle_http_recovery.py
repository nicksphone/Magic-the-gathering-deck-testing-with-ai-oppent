"""Battle recovery across response loss, a cold backend process and write races.

Response loss is injected after the real ASGI app commits; it is not a TCP
fault. Restart uses a new Python app/HTTP process and the same owned SQLite
file. Initial Battle combat positions are declared canonical fixtures.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Lock
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from game_state.state import Step
from tests.temporary_characteristics_http_fixture import owned_database, source_default_identity
from tests.test_battle_combat import position
from tests.test_manual_autoplay_collision_http import install_humans, stable


@pytest.fixture
def recovery_api(monkeypatch, tmp_path):
    import main
    import persistence.db as db

    original_default = source_default_identity()
    engine = create_engine("sqlite:///" + str(tmp_path / "battle.sqlite3"),
                           connect_args={"check_same_thread": False})
    api = SimpleNamespace(main=main, engine=engine, path=Path(engine.url.database))
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(main, "ACTIVE_MATCHES", {})
    monkeypatch.setattr(main.app, "dependency_overrides", {})
    with ExitStack() as resources:
        resources.enter_context(owned_database(engine))
        api.client = TestClient(main.app)
        resources.callback(api.client.close)
        api.close = resources.close
        try:
            yield api
        finally:
            api.close()
            engine.dispose()
            assert source_default_identity() == original_default


def combat(api, seat):
    state, battle, attacker = position(seat)
    # The operator elects to stop at their attack decision in either seat.
    state.priority_stops.setdefault(seat, set()).add(Step.DECLARE_ATTACKERS)
    controller = install_humans(api, state, seat)
    action = {"type": "attack", "attackers": [attacker],
              "attack_targets": {attacker: "battle:" + battle}}
    return controller, battle, attacker, {"player_id": seat, "action": action}


def headers(key, revision=0):
    return {"Idempotency-Key": key, "X-Match-Revision": str(revision)}


@pytest.mark.parametrize("seat", [1, 2])
def test_battle_response_loss_reconciles_before_retry(recovery_api, seat):
    api = recovery_api
    controller, battle, attacker, body = combat(api, seat)
    path = f"/matches/{controller.state.id}/action"
    lost = False

    async def response_loss(scope, receive, send):
        nonlocal lost
        messages = []

        async def buffered_send(message):
            messages.append(message)

        await api.main.app(scope, receive, buffered_send)
        if not lost and scope["method"] == "POST" and scope["path"] == path:
            lost = True
            # This occurs outside the application, after its transaction commits.
            raise httpx.ReadTimeout("Injected loss of an accepted Battle response")
        for message in messages:
            await send(message)

    client = TestClient(response_loss)
    try:
        with pytest.raises(httpx.ReadTimeout):
            client.post(path, json=body, headers=headers("lost-attack"))
        assert lost and controller.revision == 1
        committed = stable(api, controller)
        current = client.get(f"/matches/{controller.state.id}")
        assert current.status_code == 200 and current.json()["revision"] == 1
        assert controller.state.attackers == [attacker]
        assert controller.state.attack_targets == {attacker: "battle:" + battle}
        retried = client.post(path, json=body, headers=headers("lost-attack"))
        assert retried.status_code == 200 and retried.json()["revision"] == 1
        assert stable(api, controller) == committed
    finally:
        client.close()


@pytest.mark.parametrize("seat", [1, 2])
def test_battle_retry_is_durable_after_a_new_backend_process(recovery_api, seat):
    api = recovery_api
    controller, battle, attacker, body = combat(api, seat)
    match_id = controller.state.id
    response = api.client.post(f"/matches/{match_id}/action", json=body,
                               headers=headers("before-restart"))
    assert response.status_code == 200 and response.json()["revision"] == 1
    # Release the real owner and all connections before the next process opens it.
    api.close()
    environment = os.environ.copy()
    environment["MTG_DATABASE_PATH"] = str(api.path)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    worker = Path(__file__).with_name("battle_recovery_restart_worker.py")
    result = subprocess.run(
        [sys.executable, "-B", str(worker), str(api.path), match_id,
         str(seat), battle, attacker],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "revision": 1, "retry_status": 200, "stale_status": 409,
        "stored_game_unchanged": True,
    }


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("shared_key", [False, True], ids=["distinct-keys", "same-key"])
def test_battle_manual_autoplay_overlap_reconciles_one_revision(
        recovery_api, monkeypatch, seat, shared_key):
    api = recovery_api
    controller, battle, attacker, body = combat(api, seat)
    match_id = controller.state.id
    assert api.main._human_priority_pause(controller, seat) is True
    rendezvous, guard, entered = Barrier(2, timeout=10), Lock(), []
    load = api.main._load_saved_match

    def simultaneous_load(*args, **kwargs):
        with guard:
            synchronize = len(entered) < 2
            if synchronize:
                entered.append(True)
        if synchronize:
            rendezvous.wait()
        return load(*args, **kwargs)

    def request(kind):
        key = "shared-intent" if shared_key else kind
        path = f"/matches/{match_id}/action" if kind == "attack" else f"/matches/{match_id}/autoplay?ticks=1"
        return api.client.post(path, json=body if kind == "attack" else None,
                               headers=headers(key))

    with monkeypatch.context() as patch:
        patch.setattr(api.main, "_load_saved_match", simultaneous_load)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(request, ["attack", "autoplay"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["detail"]["code"] == (
        "idempotency_conflict" if shared_key else "stale_revision")
    assert controller.revision == 1
    reconciled = api.client.get(f"/matches/{match_id}")
    assert reconciled.status_code == 200 and reconciled.json()["revision"] == 1
    if responses[0].status_code == 409:
        # Autoplay won but paused for the human's legal attack. Reconcile first,
        # then issue a new intent against the newly observed revision.
        assert not controller.state.attackers
        offered = api.client.get(f"/matches/{match_id}/legal-moves")
        assert offered.status_code == 200
        legal = offered.json()
        assert legal["revision"] == 1 and legal["player_id"] == seat
        attack = next(move for move in legal["moves"] if move["type"] == "attack")
        assert attacker in attack["options"]
        defender = next(row["id"] for row in attack["defenders"]
                        if row["id"] == "battle:" + battle)
        retry_body = {"player_id": legal["player_id"], "action": {
            "type": attack["type"], "attackers": [attacker],
            "attack_targets": {attacker: defender},
        }}
        retry = api.client.post(f"/matches/{match_id}/action", json=retry_body,
                                headers=headers("reconciled-attack", legal["revision"]))
        assert retry.status_code == 200, retry.json().get("detail")
        assert retry.json()["revision"] == 2
    assert controller.state.attackers == [attacker]
    assert controller.state.attack_targets == {attacker: "battle:" + battle}
    assert controller.state.cards[attacker].tapped
    assert controller.state.cards[battle].counters["defense"] == 3
