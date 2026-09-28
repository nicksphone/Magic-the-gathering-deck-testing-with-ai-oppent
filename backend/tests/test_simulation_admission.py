"""Batch admission uses one shared slot for synchronous and job routes."""

import pytest
from fastapi import HTTPException

import main
from analytics.schemas import BatchSimulationRequest


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
