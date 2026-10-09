"""Public native fixture composition; no ambient database may be opened."""
from pathlib import Path
import threading

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

import main
from persistence import db, capacity
from persistence.repository import Repository
from tests.temporary_characteristics_http_fixture import source_default_identity
from tests.test_simulation_admission import _isolated_simulation_state


@pytest.fixture
def ambient_simulation_state(monkeypatch):
    state = {
        'SIM_JOBS': {'public-preserved-job': {'status': 'completed'}},
        'SIM_JOB_CANCEL_EVENTS': {'public-preserved-job': threading.Event()},
        'SIM_JOB_WORKERS': {},
        'SIM_WORK_SLOT': threading.BoundedSemaphore(1),
        'SIM_SHUTTING_DOWN': False,
    }
    for name, value in state.items():
        monkeypatch.setattr(main, name, value)
    return state


def assert_ambient_simulation_state(state):
    for name, value in state.items():
        assert getattr(main, name) is value
    assert state['SIM_JOBS'] == {'public-preserved-job': {'status': 'completed'}}
    assert list(state['SIM_JOB_CANCEL_EVENTS']) == ['public-preserved-job']
    assert not state['SIM_JOB_CANCEL_EVENTS']['public-preserved-job'].is_set()
    assert not state['SIM_JOB_WORKERS']


def test_earlier_genuine_native_lifespan_closes_before_admission_module(
        tmp_path_factory, monkeypatch, ambient_simulation_state):
    folder = tmp_path_factory.mktemp('prior-native')
    engine = create_engine('sqlite:///' + str(folder / 'admission.sqlite3'))
    original_main, original_db = main.engine, db.engine
    source_default = Path(__file__).resolve().parents[1] / 'mtg_lab.db'
    before = source_default_identity()
    owner = None
    def offline_catalog(repo):
        assert isinstance(repo, Repository) and repo.session.get_bind() is engine
    with _isolated_simulation_state() as context:
        context.setattr(main, 'engine', engine)
        context.setattr(db, 'engine', engine)
        # Only catalog/sync bootstrap is omitted; the native lifespan is real.
        context.setattr(main, '_ensure_builtin_decks', offline_catalog)
        context.setattr(main, '_ensure_expansion_top_decks', offline_catalog)
        with TestClient(main.app) as client:
            assert client.get('/health').json() == {'ok': True}
            owner = capacity.owner_for_engine(engine)
            assert owner.ready and owner.admissions_open and owner.fd is not None
            assert owner.path == folder / 'admission.sqlite3'
        assert not owner.producers and owner.fd is None
        assert engine.pool.checkedout() == 0
        assert engine not in capacity._OWNERS
    assert main.engine is original_main and db.engine is original_db
    assert source_default_identity() == before
    assert_ambient_simulation_state(ambient_simulation_state)


def test_owned_storage_preserves_ambient_files_and_restores_both_engine_aliases(tmp_path_factory):
    from tests.test_simulation_admission import _owned_admission_engine
    source_default = Path(__file__).resolve().parents[1] / 'mtg_lab.db'
    before = source_default_identity()
    original_main, original_db = main.engine, db.engine
    with _owned_admission_engine(tmp_path_factory, 'composition-probe') as owner:
        assert main.engine is db.engine is owner.engine
        assert owner.path.is_relative_to(tmp_path_factory.getbasetemp())
        assert owner.path != source_default
        with Session(main.engine) as session:
            row = Repository(session).save_simulation_job({
                'job_id': 'public-native-composition-probe', 'status': 'completed',
                'completed_matches': 1, 'total_matches': 1, 'started_at': 1,
                'finished_at': 2, 'error': None, 'request': {'public': True},
                'result': {'ok': True},
            })
            assert row.status == 'completed' and row.result_json == '{"ok": true}'
        assert source_default_identity() == before
    assert main.engine is original_main and db.engine is original_db
    assert source_default_identity() == before
    assert owner.fd is None and not owner.producers
    assert owner.engine not in capacity._OWNERS


def test_owned_native_shutdown_restores_ambient_simulation_state(
        tmp_path_factory, ambient_simulation_state):
    from tests.test_simulation_admission import _owned_admission_engine
    with _owned_admission_engine(tmp_path_factory, 'shutdown-probe') as owner:
        main._shutdown_simulation_workers()
        assert main.SIM_SHUTTING_DOWN is True
    assert owner.fd is None and not owner.producers
    assert_ambient_simulation_state(ambient_simulation_state)


def test_failed_shutdown_retains_owned_bindings_until_worker_stops(
        tmp_path_factory, ambient_simulation_state, monkeypatch):
    from tests.test_simulation_admission import _owned_admission_engine
    original_main, original_db = main.engine, db.engine
    release = threading.Event()
    worker = threading.Thread(target=release.wait, daemon=True)
    owned = None
    original_shutdown = main._shutdown_simulation_workers
    try:
        with pytest.raises(RuntimeError, match='owned shutdown timeout'):
            with _owned_admission_engine(tmp_path_factory, 'failed-shutdown') as owner:
                owned = owner
                worker.start()
                main.SIM_JOB_WORKERS['public-owned-worker'] = (worker, release)

                def timeout():
                    main.SIM_SHUTTING_DOWN = True
                    raise RuntimeError('owned shutdown timeout')

                monkeypatch.setattr(main, '_shutdown_simulation_workers', timeout)
        assert worker.is_alive()
        assert main.engine is db.engine is owned.engine
        assert main.SIM_JOB_WORKERS['public-owned-worker'][0] is worker
        assert main.SIM_SHUTTING_DOWN is True
        assert owned.fd is not None
        assert capacity.owner_for_engine(owned.engine) is owned
        assert not owned.admissions_open
        with pytest.raises(capacity.CapacityAdmissionClosed):
            with owned.activity():
                pytest.fail('Timed-out ownership admitted another producer')
    finally:
        release.set()
        if worker.ident is not None:
            worker.join(timeout=2)
        assert not worker.is_alive()
        if main.SIM_JOB_WORKERS is not ambient_simulation_state['SIM_JOB_WORKERS']:
            main.SIM_JOB_WORKERS.clear()
        if owned is not None and owned.fd is not None:
            owned.drain_producers(timeout=2)
            owned.close()
        for name, value in ambient_simulation_state.items():
            setattr(main, name, value)
        main.engine, db.engine = original_main, original_db
        monkeypatch.setattr(main, '_shutdown_simulation_workers', original_shutdown)
    assert_ambient_simulation_state(ambient_simulation_state)
