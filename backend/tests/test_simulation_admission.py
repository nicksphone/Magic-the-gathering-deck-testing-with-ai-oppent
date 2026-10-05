"""Batch admission uses one shared slot for synchronous and job routes."""

import pytest
import threading
import time
import json
from types import SimpleNamespace
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import main
from analytics.schemas import BatchSimulationRequest
from analytics.service import AnalyticsService, SimulationCancelled
from persistence.repository import Repository


class AdmissionRepo:
    def count_simulation_jobs(self):
        return 0


def _request() -> BatchSimulationRequest:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    return BatchSimulationRequest(deck_a=deck, deck_b=deck, matches=1)


def test_second_batch_job_and_sync_batch_are_rejected_while_slot_is_held(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, "_persist_job", lambda _job: None)

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    job_id = None
    try:
        started = main.simulate_batch_start(_request(), repo=AdmissionRepo())
        job_id = started["job_id"]
        assert started["status"] == "queued"
        for route in (main.simulate_batch_start, main.simulate_batch):
            with pytest.raises(HTTPException) as raised:
                route(_request(), repo=AdmissionRepo())
            assert raised.value.status_code == 429
            assert raised.value.detail["code"] == "simulation_busy"
    finally:
        if job_id:
            main.SIM_JOBS.pop(job_id, None)
            main.SIM_WORK_SLOT.release()


def test_failed_job_admission_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)

    def fail(_job):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(main, "_persist_job", fail)
    before = set(main.SIM_JOBS)
    with pytest.raises(RuntimeError, match="storage unavailable"):
        main.simulate_batch_start(_request(), repo=AdmissionRepo())
    assert set(main.SIM_JOBS) == before
    assert main.SIM_WORK_SLOT.acquire(blocking=False)
    main.SIM_WORK_SLOT.release()


def test_sync_batch_exception_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)

    def fail(*_args, **_kwargs):
        raise RuntimeError("simulation failed")

    monkeypatch.setattr(main.AnalyticsService, "run_batch", fail)
    with pytest.raises(RuntimeError, match="simulation failed"):
        main.simulate_batch(_request(), repo=object())
    assert main.SIM_WORK_SLOT.acquire(blocking=False)
    main.SIM_WORK_SLOT.release()


def test_cancel_job_stops_worker_and_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, "_persist_job", lambda _job: None)
    entered = threading.Event()

    def run_until_cancelled(_self, *_args, should_cancel=None, **_kwargs):
        entered.set()
        while not should_cancel():
            time.sleep(0.001)
        raise SimulationCancelled()

    monkeypatch.setattr(AnalyticsService, "run_batch", run_until_cancelled)
    started = main.simulate_batch_start(_request(), repo=AdmissionRepo())
    job_id = started["job_id"]
    try:
        assert entered.wait(2)
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] == "running"
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] in {"running", "canceled"}
        for _ in range(200):
            if main.SIM_JOBS[job_id]["status"] == "canceled":
                break
            time.sleep(0.01)
        assert main.SIM_JOBS[job_id]["status"] == "canceled"
        assert main.SIM_JOBS[job_id]["completed_matches"] == 0
        assert main.SIM_JOBS[job_id]["result"] is None
        assert job_id not in main.SIM_JOB_CANCEL_EVENTS
        assert main.SIM_WORK_SLOT.acquire(blocking=False)
        main.SIM_WORK_SLOT.release()
    finally:
        main.SIM_JOBS.pop(job_id, None)


def test_batch_checks_cancel_during_game():
    service = AnalyticsService(repo=object())
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    with pytest.raises(SimulationCancelled):
        service.run_batch(deck, deck, matches=1, should_cancel=lambda: True)


