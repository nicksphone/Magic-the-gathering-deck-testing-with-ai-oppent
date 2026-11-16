"""Battle requests preserve owned HTTP/SQLite state on rejection and retry.

Initial mana/creatures are declared canonical fixture positions. Battle casting,
search, combat and the transformed-cast permission are then reached by HTTP.
The shared fixture owns a temporary SQLite file; no application DB is used.
"""
from copy import deepcopy

import pytest
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from game_state.state import Step, Zone
from persistence.repository import Repository
from tests.test_battle_product_acceptance import battle_position
from tests.test_manual_autoplay_collision_http import (
    install_humans, seam_api, stable,
)
from tests.test_temporary_characteristics_http import persist


STAGES = ("cast", "search", "attack", "transformed")


def write_headers(controller, key=None, revision=None):
    return {
        "Idempotency-Key": key or f"battle-{controller.revision}",
        "X-Match-Revision": str(controller.revision if revision is None else revision),
    }


def action_request(api, controller, actor, action, headers=None):
    return api.client.post(
        f"/matches/{controller.state.id}/action",
        json={"player_id": actor, "action": action},
        headers=write_headers(controller) if headers is None else headers,
    )


def accept(api, controller, actor, action):
    previous = controller.revision
    response = action_request(api, controller, actor, action)
    assert response.status_code == 200
    assert response.json()["revision"] == controller.revision == previous + 1


def advance_until(api, controller, predicate):
    for _ in range(32):
        if predicate(controller.state):
            return
        assert not controller.state.pending_mechanic_choice
        assert not controller.state.pending_replacement_choice
        accept(api, controller, controller.state.priority_player,
               {"type": "pass_priority"})
    raise AssertionError("HTTP play did not reach the requested Battle boundary")


def prepare_stage(api, seat, stage):
    state, battle, attackers = battle_position(seat)
    state.mechanic_choice_players = {seat}
    controller = install_humans(api, state, seat)
    cast = {"type": "cast_spell", "card_id": battle}
    if stage == "cast":
        return controller, cast

    accept(api, controller, seat, cast)
    advance_until(api, controller, lambda s: s.pending_mechanic_choice is not None)
    pending = controller.state.pending_mechanic_choice
    assert pending["kind"] == "search_library" and pending["player_id"] == seat
    search = {"type": "choose_mechanic", "card_ids": pending["options"][:2]}
    assert len(search["card_ids"]) == 2
    if stage == "search":
        return controller, search

    accept(api, controller, seat, search)
    advance_until(api, controller, lambda s: s.step == Step.DECLARE_ATTACKERS)
    assert controller.state.cards[battle].counters["defense"] == 3
    assert controller.state.cards[battle].battle_protector == 3 - seat
    attack = {"type": "attack", "attackers": attackers,
              "attack_targets": {cid: "battle:" + battle for cid in attackers}}
    if stage == "attack":
        return controller, attack

    assert stage == "transformed"
    accept(api, controller, seat, attack)
    advance_until(api, controller, lambda s: s.step == Step.DECLARE_BLOCKERS)
    accept(api, controller, 3 - seat, {"type": "block", "blocks": {}})
    advance_until(api, controller, lambda s: s.pending_mechanic_choice is not None)
    assert controller.state.pending_mechanic_choice["kind"] == "effect_cast"
    assert controller.state.cards[battle].zone == Zone.EXILE
    return controller, {"type": "cast_spell", "card_id": battle,
                        "from_exile": True, "selected_face_index": 1}


def illegal_choice(stage, action):
    result = deepcopy(action)
    if stage in {"cast", "transformed"}:
        result["selected_face_index"] = 1 if stage == "cast" else 0
    elif stage == "search":
        result["card_ids"] = ["not-a-library-card"]
    else:
        result["attack_targets"] = {
            cid: "battle:not-on-the-battlefield" for cid in result["attackers"]
        }
    return result


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("rejection", ["malformed", "stale", "wrong-human", "ai-seat", "illegal"])
def test_battle_rejection_preserves_state_controller_and_sqlite(
        seam_api, seat, stage, rejection):
    api = seam_api
    controller, action = prepare_stage(api, seat, stage)
    actor, headers, expected = seat, write_headers(controller), 422
    if rejection == "malformed":
        action = {**action, "unknown_battle_parameter": True}
    elif rejection == "stale":
        headers = write_headers(controller, revision=controller.revision + 1)
        expected = 409
    elif rejection == "wrong-human":
        actor = 3 - seat
    elif rejection == "ai-seat":
        controller.controllers[seat] = "ai"
        persist(api, controller)
        expected = 403
    else:
        action = illegal_choice(stage, action)
    before = stable(api, controller)
    response = action_request(api, controller, actor, action, headers)
    assert response.status_code == expected
    if rejection == "stale":
        assert response.json()["detail"]["code"] == "stale_revision"
    elif rejection == "ai-seat":
        assert response.json()["detail"]["code"] == "ai_controlled_seat"
    elif rejection != "malformed":
        assert response.json()["detail"]["code"] == "illegal_action"
    assert stable(api, controller) == before


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("failure", ["snapshot-after-flush", "commit-after-flush"])
def test_battle_write_failure_rolls_back_action_revision_receipt_and_sqlite(
        seam_api, monkeypatch, seat, stage, failure):
    api = seam_api
    controller, action = prepare_stage(api, seat, stage)
    before = stable(api, controller)
    attempted = []
    save = Repository.save_active_match

    def fail_save(repo, *args, **kwargs):
        save(repo, *args, **kwargs)
        attempted.append("snapshot-after-flush")
        raise OperationalError("injected Battle snapshot failure", {}, Exception("test"))

    def fail_commit(session):
        session.flush()
        attempted.append("commit-after-flush")
        raise OperationalError("injected Battle commit failure", {}, Exception("test"))

    with monkeypatch.context() as patch:
        if failure == "snapshot-after-flush":
            patch.setattr(Repository, "save_active_match", fail_save)
        else:
            patch.setattr(Session, "commit", fail_commit)
        response = action_request(api, controller, seat, action)
    assert attempted == [failure]
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "match_storage_unavailable"
    assert stable(api, controller) == before
    # The rolled-back key must remain usable: one fresh durable application.
    accept(api, controller, seat, action)


@pytest.mark.parametrize("seat", [1, 2])
@pytest.mark.parametrize("stage", STAGES)
def test_battle_lost_response_retry_survives_sqlite_reload_without_reapplication(
        seam_api, seat, stage):
    api = seam_api
    controller, action = prepare_stage(api, seat, stage)
    revision = controller.revision
    headers = write_headers(controller, key="lost-battle-response")
    assert action_request(api, controller, seat, action, headers).status_code == 200
    assert controller.revision == revision + 1
    committed = stable(api, controller)
    # Discard the accepted response; the client reconciles with authoritative GET.
    match_id = controller.state.id
    api.main.ACTIVE_MATCHES.pop(match_id)
    refreshed = api.client.get(f"/matches/{match_id}")
    assert refreshed.status_code == 200
    restored = api.main.ACTIVE_MATCHES[match_id]
    assert refreshed.json()["revision"] == revision + 1
    assert stable(api, restored) == committed
    retry = action_request(api, restored, seat, action, headers)
    assert retry.status_code == 200 and retry.json()["revision"] == revision + 1
    assert stable(api, restored) == committed
    conflict = action_request(api, restored, seat, {"type": "pass_priority"}, headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert stable(api, restored) == committed
