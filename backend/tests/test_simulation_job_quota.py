"""Job admission quota on isolated SQLite only; no simulation workers execute."""

import threading

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import main
from analytics.schemas import BatchSimulationRequest
from persistence.models import SimulationJobRecord
from persistence.repository import Repository


REAL_THREAD = threading.Thread


def test_default_row_limit_is_conservative_and_positive():
    assert main.SIM_JOBS_ROW_LIMIT == 10000


def request():
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    return BatchSimulationRequest(deck_a=deck, deck_b=deck, matches=1)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'quota.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SIM_JOBS", {})
    monkeypatch.setattr(main, "SIM_JOB_CANCEL_EVENTS", {})
    monkeypatch.setattr(main, "SIM_START_LOCK", threading.Lock())
    monkeypatch.setattr(main, "SIM_WORK_SLOT", threading.BoundedSemaphore(1))
    monkeypatch.setattr(main, "SIM_JOBS_ROW_LIMIT", 2)
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    starts = []

    class DormantThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            starts.append(True)

    monkeypatch.setattr(main.threading, "Thread", DormantThread)
    try:
        yield engine, starts
    finally:
        engine.dispose()


def seed(repo, job_id, status="completed"):
    repo.save_simulation_job({
        "job_id": job_id, "status": status, "started_at": 1.0,
        "finished_at": 2.0 if status in {"completed", "failed", "canceled"} else None,
        "request": request().model_dump(mode="json"), "result": {"matches": 1},
    })


def snapshot(repo):
    return [row.model_dump() for row in repo.session.exec(
        select(SimulationJobRecord).order_by(SimulationJobRecord.id)
    ).all()]


def assert_slot_available():
    assert main.SIM_WORK_SLOT.acquire(blocking=False)
    main.SIM_WORK_SLOT.release()


@pytest.mark.parametrize("key", [None, "a" * 32])
def test_one_below_limit_admits_once_then_rejects_without_side_effects(isolated, key):
    engine, starts = isolated
    with Session(engine) as session:
        repo = Repository(session)
        seed(repo, "old")
        accepted = main.simulate_batch_start(request(), repo=repo, idempotency_key=key)
        assert repo.count_simulation_jobs() == 2
        assert accepted["status"] == "queued"
        before = snapshot(repo)
        jobs = dict(main.SIM_JOBS)
        events = dict(main.SIM_JOB_CANCEL_EVENTS)
        for next_key in (None, "b" * 32):
            with pytest.raises(HTTPException) as rejected:
                main.simulate_batch_start(request(), repo=repo, idempotency_key=next_key)
            assert rejected.value.status_code == 429
            assert rejected.value.detail["code"] == "simulation_job_quota_exceeded"
            assert rejected.value.detail["limit"] == 2
        assert snapshot(repo) == before
        assert main.SIM_JOBS == jobs
        assert main.SIM_JOB_CANCEL_EVENTS == events
        assert len(starts) == 1


@pytest.mark.parametrize("cache_present", [False, True])
def test_replay_and_conflict_precede_quota_even_when_slot_held(isolated, monkeypatch, cache_present):
    engine, starts = isolated
    key = "c" * 32
    with Session(engine) as session:
        repo = Repository(session)
        seed(repo, key)
        seed(repo, "other")
        if cache_present:
            row = repo.get_simulation_job(key)
            main.SIM_JOBS[key] = {**main._job_dict(row), "request": request().model_dump(mode="json")}
        before = snapshot(repo)

        def must_not_count():
            pytest.fail("existing-key replay/conflict must bypass quota")

        monkeypatch.setattr(repo, "count_simulation_jobs", must_not_count)
        assert main.SIM_WORK_SLOT.acquire(blocking=False)
        try:
            assert main.simulate_batch_start(request(), repo=repo, idempotency_key=key) == {
                "job_id": key, "status": "completed",
            }
            with pytest.raises(HTTPException) as conflict:
                main.simulate_batch_start(request().model_copy(update={"matches": 2}), repo=repo, idempotency_key=key)
            assert conflict.value.status_code == 409
            assert conflict.value.detail["code"] == "idempotency_conflict"
        finally:
            main.SIM_WORK_SLOT.release()
        assert snapshot(repo) == before
        assert not starts


