"""Batch admission uses one shared slot for synchronous and job routes."""

import pytest
import threading
import time
import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

import main
from analytics.schemas import BatchSimulationRequest
from analytics.service import AnalyticsService, SimulationCancelled
from persistence.repository import Repository
from persistence.capacity import DatabaseOwner
from persistence.models import ResourceReservation
from persistence import capacity, db


_admission_session = None


class AdmissionRepo(Repository):
    def __init__(self):
        assert _admission_session is not None
        super().__init__(_admission_session)


class DormantThread:
    """Park the real runner until cancellation; never simulate in this double."""
    def __init__(self, *, target, daemon):
        assert callable(target) and target.__name__ == '_runner' and daemon is True
        self.target = target
        self.started = False

    def start(self):
        assert not self.started
        self.started = True

    def is_alive(self):
        return self.started

    def join(self, timeout=None):
        assert timeout is None or timeout >= 0
        if self.started:
            assert all(event.is_set() for _thread, event in main.SIM_JOB_WORKERS.values())
            self.target()
            self.started = False


def _finish_dormant_job(job_id):
    thread, event = main.SIM_JOB_WORKERS.pop(job_id)
    event.set()
    assert isinstance(thread, DormantThread)
    # The join contract checks all registered signals, including this one.
    main.SIM_JOB_WORKERS[job_id] = (thread, event)
    thread.join()
    assert not thread.is_alive()
    main.SIM_JOB_WORKERS.pop(job_id)
    main.SIM_JOBS.pop(job_id, None)
    main.SIM_JOB_CANCEL_EVENTS.pop(job_id, None)


def _cancel_unfinished(engine):
    with Session(engine) as session:
        repo = Repository(session)
        for row in repo.list_unfinished_simulation_jobs():
            repo.save_simulation_job({**main._job_dict(row), 'status': 'canceled',
                                      'request': json.loads(row.request_json),
                                      'finished_at': time.time(), 'error': None, 'result': None})
        assert session.exec(select(ResourceReservation)).all() == []


@contextmanager
def _isolated_simulation_state():
    assert not main.SIM_JOB_WORKERS
    assert not any(owner.producers for owner in capacity._OWNERS.values())
    previous_owners = set(capacity._OWNERS)
    context = pytest.MonkeyPatch()
    for name in ('SIM_JOBS', 'SIM_JOB_CANCEL_EVENTS', 'SIM_JOB_WORKERS'):
        context.setattr(main, name, {})
    context.setattr(main, 'SIM_WORK_SLOT', threading.BoundedSemaphore(1))
    context.setattr(main, 'SIM_SHUTTING_DOWN', False)
    try:
        yield context
    finally:
        if (main.SIM_JOB_WORKERS or set(capacity._OWNERS) - previous_owners
                or any(owner.producers for owner in capacity._OWNERS.values())):
            # A failed teardown must not redirect surviving work to ambient state.
            main.SIM_SHUTTING_DOWN = True
        else:
            context.undo()
    assert not main.SIM_JOB_WORKERS
    assert not set(capacity._OWNERS) - previous_owners
    assert not any(owner.producers for owner in capacity._OWNERS.values())


@contextmanager
def _owned_admission_engine(tmp_path_factory, label):
    root = Path(__file__).resolve().parents[2]
    assert os.environ['MTG_ISOLATED_TEST_ROOT'] == str(root)
    assert not (root / '.git').exists()
    for marker in ('.private', '.private-choice-audit-source'):
        assert (root / marker).read_text() == str(root)
    folder = tmp_path_factory.mktemp(label)
    backup = folder / 'backup'
    backup.mkdir()
    test_engine = create_engine('sqlite:///' + str(folder / 'admission.sqlite3'))
    with _isolated_simulation_state() as context:
        context.setattr(main, 'engine', test_engine)
        context.setattr(db, 'engine', test_engine)
        owner = DatabaseOwner(test_engine).acquire()
        try:
            db.init_db()
            db.initialize_resource_capacity(owner, backup / 'before.db')
            owner.open_admission()
            yield owner
        finally:
            owner.fence_admission()
            main._shutdown_simulation_workers()
            owner.drain_producers(timeout=2)
            owner.close()
            assert owner.fd is None and not owner.producers


@pytest.fixture(scope='module')
def owned_admission_storage(tmp_path_factory):
    with _owned_admission_engine(tmp_path_factory, 'admission-module') as owner:
        yield owner