def test_cancel_queued_job_is_idempotent_and_unknown_job_is_404(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, "_persist_job", lambda _job: None)

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    job_id = main.simulate_batch_start(_request(), repo=AdmissionRepo())["job_id"]
    try:
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] == "queued"
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] == "queued"
        assert main.SIM_JOB_CANCEL_EVENTS[job_id].is_set()
    finally:
        main.SIM_JOBS.pop(job_id, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(job_id, None)
        main.SIM_WORK_SLOT.release()

    class EmptyRepo:
        def get_simulation_job(self, _job_id):
            return None

    with pytest.raises(HTTPException) as raised:
        main.simulate_batch_cancel("missing", repo=EmptyRepo())
    assert raised.value.status_code == 404


def test_cancel_http_route_sets_worker_signal():
    job_id = "http-cancel-fixture"
    event = threading.Event()
    main.SIM_JOBS[job_id] = {
        "job_id": job_id, "status": "running", "completed_matches": 2,
        "total_matches": 10, "started_at": time.time(), "finished_at": None,
        "error": None, "result": None,
    }
    main.SIM_JOB_CANCEL_EVENTS[job_id] = event
    main.app.dependency_overrides[main.get_repo] = lambda: object()
    try:
        response = TestClient(main.app).post(f"/simulate/batch/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["completed_matches"] == 2
        assert event.is_set()
    finally:
        main.app.dependency_overrides.pop(main.get_repo, None)
        main.SIM_JOBS.pop(job_id, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(job_id, None)


def test_batch_start_key_replays_without_second_worker_and_rejects_conflict(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, "_persist_job", lambda _job: None)

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    class EmptyRepo(AdmissionRepo):
        def get_simulation_job(self, _job_id):
            return None

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    key = "a" * 32
    repo = EmptyRepo()
    try:
        started = main.simulate_batch_start(_request(), repo=repo, idempotency_key=key)
        assert started == {"job_id": key, "status": "queued"}
        assert main.simulate_batch_start(_request(), repo=repo, idempotency_key=key) == started
        with pytest.raises(HTTPException) as conflict:
            main.simulate_batch_start(_request().model_copy(update={"matches": 2}), repo=repo, idempotency_key=key)
        assert conflict.value.status_code == 409
        with pytest.raises(HTTPException) as busy:
            main.simulate_batch_start(_request(), repo=repo, idempotency_key="b" * 32)
        assert busy.value.status_code == 429
    finally:
        main.SIM_JOBS.pop(key, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(key, None)
        main.SIM_WORK_SLOT.release()


def test_batch_start_key_recovers_persisted_job_after_restart():
    request = _request()
    key = "c" * 32
    row = SimpleNamespace(status="completed", request_json=json.dumps(request.model_dump(mode="json")))

    class SavedRepo:
        def get_simulation_job(self, job_id):
            return row if job_id == key else None

    assert main.simulate_batch_start(request, repo=SavedRepo(), idempotency_key=key) == {"job_id": key, "status": "completed"}
    with pytest.raises(HTTPException) as invalid:
        main.simulate_batch_start(request, repo=SavedRepo(), idempotency_key="bad")
    assert invalid.value.status_code == 422


def test_batch_start_http_idempotency_header(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, "_persist_job", lambda _job: None)

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    class EmptyRepo(AdmissionRepo):
        def get_simulation_job(self, _job_id):
            return None

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    main.app.dependency_overrides[main.get_repo] = lambda: EmptyRepo()
    key = "d" * 32
    try:
        client = TestClient(main.app)
        payload = _request().model_dump(mode="json")
        headers = {"Idempotency-Key": key}
        first = client.post("/simulate/batch/start", json=payload, headers=headers)
        assert first.status_code == 200
        assert first.json() == {"job_id": key, "status": "queued"}
        assert client.post("/simulate/batch/start", json=payload, headers=headers).json() == first.json()
        assert client.post("/simulate/batch/start", json={**payload, "matches": 2}, headers=headers).status_code == 409
        assert client.post("/simulate/batch/start", json=payload, headers={"Idempotency-Key": "invalid"}).status_code == 422
    finally:
        main.app.dependency_overrides.pop(main.get_repo, None)
        main.SIM_JOBS.pop(key, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(key, None)
        main.SIM_WORK_SLOT.release()


def test_batch_start_key_replays_from_sqlite_after_process_memory_is_cleared(monkeypatch):
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    key = "e" * 32
    try:
        with Session(test_engine) as session:
            repo = Repository(session)
            first = main.simulate_batch_start(_request(), repo=repo, idempotency_key=key)
            assert repo.get_simulation_job(key) is not None
            main.SIM_JOBS.pop(key, None)
            main.SIM_JOB_CANCEL_EVENTS.pop(key, None)
            assert main.simulate_batch_start(_request(), repo=repo, idempotency_key=key) == first
            with pytest.raises(HTTPException) as conflict:
                main.simulate_batch_start(_request().model_copy(update={"matches": 2}), repo=repo, idempotency_key=key)
            assert conflict.value.status_code == 409
    finally:
        main.SIM_JOBS.pop(key, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(key, None)
        main.SIM_WORK_SLOT.release()


def test_worker_start_failure_persists_failed_job_and_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    saved = []
    monkeypatch.setattr(main, "_persist_job", lambda job: saved.append(dict(job)))

    class BrokenThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("thread unavailable")

    monkeypatch.setattr(main.threading, "Thread", BrokenThread)
    key = "f" * 32

    class EmptyRepo(AdmissionRepo):
        def get_simulation_job(self, _job_id):
            return None

    with pytest.raises(RuntimeError, match="thread unavailable"):
        main.simulate_batch_start(_request(), repo=EmptyRepo(), idempotency_key=key)
    assert [row["status"] for row in saved] == ["queued", "failed"]
    assert saved[-1]["error"] == "Simulation worker could not start."
    assert key not in main.SIM_JOBS
    assert key not in main.SIM_JOB_CANCEL_EVENTS
    assert main.SIM_WORK_SLOT.acquire(blocking=False)
    main.SIM_WORK_SLOT.release()