@pytest.mark.parametrize("status", ["queued", "running", "completed", "failed", "canceled", "unknown"])
def test_all_statuses_count_and_over_limit_preserves_existing_rows(isolated, monkeypatch, status):
    engine, starts = isolated
    monkeypatch.setattr(main, "SIM_JOBS_ROW_LIMIT", 1)
    with Session(engine) as session:
        repo = Repository(session)
        assert repo.count_simulation_jobs() == 0
        seed(repo, "old", status)
        seed(repo, "extra", status)
        assert repo.count_simulation_jobs() == 2
        before = snapshot(repo)
        with pytest.raises(HTTPException) as rejected:
            main.simulate_batch_start(request(), repo=repo)
        assert rejected.value.detail["code"] == "simulation_job_quota_exceeded"
        assert snapshot(repo) == before
        assert not main.SIM_JOBS and not main.SIM_JOB_CANCEL_EVENTS and not starts
        assert_slot_available()


def test_count_uses_scalar_query_without_loading_json(isolated):
    engine, _ = isolated
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO simulationjobrecord (id, status, completed_matches, total_matches, started_at, request_json, result_json) "
            "VALUES ('invalid-json', 'unknown', 0, 0, 0, 'not json', 'not json')"
        )
    with Session(engine) as session:
        assert Repository(session).count_simulation_jobs() == 1
        assert not session.identity_map


def test_count_failure_leaves_admission_state_and_slot_untouched(isolated):
    _, starts = isolated

    class BrokenRepo:
        def count_simulation_jobs(self):
            raise RuntimeError("count unavailable")

    with pytest.raises(RuntimeError, match="count unavailable"):
        main.simulate_batch_start(request(), repo=BrokenRepo())
    assert not main.SIM_JOBS and not main.SIM_JOB_CANCEL_EVENTS and not starts
    assert_slot_available()


def test_full_quota_precedes_validation_and_preserves_active_cancel_updates(isolated, monkeypatch):
    engine, starts = isolated
    with Session(engine) as session:
        repo = Repository(session)
        seed(repo, "old")
        accepted = main.simulate_batch_start(request(), repo=repo)
        job_id = accepted["job_id"]
        event = main.SIM_JOB_CANCEL_EVENTS[job_id]

        def must_not_validate(*_args):
            pytest.fail("quota rejection must precede deck validation")

        monkeypatch.setattr(main, "_validated_deck_cards", must_not_validate)
        with pytest.raises(HTTPException) as rejected:
            main.simulate_batch_start(request(), repo=repo)
        assert rejected.value.detail["code"] == "simulation_job_quota_exceeded"
        assert main.simulate_batch_cancel(job_id, repo=repo)["status"] == "queued"
        assert event.is_set()
        updated = {**main.SIM_JOBS[job_id], "status": "canceled", "finished_at": 3.0}
        main._persist_job(updated)
        assert repo.count_simulation_jobs() == 2
        session.expire_all()
        assert repo.get_simulation_job(job_id).status == "canceled"
        assert len(starts) == 1


def test_concurrent_new_keys_cannot_cross_row_limit(isolated, monkeypatch):
    engine, starts = isolated
    monkeypatch.setattr(main, "SIM_JOBS_ROW_LIMIT", 1)
    barrier = threading.Barrier(2)
    outcomes = []

    def start(key):
        try:
            with Session(engine) as session:
                barrier.wait(timeout=5)
                outcomes.append(main.simulate_batch_start(request(), repo=Repository(session), idempotency_key=key))
        except Exception as exc:
            outcomes.append(exc)

    threads = [REAL_THREAD(target=start, args=(char * 32,)) for char in ("d", "e")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    accepted = [value for value in outcomes if isinstance(value, dict)]
    rejected = [value for value in outcomes if isinstance(value, HTTPException)]
    assert len(outcomes) == 2 and len(accepted) == 1 and len(rejected) == 1
    assert rejected[0].status_code == 429
    assert rejected[0].detail["code"] == "simulation_job_quota_exceeded"
    with Session(engine) as session:
        assert Repository(session).count_simulation_jobs() == 1
    assert len(starts) == 1


def test_http_quota_response_and_existing_status_cancel_remain_available(isolated):
    engine, starts = isolated
    with Session(engine) as session:
        repo = Repository(session)
        seed(repo, "old")
        seed(repo, "other")
        before = snapshot(repo)
        original_overrides = dict(main.app.dependency_overrides)
        main.app.dependency_overrides[main.get_repo] = lambda: repo
        try:
            client = TestClient(main.app)
            rejected = client.post("/simulate/batch/start", json=request().model_dump(mode="json"))
            assert rejected.status_code == 429
            assert rejected.json()["detail"]["code"] == "simulation_job_quota_exceeded"
            assert client.get("/simulate/batch/old").json()["status"] == "completed"
            assert client.post("/simulate/batch/old/cancel").json()["status"] == "completed"
        finally:
            main.app.dependency_overrides.clear()
            main.app.dependency_overrides.update(original_overrides)
        assert snapshot(repo) == before and not starts
        assert_slot_available()
