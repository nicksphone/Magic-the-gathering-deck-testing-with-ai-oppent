"""Actual lifecycle/policy methods with explicitly fake owner/SQL/FD bindings."""
import ast
import asyncio
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest
import persistence.capacity as capacity


def fake_owner():
    owner = capacity.DatabaseOwner.__new__(capacity.DatabaseOwner)
    owner.mutex = threading.RLock()
    owner.local = threading.local()
    owner.admissions_open = True
    owner.producers = {}
    owner.require = lambda **kw: None
    return owner


def test_actual_activity_fence_allows_existing_nested_settlement_only():
    owner = fake_owner()
    with owner.activity() as stop:
        owner.fence_admission()
        assert stop.is_set()
        with owner.activity():
            assert len(owner.producers) == 2
    with pytest.raises(capacity.CapacityAdmissionClosed):
        with owner.activity():
            pass
    owner.drain_producers(timeout=0)
    assert owner.producers == {}


def test_failed_drain_preserves_actual_activity_registration():
    owner = fake_owner()
    with owner.activity():
        with pytest.raises(capacity.CapacityIntegrityError, match='owner retained'):
            owner.drain_producers(timeout=0)
        assert len(owner.producers) == 1
    assert owner.producers == {}


def test_cross_thread_dependency_scope_uses_completion_not_thread_join():
    owner = fake_owner()
    scope = owner.activity(threaded=False)
    scope.__enter__()
    thread = threading.Thread(target=lambda: scope.__exit__(None, None, None))
    thread.start()
    thread.join(2)
    assert not thread.is_alive() and owner.producers == {}
    owner.drain_producers(timeout=0)


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('join_fails', [False, True])
def test_actual_lifespan_owner_order_without_any_native_sql(legacy, join_fails, tmp_path):
    import __future__
    from contextlib import asynccontextmanager
    path = Path(__file__).resolve().parents[1] / 'main.py'
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == 'lifespan')
    calls = []
    database = tmp_path / 'non-SQL-fixture.txt'
    if legacy:
        database.write_text('non-SQL legacy path-presence fixture')

    class Owner:
        path = database
        epoch = 'fake'
        def acquire(self): calls.append('acquire'); return self
        def open_admission(self): calls.append('open')
        def fence_admission(self): calls.append('fence')
        def drain_producers(self, **kw): calls.append('drain')
        def close(self): calls.append('close')

    def join():
        calls.append('join')
        if join_fails:
            raise RuntimeError('live producer')

    namespace = dict(asynccontextmanager=asynccontextmanager, DatabaseOwner=lambda engine: Owner(),
        engine=object(), _prepare_simulation_admission=lambda: calls.append('prepare'),
        init_db=lambda: calls.append('init'),
        initialize_resource_capacity=lambda owner, backup: calls.append('backup/migrate'),
        Session=lambda engine: nullcontext(object()), Repository=lambda session: session,
        _ensure_builtin_decks=lambda repo: None, _ensure_expansion_top_decks=lambda repo: None,
        _restore_simulation_jobs=lambda repo: calls.append('reconcile-cache'),
        SIM_START_LOCK=nullcontext(), SIM_SHUTTING_DOWN=True,
        SIM_JOB_SHUTDOWN_TIMEOUT=20, _shutdown_simulation_workers=join)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)

    async def run():
        async with namespace['lifespan'](None):
            calls.append('yield')

    if join_fails:
        with pytest.raises(RuntimeError, match='live producer'):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert calls[:2] == ['prepare', 'acquire']
    assert calls[2:4] == (['backup/migrate', 'init'] if legacy else ['init', 'backup/migrate'])
    assert calls[4:7] == ['reconcile-cache', 'open', 'yield']
    assert calls[7:] == (['join','fence'] if join_fails else ['join','fence','drain','close'])


def test_actual_repo_admission_commit_precedes_worker_publication():
    text = (Path(__file__).resolve().parents[1] / 'main.py').read_text()
    start = text[text.index('def _start_batch_job'):text.index('@app.post("/simulate/batch/{job_id}/cancel"')]
    assert start.index('admitted_repo.save_simulation_job(job)') < start.index('SIM_JOBS[job_id] = job')
    assert start.index('background_snapshot_token(job_id)') < start.index('t.start()')
    assert 'snapshot_token' in start and 'reservation_token=snapshot_token' in start


