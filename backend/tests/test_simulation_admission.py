"""Batch admission uses one shared slot for synchronous and job routes."""

import pytest
import threading
import time
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from analytics.schemas import BatchSimulationRequest
from analytics.service import AnalyticsService, SimulationCancelled


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
        started = main.simulate_batch_start(_request(), repo=object())
        job_id = started["job_id"]
        assert started["status"] == "queued"
        for route in (main.simulate_batch_start, main.simulate_batch):
            with pytest.raises(HTTPException) as raised:
                route(_request(), repo=object())
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
        main.simulate_batch_start(_request(), repo=object())
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
    started = main.simulate_batch_start(_request(), repo=object())
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
    job_id = main.simulate_batch_start(_request(), repo=object())["job_id"]
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
