"""Officer's actual startup protocol with SQL/FD/server bindings replaced, not native I/O."""
import __future__
import ast
import json
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'frontend/tests/activated-top-selection-fixture.py'


def actual(path, *names, namespace):
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and node.name in names]
    assert {node.name for node in nodes} == set(names)
    for node in nodes:
        node.decorator_list = [decorator for decorator in node.decorator_list
                               if isinstance(decorator, ast.Name)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace


def immediate(coroutine):
    """These source protocols have no asynchronous I/O; do not create an event-loop socket."""
    iterator = coroutine.__await__()
    try:
        iterator.send(None)
    except StopIteration as done:
        return done.value
    finally:
        iterator.close()
    raise AssertionError('Unexpected asynchronous I/O in the pure protocol')


def lifecycle(tmp_path, *, existing=False, bootstrap_fails=False, join_fails=False):
    calls, registry = [], {}
    # Text path-presence control, deliberately NOT a SQLite database.
    path = tmp_path / 'non-SQL-presence.txt'
    if existing:
        path.write_text('Public synthetic path-presence control')
    engine = object()

    class Owner:
        epoch = '1' * 32
        admissions_open = False
        ready = False
        def acquire(self):
            assert engine not in registry
            calls.append('acquire')
            registry[engine] = self
            return self
        def require(self, *, ready=True):
            assert registry.get(engine) is self and (self.ready or not ready)
        def open_admission(self):
            self.require()
            calls.append('open')
            self.admissions_open = True
        def fence_admission(self):
            calls.append('fence')
            self.admissions_open = False
        def drain_producers(self, *, timeout):
            assert not self.admissions_open
            calls.append('drain')
        def close(self):
            assert not self.admissions_open
            calls.append('close')
            del registry[engine]
        def activity(self, *, threaded):
            self.require()
            if not self.admissions_open:
                raise state['CapacityAdmissionClosed']('Capacity admission is closed')
            assert threaded is False
            return nullcontext()

    owner = Owner()
    owner.path, owner.engine = path, engine

    def bootstrap(candidate, backup):
        assert candidate is owner
        assert backup == tmp_path / ('non-SQL-presence.txt.before-capacity-' + '1' * 32 + '.db')
        calls.append('bootstrap')
        if bootstrap_fails:
            raise RuntimeError('synthetic bootstrap failure')
        owner.ready = True

    def shutdown():
        calls.append('join')
        if join_fails:
            raise RuntimeError('synthetic live worker')

    state = dict(asynccontextmanager=asynccontextmanager, engine=engine,
                 DatabaseOwner=lambda candidate: owner,
                 _prepare_simulation_admission=lambda: calls.append('prepare'),
                 init_db=lambda: calls.append('init'),
                 initialize_resource_capacity=bootstrap,
                 Session=lambda candidate: nullcontext(calls.append('session')),
                 Repository=lambda session: session,
                 _ensure_builtin_decks=lambda repo: calls.append('builtin'),
                 _ensure_expansion_top_decks=lambda repo: calls.append('expansion'),
                 _restore_simulation_jobs=lambda repo: calls.append('restore-jobs'),
                 _shutdown_simulation_workers=shutdown, SIM_START_LOCK=threading.Lock(),
                 SIM_SHUTTING_DOWN=False, SIM_JOB_SHUTDOWN_TIMEOUT=20,
                 _OWNERS=registry, _OWNER_LOCK=threading.RLock(),
                 JSONResponse=lambda **kw: SimpleNamespace(**kw))
    actual(ROOT / 'backend/persistence/capacity.py', 'CapacityAdmissionClosed',
           'owner_for_engine', namespace=state)
    actual(ROOT / 'backend/persistence/db.py', 'get_session', namespace=state)
    actual(ROOT / 'backend/main.py', 'lifespan', 'capacity_closed_response', namespace=state)

    def request():
        # Keep the actual function-local import, binding it to the extracted real helper.
        parent, module = ModuleType('persistence'), ModuleType('persistence.capacity')
        parent.__path__ = []
        module.owner_for_engine = state['owner_for_engine']
        with patch.dict(sys.modules, {'persistence': parent, 'persistence.capacity': module}):
            dependency = state['get_session']()
            try:
                next(dependency)
                return SimpleNamespace(status_code=200, content={'synthetic_handler': True})
            except state['CapacityAdmissionClosed'] as error:
                return immediate(state['capacity_closed_response'](None, error))
            finally:
                dependency.close()

    return state, calls, registry, owner, request


def test_actual_officer_entry_starts_native_owner_before_first_api_dependency(tmp_path, monkeypatch):
    state, calls, registry, owner, request = lifecycle(tmp_path)
    responses = []

    def run(application, *, host, port, lifespan):
        assert host == '127.0.0.1' and port == 10237
        async def serve():
            if lifespan == 'on':
                async with application.router.lifespan_context(application):
                    responses.append(request())
            else:
                responses.append(request())
        immediate(serve())

    monkeypatch.setitem(sys.modules, 'uvicorn', SimpleNamespace(run=run))
    entry = next(node for node in ast.parse(FIXTURE.read_text()).body
                 if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'")
    exec(compile(ast.Module(body=[entry], type_ignores=[]), str(FIXTURE), 'exec'),
         dict(__name__='__main__', os=SimpleNamespace(environ={}),
              app=SimpleNamespace(router=SimpleNamespace(lifespan_context=state['lifespan']))))
    assert [(response.status_code, response.content) for response in responses] == [
        (200, {'synthetic_handler': True})]
    assert calls == ['prepare', 'acquire', 'init', 'bootstrap', 'session', 'builtin',
                     'expansion', 'restore-jobs', 'open', 'session', 'join', 'fence', 'drain', 'close']
    assert not registry and not owner.admissions_open


@pytest.mark.parametrize('closed', [False, True])
def test_actual_dependency_keeps_503_without_owner_or_after_shutdown(tmp_path, closed):
    state, calls, registry, owner, request = lifecycle(tmp_path)
    if closed:
        async def serve():
            async with state['lifespan'](None):
                assert request().status_code == 200
        immediate(serve())
    before = list(calls)
    response = request()
    assert response.status_code == 503
    assert response.content == {'detail': {'code': 'simulation_shutting_down'}}
    assert calls == before and not registry and not owner.admissions_open


@pytest.mark.parametrize('existing', [False, True])
def test_actual_native_lifespan_bootstrap_order_and_fenced_rejection(tmp_path, existing):
    state, calls, registry, owner, request = lifecycle(tmp_path, existing=existing)
    async def serve():
        async with state['lifespan'](None):
            assert calls[:4] == ['prepare', 'acquire'] + (
                ['bootstrap', 'init'] if existing else ['init', 'bootstrap'])
            assert request().status_code == 200
            owner.fence_admission()
            before = list(calls)
            assert request().status_code == 503
            assert calls == before
    immediate(serve())
    assert calls[-4:] == ['join', 'fence', 'drain', 'close'] and not registry


def test_actual_native_bootstrap_failure_never_opens_admission(tmp_path):
    state, calls, registry, owner, request = lifecycle(tmp_path, bootstrap_fails=True)
    async def serve():
        async with state['lifespan'](None):
            pytest.fail('Failed bootstrap yielded a running application')
    with pytest.raises(RuntimeError, match='synthetic bootstrap failure'):
        immediate(serve())
    assert calls == ['prepare', 'acquire', 'init', 'bootstrap', 'close']
    assert not registry and not owner.admissions_open and request().status_code == 503


@pytest.mark.parametrize('join_fails', [False, True])
def test_actual_native_shutdown_does_not_mask_failure_or_close_live_owner(tmp_path, join_fails):
    state, calls, registry, owner, request = lifecycle(tmp_path, join_fails=join_fails)
    async def serve():
        async with state['lifespan'](None):
            raise ValueError('synthetic application failure')
    if join_fails:
        with pytest.raises(RuntimeError, match='synthetic live worker'):
            immediate(serve())
        assert calls[-2:] == ['join', 'fence'] and registry == {owner.engine: owner}
    else:
        with pytest.raises(ValueError, match='synthetic application failure'):
            immediate(serve())
        assert calls[-4:] == ['join', 'fence', 'drain', 'close'] and not registry
    assert not owner.admissions_open and request().status_code == 503


def guard_state(tmp_path):
    return actual(FIXTURE, 'guard', namespace=dict(
        Path=Path, os=__import__('os'), DATABASE=tmp_path / 'officer-test.sqlite',
        BOOTSTRAP_DATABASES=frozenset()))


@pytest.mark.parametrize('readonly', [False, True])
def test_fixture_guard_accepts_only_exact_owned_database_form(tmp_path, readonly):
    state = guard_state(tmp_path)
    address = (state['DATABASE'].as_uri() + '?mode=ro') if readonly else str(state['DATABASE'])
    state['guard']('sqlite3.connect', (address,))


@pytest.mark.parametrize('target', [
    ':memory:', 'foreign.sqlite', 'officer-test.sqlite', '../officer-test.sqlite',
    'file:officer-test.sqlite?mode=ro', '/tmp/foreign.sqlite',
    'db-uri-rw', 'db-uri-extra', 'old-epoch', 'epoch-uri', 'backup-sibling',
])
def test_fixture_guard_rejects_foreign_memory_uri_and_unapproved_backup(tmp_path, target):
    state = guard_state(tmp_path)
    database = state['DATABASE']
    address = {
        'db-uri-rw': database.as_uri() + '?mode=rw',
        'db-uri-extra': database.as_uri() + '?mode=ro&cache=shared',
        'old-epoch': str(tmp_path / ('officer-test.sqlite.before-capacity-' + '0' * 32 + '.db')),
        'epoch-uri': (tmp_path / ('officer-test.sqlite.before-capacity-' + '0' * 32 + '.db')).as_uri() + '?mode=ro',
        'backup-sibling': str(tmp_path / 'officer-test.sqlite.backup'),
    }.get(target, target)
    with pytest.raises(RuntimeError, match='foreign database'):
        state['guard']('sqlite3.connect', (address,))


@pytest.mark.parametrize('fails', [False, True])
def test_fixture_bootstrap_delegates_native_and_scopes_exact_backup_even_on_failure(tmp_path, fails):
    state = guard_state(tmp_path)
    engine = object()
    backup = tmp_path / ('officer-test.sqlite.before-capacity-' + 'a' * 32 + '.db')
    calls = []
    owner = SimpleNamespace(engine=engine, path=state['DATABASE'], epoch='a' * 32,
                            require=lambda **kw: calls.append(kw))
    def native(candidate, destination):
        assert candidate is owner and destination == backup
        for address in (str(backup), backup.as_uri() + '?mode=ro'):
            state['guard']('sqlite3.connect', (address,))
        if fails:
            raise RuntimeError('synthetic native bootstrap failure')
        return 'native result'
    state.update(db=SimpleNamespace(engine=engine), NATIVE_INITIALIZE_CAPACITY=native)
    actual(FIXTURE, 'initialize_owned_capacity', namespace=state)
    if fails:
        with pytest.raises(RuntimeError, match='synthetic native bootstrap failure'):
            state['initialize_owned_capacity'](owner, backup)
    else:
        assert state['initialize_owned_capacity'](owner, backup) == 'native result'
    assert calls == [{'ready': False}] and state['BOOTSTRAP_DATABASES'] == frozenset()
    for address in (str(backup), backup.as_uri() + '?mode=ro'):
        with pytest.raises(RuntimeError, match='foreign database'):
            state['guard']('sqlite3.connect', (address,))


@pytest.mark.parametrize('wrong', ['engine', 'path', 'backup'])
def test_fixture_bootstrap_rejects_foreign_binding_before_native_delegate(tmp_path, wrong):
    state = guard_state(tmp_path)
    engine = object()
    backup = tmp_path / ('officer-test.sqlite.before-capacity-' + 'a' * 32 + '.db')
    owner = SimpleNamespace(engine=object() if wrong == 'engine' else engine,
                            path=tmp_path / 'foreign.sqlite' if wrong == 'path' else state['DATABASE'],
                            epoch='a' * 32, require=lambda **kw: None)
    state.update(db=SimpleNamespace(engine=engine),
                 NATIVE_INITIALIZE_CAPACITY=lambda *args: pytest.fail('Foreign bootstrap delegated'))
    actual(FIXTURE, 'initialize_owned_capacity', namespace=state)
    with pytest.raises(RuntimeError, match='Foreign capacity bootstrap'):
        state['initialize_owned_capacity'](owner, backup.with_name('foreign.db') if wrong == 'backup' else backup)
    assert state['BOOTSTRAP_DATABASES'] == frozenset()


def test_fixture_import_has_no_schema_or_restore_io_before_native_owner():
    tree = ast.parse(FIXTURE.read_text())
    startup = [node for node in tree.body
               if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.If))]
    calls = [ast.unparse(node.func) for parent in startup for node in ast.walk(parent)
             if isinstance(node, ast.Call)]
    assert 'db.init_db' not in calls and 'main._restore_active_matches' not in calls


