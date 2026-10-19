"""Fake commit protocol and ordinary files ONLY, never native SQLite proof."""
from contextlib import nullcontext
import os
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import create_engine

import persistence.capacity as capacity


@pytest.mark.parametrize('failure', [RuntimeError, SQLAlchemyError])
@pytest.mark.parametrize('rollback_fails', [False, True])
def test_fake_postcommit_raise_fences_and_preserves_original(monkeypatch, failure, rollback_fails):
    original = failure('fake postcommit acknowledgment failure')
    state = {'durable': False}
    owner = SimpleNamespace(path=Path('/fake-commit.txt'), mutex=threading.RLock(),
        require=lambda: None, admissions_open=True, uncertain=False, producers={})
    monkeypatch.setattr(capacity, 'owner_for', lambda session: owner)
    monkeypatch.setattr(capacity, 'CapacityTransaction', lambda *a: object())
    connection = SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(in_transaction=False)))
    connection.exec_driver_sql = lambda sql: SimpleNamespace(all=lambda: [(0, 'main', str(owner.path))])
    def commit():
        state['durable'] = True
        raise original
    def rollback():
        assert not owner.admissions_open and owner.uncertain
        if rollback_fails:
            raise RuntimeError('fake rollback failure must not replace original')
    session = SimpleNamespace(new=[], dirty=[], deleted=[], connection=lambda: connection,
        no_autoflush=nullcontext(), commit=commit, rollback=rollback)
    with pytest.raises(failure) as caught:
        with capacity.capacity_transaction(session):
            pass
    assert caught.value is original
    assert state['durable'] and owner.uncertain and not owner.admissions_open


def test_generic_uncertain_snapshot_failure_does_not_compensate():
    import ast
    from contextlib import contextmanager
    path = Path(__file__).resolve().parents[1] / 'analytics/service.py'
    node = next(n for n in ast.walk(ast.parse(path.read_text()))
                if isinstance(n, ast.FunctionDef) and n.name == '_snapshot_producer')
    owner = SimpleNamespace(uncertain=False)
    @contextmanager
    def activity():
        yield threading.Event()
    owner.activity = activity
    calls = []
    repo = SimpleNamespace(session=object(), reserve_snapshot=lambda: 'token',
        validate_snapshot_reservation=lambda token: None,
        release_snapshot_reservation=lambda token: calls.append('compensation'))
    namespace = dict(contextmanager=contextmanager, owner_for=lambda session: owner,
        SQLAlchemyError=SQLAlchemyError, CapacityIntegrityError=capacity.CapacityIntegrityError)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    original = RuntimeError('fake postcommit acknowledgment failure')
    with pytest.raises(RuntimeError) as caught:
        with namespace['_snapshot_producer'](SimpleNamespace(repo=repo), None, None):
            owner.uncertain = True
            raise original
    assert caught.value is original and calls == []


@pytest.fixture
def registered_file_owner(tmp_path):
    """Real non-database files/FD, explicitly fake registration; no flock/SQL."""
    path = tmp_path / 'ordinary-not-a-database.txt'
    path.write_text('ordinary file, not SQLite')
    engine = create_engine('sqlite:///' + str(path))
    owner = capacity.DatabaseOwner(engine)
    fd = os.open(owner.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    info = os.fstat(fd)
    owner.fd, owner.identity, owner.ready = fd, (info.st_dev, info.st_ino), True
    capacity._OWNERS[engine] = owner
    try:
        yield owner
    finally:
        capacity._OWNERS.pop(engine, None)
        os.close(fd)
        engine.dispose()


def test_fake_registered_regular_file_require_passes(registered_file_owner):
    registered_file_owner.require()


def test_same_path_regular_replacement_is_rejected(registered_file_owner):
    owner = registered_file_owner
    replacement = owner.path.with_name('replacement.txt')
    replacement.write_text('different inode')
    os.replace(replacement, owner.path)
    with pytest.raises(capacity.CapacityIntegrityError):
        owner.require()


def test_new_hardlink_alias_is_rejected(registered_file_owner):
    owner = registered_file_owner
    os.link(owner.path, owner.path.with_name('alias.txt'))
    with pytest.raises(capacity.CapacityIntegrityError):
        owner.require()


def test_same_path_directory_is_rejected(registered_file_owner):
    owner = registered_file_owner
    owner.path.unlink()
    owner.path.mkdir()
    with pytest.raises(capacity.CapacityIntegrityError):
        owner.require()


def test_uncertain_owner_denies_even_existing_nested_producer(registered_file_owner):
    owner = registered_file_owner
    owner.admissions_open = True
    with owner.activity():
        owner.uncertain = True
        owner.admissions_open = False
        with pytest.raises(capacity.CapacityIntegrityError):
            with owner.activity():
                pass


@pytest.mark.parametrize('failure', [RuntimeError, SQLAlchemyError])
def test_known_thread_start_failure_uncertain_settlement_preserves_storage_exception(failure):
    import ast
    import __future__
    import time
    path = Path(__file__).resolve().parents[1] / 'main.py'
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in {'_start_batch_job', '_fence_uncertain_job'}]
    original = failure('fake settlement postcommit acknowledgment failure')
    calls, state = [], {'uncertain': False}
    slot, start_lock = threading.BoundedSemaphore(1), threading.Lock()
    class FailedThread:
        def __init__(self, **kw): pass
        def start(self): raise ValueError('known thread start failure')
    def settle(job):
        state['uncertain'] = True
        calls.append('settle')
        raise original
    namespace = dict(_reap_simulation_workers=lambda: None, SIM_START_LOCK=start_lock,
        SIM_JOBS_LOCK=threading.Lock(), SIM_JOBS={}, SIM_JOB_WORKERS={},
        SIM_JOB_CANCEL_EVENTS={}, SIM_SHUTTING_DOWN=False, SIM_WORK_SLOT=slot,
        SIM_JOBS_ROW_LIMIT=10000, RESOURCE_LIMITS={'request_json_bytes': 1},
        checked_json=lambda *a: None, _validated_deck_cards=lambda *a: [],
        Session=lambda engine: nullcontext(object()),
        Repository=lambda session: SimpleNamespace(save_simulation_job=lambda job: calls.append('admit'),
            background_snapshot_token=lambda job_id: 'token'),
        _persist_job=settle, owner_uncertain=lambda engine: state['uncertain'],
        owner_for_engine=lambda engine: SimpleNamespace(fence_admission=lambda: calls.append('fence')),
        engine=object(), threading=SimpleNamespace(Event=threading.Event, Thread=FailedThread),
        time=time, nullcontext=nullcontext, SQLAlchemyError=SQLAlchemyError,
        CapacityIntegrityError=capacity.CapacityIntegrityError,
        CapacityAdmissionClosed=capacity.CapacityAdmissionClosed,
        SimulationResourceLimit=type('Limit', (Exception,), {}))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    payload = SimpleNamespace(model_dump=lambda **kw: {}, matches=1, deck_a=[], deck_b=[])
    repo = SimpleNamespace(get_simulation_job=lambda key: None, count_simulation_jobs=lambda: 0)
    with start_lock, pytest.raises(failure) as caught:
        namespace['_start_batch_job'](payload, repo, 'j')
    assert caught.value is original
    assert calls == ['admit', 'settle', 'fence'] and state['uncertain']
    assert namespace['SIM_SHUTTING_DOWN'] and not namespace['SIM_JOBS']
    assert not namespace['SIM_JOB_WORKERS'] and not namespace['SIM_JOB_CANCEL_EVENTS']
    assert slot.acquire(False)
    slot.release()