def test_snapshot_producer_context_precedes_game_work_and_releases_only_known_failure():
    text = (Path(__file__).resolve().parents[1] / 'analytics/service.py').read_text()
    assert text.index('self.repo.reserve_snapshot()') < text.index('yield token, cancelled')
    assert text.index('validate_snapshot_reservation(token)') < text.index('yield token, cancelled')
    assert 'except (SQLAlchemyError, CapacityIntegrityError):' in text
    assert 'reservation_token=reservation_token' in text


def test_retirement_keeps_retry_rows_and_requires_fenced_drained_owner():
    text = (Path(__file__).resolve().parents[1] / 'persistence/repository.py').read_text()
    tree = ast.parse(text)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'retire_simulations')
    body = ast.get_source_segment(text, node)
    assert 'owner.admissions_open or owner.producers' in body
    assert 'job_rows_reclaimed' in body and "'retired', None, None" in body
    assert 'request_json =' not in body
    assert 'self.session.delete(row)' in body and 'snapshot_ids' in body


def main_functions(*names):
    import __future__
    path = Path(__file__).resolve().parents[1] / 'main.py'
    tree = ast.parse(path.read_text())
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    return compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                   flags=__future__.annotations.compiler_flag)


@pytest.mark.parametrize('failure', [capacity.CapacityIntegrityError,
                                    capacity.CapacityAdmissionClosed, __import__('sqlalchemy').exc.SQLAlchemyError])
def test_actual_uncertain_update_fences_without_retry_or_cache_publication(failure):
    from sqlalchemy.exc import SQLAlchemyError
    calls = []
    start_lock, jobs_lock = threading.Lock(), threading.Lock()
    def persist(candidate):
        calls.append(dict(candidate))
        raise failure('private diagnostic must not be published')
    def owner(engine):
        assert start_lock.acquire(False)
        start_lock.release()
        assert jobs_lock.acquire(False)
        jobs_lock.release()
        return SimpleNamespace(fence_admission=lambda: calls.append('fence'))
    namespace = dict(SIM_START_LOCK=start_lock, SIM_JOBS_LOCK=jobs_lock,
        SIM_JOBS={'j': {'status': 'running'}}, SIM_SHUTTING_DOWN=False,
        _persist_job=persist, _prune_simulation_jobs=lambda: calls.append('prune'),
        SQLAlchemyError=SQLAlchemyError, CapacityIntegrityError=capacity.CapacityIntegrityError,
        CapacityAdmissionClosed=capacity.CapacityAdmissionClosed, owner_for_engine=owner,
        engine=object())
    exec(main_functions('_update_job', '_fence_uncertain_job'), namespace)
    with pytest.raises(failure):
        namespace['_update_job']('j', status='completed')
    assert calls == [{'status': 'completed'}, 'fence']
    assert namespace['SIM_JOBS'] == {} and namespace['SIM_SHUTTING_DOWN']


def test_actual_acknowledged_update_publishes_only_after_persistence():
    jobs = {'j': {'status': 'running'}}
    calls = []
    def persist(candidate):
        assert jobs['j']['status'] == 'running'
        calls.append(dict(candidate))
    namespace = dict(SIM_JOBS_LOCK=threading.Lock(), SIM_JOBS=jobs,
        _persist_job=persist, _prune_simulation_jobs=lambda: calls.append('prune'))
    exec(main_functions('_update_job'), namespace)
    namespace['_update_job']('j', status='completed')
    assert jobs['j']['status'] == 'completed'
    assert calls == [{'status': 'completed'}, 'prune']


def test_actual_worker_owner_lookup_failure_releases_slot_and_cancel_registry():
    from sqlalchemy.exc import SQLAlchemyError
    calls = []
    def lookup(engine):
        raise capacity.CapacityAdmissionClosed('no owner')
    namespace = dict(owner_for_engine=lookup, engine=object(), job_id='j',
        SIM_JOBS_LOCK=threading.Lock(), SIM_JOB_CANCEL_EVENTS={'j': object()},
        SIM_WORK_SLOT=SimpleNamespace(release=lambda: calls.append('release')),
        _fence_uncertain_job=lambda job_id: calls.append(('fence', job_id)),
        SimulationCancelled=type('Cancelled', (Exception,), {}),
        SimulationResourceLimit=type('Limit', (Exception,), {}),
        SQLAlchemyError=SQLAlchemyError, CapacityIntegrityError=capacity.CapacityIntegrityError,
        CapacityAdmissionClosed=capacity.CapacityAdmissionClosed)
    exec(main_functions('_runner'), namespace)
    namespace['_runner']()
    assert calls == [('fence', 'j'), 'release']
    assert namespace['SIM_JOB_CANCEL_EVENTS'] == {}