def test_fixture_configures_owned_import_default_before_persistence_import(tmp_path):
    tree = ast.parse(FIXTURE.read_text())
    imports = [node.lineno for node in tree.body
               if isinstance(node, ast.ImportFrom) and node.module == 'persistence']
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Subscript)
                           and ast.unparse(target) == "os.environ['MTG_DATABASE_PATH']"
                           for target in node.targets)]
    assert len(assignments) == 1 and assignments[0].lineno < min(imports)
    environment = {}
    database = tmp_path / 'officer-test.sqlite'
    exec(compile(ast.Module(body=assignments, type_ignores=[]), str(FIXTURE), 'exec'),
         dict(os=SimpleNamespace(environ=environment), DATABASE=database))
    assert environment == {'MTG_DATABASE_PATH': str(database)}


@pytest.mark.parametrize('host', ['127.0.0.1', '::1', 'localhost', '203.0.113.4'])
def test_existing_socket_rule_is_not_widened(tmp_path, host):
    state = guard_state(tmp_path)
    if host == '203.0.113.4':
        with pytest.raises(RuntimeError, match='Non-loopback'):
            state['guard']('socket.connect', (None, (host, 443)))
    else:
        state['guard']('socket.connect', (None, (host, 10237)))


def test_actual_retired_key_rejects_410_before_admission_or_worker_publication():
    class Rejected(Exception):
        def __init__(self, status_code, detail):
            self.status_code, self.detail = status_code, detail
    state = dict(json=json, HTTPException=Rejected, _reap_simulation_workers=lambda: None,
                 SIM_JOBS_LOCK=threading.Lock(), SIM_JOBS={}, SIM_JOB_WORKERS={},
                 SIM_SHUTTING_DOWN=True)
    actual(ROOT / 'backend/main.py', '_retired_job_response', '_start_batch_job', namespace=state)
    repo = SimpleNamespace(get_simulation_job=lambda key: SimpleNamespace(
        request_json='{}', status='retired', id='a' * 32))
    with pytest.raises(Rejected) as caught:
        state['_start_batch_job'](SimpleNamespace(model_dump=lambda **kw: {}), repo, 'a' * 32)
    assert caught.value.status_code == 410
    assert caught.value.detail == {'code': 'simulation_job_retired', 'job_id': 'a' * 32}
    assert state['SIM_JOB_WORKERS'] == {} and state['SIM_JOBS'] == {}