@pytest.fixture(autouse=True)
def admission_state(owned_admission_storage):
    global _admission_session
    assert not main.SIM_JOB_WORKERS and not owned_admission_storage.producers
    with _isolated_simulation_state():
        with Session(main.engine) as session:
            _admission_session = session
            try:
                yield
            finally:
                try:
                    main._shutdown_simulation_workers()
                    _cancel_unfinished(main.engine)
                finally:
                    _admission_session = None
        assert not main.SIM_JOB_WORKERS and not main.SIM_JOB_CANCEL_EVENTS
        assert not owned_admission_storage.producers
        assert main.SIM_WORK_SLOT.acquire(blocking=False)
        main.SIM_WORK_SLOT.release()


@pytest.fixture
def admission_replay_engine(admission_state, tmp_path_factory):
    with _owned_admission_engine(tmp_path_factory, 'admission-replay') as owner:
        try:
            yield owner.engine
        finally:
            _cancel_unfinished(owner.engine)


def _request() -> BatchSimulationRequest:
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    return BatchSimulationRequest(deck_a=deck, deck_b=deck, matches=1)


def test_second_batch_job_and_sync_batch_are_rejected_while_slot_is_held(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=DormantThread,
                        Event=threading.Event, current_thread=threading.current_thread))
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
            _finish_dormant_job(job_id)


def test_failed_job_admission_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)

    def fail(_self, _job):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(Repository, "save_simulation_job", fail)
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
    entered = threading.Event()

    def run_until_cancelled(_self, deck_a, deck_b, matches, difficulty, *, max_ticks,
                            progress_callback, should_cancel, reservation_token):
        assert deck_a == deck_b == _request().deck_a
        assert (matches, difficulty, max_ticks) == (1, 'master', 6000)
        assert _self.repo.session.get_bind() is main.engine
        _self.repo.validate_snapshot_reservation(reservation_token)
        progress_callback(0, matches)
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
    service = AnalyticsService(repo=AdmissionRepo())
    deck = [{"quantity": 60, "card_name": "Mountain"}]
    with pytest.raises(SimulationCancelled):
        service.run_batch(deck, deck, matches=1, should_cancel=lambda: True)


def test_cancel_queued_job_is_idempotent_and_unknown_job_is_404(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=DormantThread,
                        Event=threading.Event, current_thread=threading.current_thread))
    job_id = main.simulate_batch_start(_request(), repo=AdmissionRepo())["job_id"]
    try:
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] == "queued"
        assert main.simulate_batch_cancel(job_id, repo=object())["status"] == "queued"
        assert main.SIM_JOB_CANCEL_EVENTS[job_id].is_set()
    finally:
        _finish_dormant_job(job_id)

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
        client = TestClient(main.app)
        response = client.post(f"/simulate/batch/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["completed_matches"] == 2
        assert event.is_set()
    finally:
        client.close()
        main.app.dependency_overrides.pop(main.get_repo, None)
        main.SIM_JOBS.pop(job_id, None)
        main.SIM_JOB_CANCEL_EVENTS.pop(job_id, None)


def test_batch_start_key_replays_without_second_worker_and_rejects_conflict(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    class EmptyRepo(AdmissionRepo):
        def get_simulation_job(self, _job_id):
            return None

    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=DormantThread,
                        Event=threading.Event, current_thread=threading.current_thread))
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
        _finish_dormant_job(key)


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
    class EmptyRepo(AdmissionRepo):
        def get_simulation_job(self, _job_id):
            return None

    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=DormantThread,
                        Event=threading.Event, current_thread=threading.current_thread))
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
        client.close()
        main.app.dependency_overrides.pop(main.get_repo, None)
        _finish_dormant_job(key)


def test_batch_start_key_replays_from_sqlite_after_process_memory_is_cleared(monkeypatch, admission_replay_engine):
    test_engine = admission_replay_engine
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)

    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=DormantThread,
                        Event=threading.Event, current_thread=threading.current_thread))
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
        _finish_dormant_job(key)


def test_worker_start_failure_persists_failed_job_and_releases_slot(monkeypatch):
    monkeypatch.setattr(main, "_validated_deck_cards", lambda _repo, cards: cards)
    saved = []
    original_save = Repository.save_simulation_job
    def record_save(repo, job):
        row = original_save(repo, job)
        saved.append(dict(job))
        return row
    monkeypatch.setattr(Repository, "save_simulation_job", record_save)

    class BrokenThread:
        def __init__(self, *, target, daemon):
            assert callable(target) and target.__name__ == '_runner' and daemon is True

        def start(self):
            raise RuntimeError("thread unavailable")

    monkeypatch.setattr(main, 'threading', SimpleNamespace(Thread=BrokenThread,
                        Event=threading.Event, current_thread=threading.current_thread))
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