@pytest.mark.parametrize('failure', [capacity.CapacityIntegrityError,
                                    capacity.CapacityAdmissionClosed, __import__('sqlalchemy').exc.SQLAlchemyError])
def test_actual_initial_admission_uncertainty_fences_under_held_start_lock(failure):
    import time
    from sqlalchemy.exc import SQLAlchemyError
    calls = []
    slot, start_lock = threading.BoundedSemaphore(1), threading.Lock()
    def save(job):
        calls.append('save')
        raise failure('uncertain commit')
    def owner(engine):
        assert start_lock.locked()
        return SimpleNamespace(fence_admission=lambda: calls.append('fence'))
    namespace = dict(_reap_simulation_workers=lambda: None,
        SIM_START_LOCK=start_lock, SIM_JOBS_LOCK=threading.Lock(),
        SIM_JOBS={}, SIM_JOB_WORKERS={}, SIM_JOB_CANCEL_EVENTS={}, SIM_SHUTTING_DOWN=False,
        SIM_WORK_SLOT=slot, SIM_JOBS_ROW_LIMIT=10000, RESOURCE_LIMITS={'request_json_bytes': 1},
        checked_json=lambda *a: None, _validated_deck_cards=lambda *a: [],
        Session=lambda engine: nullcontext(object()), Repository=lambda session: SimpleNamespace(save_simulation_job=save),
        owner_for_engine=owner, engine=object(), threading=threading, time=time, nullcontext=nullcontext,
        SQLAlchemyError=SQLAlchemyError, CapacityIntegrityError=capacity.CapacityIntegrityError,
        CapacityAdmissionClosed=capacity.CapacityAdmissionClosed,
        SimulationResourceLimit=type('Limit', (Exception,), {}))
    exec(main_functions('_start_batch_job', '_fence_uncertain_job'), namespace)
    payload = SimpleNamespace(model_dump=lambda **kw: {}, matches=1, deck_a=[], deck_b=[])
    repo = SimpleNamespace(get_simulation_job=lambda key: None, count_simulation_jobs=lambda: 0)
    with start_lock, pytest.raises(failure):
        namespace['_start_batch_job'](payload, repo, 'j')
    assert calls == ['save', 'fence'] and namespace['SIM_SHUTTING_DOWN']
    assert not namespace['SIM_JOBS'] and not namespace['SIM_JOB_WORKERS']
    assert not namespace['SIM_JOB_CANCEL_EVENTS']
    assert slot.acquire(False)
    slot.release()


@pytest.mark.parametrize('failure,release', [(ValueError, True),
    (capacity.CapacityIntegrityError, False),
    (__import__('sqlalchemy').exc.SQLAlchemyError, False)])
def test_actual_snapshot_scope_releases_only_confirmed_computation_failure(failure, release):
    from contextlib import contextmanager
    from sqlalchemy.exc import SQLAlchemyError
    path = Path(__file__).resolve().parents[1] / 'analytics/service.py'
    tree = ast.parse(path.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name == '_snapshot_producer')
    calls = []
    @contextmanager
    def activity():
        yield threading.Event()
    repo = SimpleNamespace(session=object(), reserve_snapshot=lambda: calls.append('reserve') or 'token',
        validate_snapshot_reservation=lambda token: calls.append(('validate', token)),
        release_snapshot_reservation=lambda token: calls.append(('release', token)))
    namespace = dict(contextmanager=contextmanager,
        owner_for=lambda session: SimpleNamespace(activity=activity),
        SQLAlchemyError=SQLAlchemyError, CapacityIntegrityError=capacity.CapacityIntegrityError)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    with pytest.raises(failure):
        with namespace['_snapshot_producer'](SimpleNamespace(repo=repo), None, None):
            raise failure('fixture')
    assert calls == ['reserve', ('validate', 'token')] + ([('release', 'token')] if release else [])
