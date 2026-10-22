"""Concurrent real ASGI routes with ordinary pytest-owned temporary SQLite."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from game_state.state import MatchFactory, Step
from tests.cleanup_canonical_db4e import canonical_entry
from tests.temporary_characteristics_http_fixture import owned_database, source_default_identity
from tests.test_temporary_characteristics_http import (
    controller_view, db_dump, install, persist, restore, snapshot,
)


@pytest.fixture
def seam_api(monkeypatch, tmp_path):
    import main
    import persistence.db as db

    original_default = source_default_identity()
    engine = create_engine("sqlite:///" + str(tmp_path / "state.sqlite3"),
                           connect_args={"check_same_thread": False})
    api = SimpleNamespace(main=main, engine=engine, client=None, directory=tmp_path)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(main, "ACTIVE_MATCHES", {})
    monkeypatch.setattr(main.app, "dependency_overrides", {})

    def forbidden(*args, **kwargs):
        pytest.fail("No default database, application startup or remote sync")

    monkeypatch.setattr(main, "init_db", forbidden)
    monkeypatch.setattr(main.app.router, "lifespan_context", forbidden)
    from card_data.sync import ScryfallSyncService
    monkeypatch.setattr(ScryfallSyncService, "sync_card_by_name", forbidden)
    try:
        with owned_database(engine):
            # No lifespan/listener and no shared Repository/Session: the real
            # get_repo -> get_session path uses the patched owned file engine.
            api.client = TestClient(main.app)
            try:
                yield api
            finally:
                api.client.close()
    finally:
        engine.dispose()
        assert source_default_identity() == original_default


def stable(api, controller):
    return (snapshot(controller.state), controller_view(api, controller),
            db_dump(api.engine))


def install_humans(api, state, seat):
    controller = install(api, state, seat)
    controller.controllers = {1: "human", 2: "human"}
    controller.mode = "human_vs_human"
    persist(api, controller)
    return controller


def post_action(api, controller, seat, action):
    response = api.client.post(
        f"/matches/{controller.state.id}/action",
        json={"player_id": seat, "action": action},
    )
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == controller.revision
    return response


def record_seam(api, request, **numeric):
    # Only public case labels, counts/statuses and a final equality digest.
    value = {"case": request.node.name, "transport": "ASGI_TestClient", **numeric}
    with (api.directory / "rc-seam-result.json").open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)


@pytest.mark.parametrize(
    "seat,revisioned", [(1, False), (2, False), (1, True), (2, True)],
    ids=["seat1-unversioned", "seat2-unversioned", "seat1-revisioned", "seat2-revisioned"],
)
def test_manual_and_autoplay_same_match_are_serial_and_durable(
        seam_api, monkeypatch, request, seat, revisioned):
    api = seam_api
    deck = [canonical_entry("Island", 60)]
    state = MatchFactory.from_decks(deck, deck, seed=17031)
    state.pregame_pending = False
    state.active_player = state.priority_player = seat
    state.step = Step.END_STEP
    assert all(len(player.hand) == 7 and not player.battlefield for player in state.players.values())
    controller = install_humans(api, state, seat)
    assert api.main._human_priority_pause(controller, seat) is False
    mid = state.id
    card = state.players[seat].hand[0]
    before_turn = state.turn
    base_revision = controller.revision
    body = {"player_id": seat, "action": {"type": "pass_priority"}}
    paths = {"manual": f"/matches/{mid}/action", "autoplay": f"/matches/{mid}/autoplay?ticks=1"}
    headers = {
        name: ({"Idempotency-Key": f"seam-{seat}-{name}",
                "X-Match-Revision": str(base_revision)} if revisioned else {})
        for name in paths
    }
    rendezvous, arrivals_lock, arrivals = Barrier(2), Lock(), []
    original_load = api.main._load_saved_match
    real_checked_action = api.main.checked_action
    checks = []

    def observed_checked_action(root, rules, actor, value):
        before = snapshot(root)
        event = {"revision": controller.revision, "actor": actor,
                 "action_type": value["type"], "step_before": root.step.value,
                 "priority_before": root.priority_player,
                 "passed_before": sorted(root.passed_priority)}
        try:
            candidate = real_checked_action(root, rules, actor, value)
        except Exception:
            checks.append({**event, "returned": False,
                           "input_unchanged": snapshot(root) == before})
            raise
        checks.append({**event, "returned": True,
                       "input_unchanged": snapshot(root) == before,
                       "candidate_changed": snapshot(candidate) != before,
                       "step_after": candidate.step.value,
                       "priority_after": candidate.priority_player,
                       "passed_after": sorted(candidate.passed_priority)})
        return candidate

    def load_then_rendezvous(match_id, repo):
        loaded = original_load(match_id, repo)
        assert match_id == mid and loaded is controller
        with arrivals_lock:
            arrivals.append(True)
        # Both genuine requests arrive before the unchanged decorator's RLock.
        rendezvous.wait(timeout=10)
        return loaded

    def send(name):
        kwargs = {"headers": headers[name]}
        if name == "manual":
            kwargs["json"] = body
        return api.client.post(paths[name], **kwargs)

    with monkeypatch.context() as observed:
        observed.setattr(api.main, "_load_saved_match", load_then_rendezvous)
        observed.setattr(api.main, "checked_action", observed_checked_action)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {name: pool.submit(send, name) for name in paths}
            responses = {name: future.result(timeout=30) for name, future in pending.items()}
    assert len(arrivals) == 2 and not rendezvous.broken
    assert api.main.checked_action is real_checked_action
    collision_checks = list(checks)
    statuses = {name: response.status_code for name, response in responses.items()}
    if revisioned:
        assert sorted(statuses.values()) == [200, 409]
        winner = next(name for name in responses if statuses[name] == 200)
        loser = next(name for name in responses if statuses[name] == 409)
        assert responses[loser].json()["detail"]["code"] == "stale_revision"
        assert controller.revision == base_revision + 1
        assert len(controller.mutation_receipts) == 1
        assert headers[winner]["Idempotency-Key"] in controller.mutation_receipts
        unchanged = stable(api, controller)
        repeated = send(winner)
        assert repeated.status_code == 200
        assert stable(api, controller) == unchanged
        stale = send(loser)
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_revision"
        assert stable(api, controller) == unchanged
    else:
        assert statuses["autoplay"] == 200 and statuses["manual"] in (200, 422)
        if statuses["manual"] == 422:
            assert responses["manual"].json()["detail"]["code"] == "illegal_action"
        accepted_revisions = sorted(response.json()["revision"]
                                    for response in responses.values() if response.status_code == 200)
        assert accepted_revisions == list(range(base_revision + 1,
                                                base_revision + 1 + len(accepted_revisions)))
        assert controller.revision == base_revision + len(accepted_revisions)
        assert controller.mutation_receipts == {}

    accepted = [response for response in responses.values() if response.status_code == 200]
    returned_in_collision = [event for event in collision_checks if event["returned"]]
    assert len(returned_in_collision) == len(accepted)
    assert all(event["input_unchanged"] for event in collision_checks)
    for response in accepted:
        witnessed = [event for event in returned_in_collision
                     if event["revision"] == response.json()["revision"]]
        assert len(witnessed) == 1 and witnessed[0]["action_type"] == "pass_priority"
        assert witnessed[0]["candidate_changed"]
    latest = max(accepted, key=lambda response: response.json()["revision"])
    authoritative = api.client.get(f"/matches/{mid}")
    assert authoritative.status_code == 200
    assert authoritative.json() == latest.json()

    autoplay_committed_during_collision = statuses["autoplay"] == 200
    autoplay_response = responses["autoplay"]
    reconciled = False
    if not autoplay_committed_during_collision:
        # A legitimate revision conflict never reached checked_action. Record
        # one fresh-revision request separately, not as a collision commit.
        assert revisioned and statuses["autoplay"] == 409 and statuses["manual"] == 200
        fresh_headers = {"Idempotency-Key": f"seam-{seat}-autoplay-reconciled",
                         "X-Match-Revision": str(controller.revision)}
        with monkeypatch.context() as observed:
            observed.setattr(api.main, "checked_action", observed_checked_action)
            autoplay_response = api.client.post(paths["autoplay"], headers=fresh_headers)
        assert autoplay_response.status_code == 200
        unchanged = stable(api, controller)
        repeated = api.client.post(paths["autoplay"], headers=fresh_headers)
        assert repeated.status_code == 200 and stable(api, controller) == unchanged
        reconciled = True

    assert api.main.checked_action is real_checked_action
    autoplay_checks = [event for event in checks if event["returned"]
                       and event["revision"] == autoplay_response.json()["revision"]]
    assert len(autoplay_checks) == 1
    autoplay_check = autoplay_checks[0]
    assert autoplay_check["input_unchanged"] and autoplay_check["candidate_changed"]
    assert autoplay_check["action_type"] == "pass_priority"
    assert (autoplay_check["step_before"], autoplay_check["priority_before"], autoplay_check["passed_before"]) != (
        autoplay_check["step_after"], autoplay_check["priority_after"], autoplay_check["passed_after"])
    committed_posts = len(accepted) + int(reconciled)
    assert controller.revision == base_revision + committed_posts
    current = controller.state
    assert current.turn == before_turn
    assert current.step == (Step.CLEANUP if committed_posts == 2 else Step.END_STEP)
    assert all(len(player.hand) == 7 and not player.battlefield
               and player.lands_played_this_turn == 0 for player in current.players.values())
    authoritative = api.client.get(f"/matches/{mid}")
    assert authoritative.status_code == 200
    assert authoritative.json() == (autoplay_response if reconciled else latest).json()
    unchanged = stable(api, controller)
    for actor, action in [
        (seat, {"type": "play_land", "card_id": "not-a-live-object"}),
        (3 - seat, {"type": "play_land", "card_id": card}),
    ]:
        rejected = api.client.post(paths["manual"], json={"player_id": actor, "action": action})
        assert rejected.status_code == 422
        assert stable(api, controller) == unchanged
    restored = restore(api, controller)
    assert stable(api, restored) == unchanged
    assert restored.controllers == {1: "human", 2: "human"}
    digest = hashlib.sha256(json.dumps(unchanged, sort_keys=True).encode()).hexdigest()
    record_seam(api, request, seat=seat, revisioned=revisioned, requests_arrived=2,
                statuses=statuses, revision_delta=restored.revision - base_revision,
                autoplay_committed_during_collision=autoplay_committed_during_collision,
                autoplay_reconciled_after_stale=reconciled, autoplay_checked_step=autoplay_check,
                collision_checked_calls=len(collision_checks), atomic_negative_checks=2,
                priority_after=restored.state.priority_player,
                state_controller_sql_restored_equal=True, final_digest=digest)
