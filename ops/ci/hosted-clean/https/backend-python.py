#!/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK/venv/bin/python
"""REVIEW ONLY: real uvicorn entry with local resource/ASGI observations."""
import atexit
from contextlib import asynccontextmanager, closing, contextmanager
import json
from pathlib import Path
import runpy
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "runtime-gate/backend"
LEDGER = ROOT / "evidence/runtime-gate/backend.jsonl"
assert Path.cwd() == BACKEND
assert sys.argv[1:] == ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "48344", "--workers", "1", "--no-access-log", "--no-proxy-headers", "--log-level", "critical"]
LEDGER.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
reject_phase = False
denials = []
sql_role = threading.local()


def record(value):
    with LEDGER.open("a") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def audit(event, args):
    denied = False
    if event == "sqlite3.connect":
        database = str(args[0])
        scoped = getattr(sql_role, "operands", {})
        denied = reject_phase or not (database == str(BACKEND / "mtg_lab.db") or database in scoped)
        if denied or database in scoped:
            primary_uri = (BACKEND / "mtg_lab.db").as_uri()
            category = scoped.get(database, "primary_uri" if database.startswith(primary_uri + "?") else "memory" if database == ":memory:" else "unrecognized_operand")
            record({"event": "sql_operand_policy", "operand_role": category, "allowed": not denied,
                    "request_rejection_phase": reject_phase, "active_role": getattr(sql_role, "name", None)})
    elif event == "socket.bind":
        denied = args[1] != ("127.0.0.1", 48344)
    elif event == "socket.connect":
        denied = True
    elif event == "socket.getaddrinfo":
        denied = args[0] not in {"127.0.0.1", "localhost"}
    if denied:
        denials.append(event)
        record({"event": "native_denial", "audit_event": event})
        raise RuntimeError("Gate native resource denied")


sys.addaudithook(audit)
import sqlite3
import sqlite3.dbapi2
import _sqlite3


def socket_canary(operation, address):
    with closing(socket.socket()) as client:
        getattr(client, operation)(address)


canaries = [
    ("sqlite3_foreign_path", lambda: sqlite3.connect(str(ROOT / "outside-denied.db"))),
    ("dbapi2_foreign_path", lambda: sqlite3.dbapi2.connect(str(ROOT / "dbapi2-denied.db"))),
    ("native_foreign_path", lambda: _sqlite3.connect(str(ROOT / "native-denied.db"))),
    ("runtime_uri_denied", lambda: sqlite3.connect("file:" + str(BACKEND / "mtg_lab.db") + "?mode=ro", uri=True)),
    ("dbapi2_memory_denied", lambda: sqlite3.dbapi2.connect(":memory:")),
    ("native_memory_denied", lambda: _sqlite3.connect(":memory:")),
    ("outside_socket", lambda: socket_canary("connect", ("127.0.0.1", 9))),
    ("outside_dns", lambda: socket.getaddrinfo("invalid.example", 443)),
    ("wrong_bind_port", lambda: socket_canary("bind", ("127.0.0.1", 48345))),
    ("wildcard_bind", lambda: socket_canary("bind", ("0.0.0.0", 48344))),
]
for label, canary in canaries:
    try:
        canary()
    except RuntimeError:
        record({"event": "canary", "label": label, "denied": True})
    else:
        raise AssertionError("Native canary escaped guard")
assert len(denials) == len(canaries)

import sqlalchemy
import sqlmodel
from sqlalchemy import event
engines = []
real_create_engine = sqlalchemy.create_engine


def create_engine(*args, **kwargs):
    engine = real_create_engine(*args, **kwargs)
    engines.append(engine)
    return engine


sqlalchemy.create_engine = sqlmodel.create_engine = create_engine
sys.path.insert(0, str(BACKEND))
from browser_origin import BrowserOriginMiddleware
real_origin_call = BrowserOriginMiddleware.__call__


def world():
    # Reuse the exact qualified full-controller/root snapshot helper, not wire views.
    from tests.test_browser_origin_http import complete_root_snapshot
    with closing(sqlite3.connect(str(BACKEND / "mtg_lab.db"))) as connection:
        sql = list(connection.iterdump())
    return complete_root_snapshot(), sql


async def observed_origin_call(self, scope, receive, send):
    global reject_phase
    if scope["type"] != "http":
        return await real_origin_call(self, scope, receive, send)
    headers = scope.get("headers", ())
    assert not any(name.lower() == b"authorization" for name, _ in headers)
    origins = [value for name, value in headers if name.lower() == b"origin"]
    malicious = scope["method"] not in {"GET", "HEAD", "OPTIONS"} and bool(origins) and (len(origins) != 1 or origins[0].decode("latin-1") not in self.origins)
    record({"event": "backend_request", "method": scope["method"], "authorization_absent": True,
            "media_prefix_preserved": scope["path"].startswith("/card-images/")})
    if not malicious:
        return await real_origin_call(self, scope, receive, send)
    import main
    before = world()
    observed = dict(body=0, dependency=0, sql=0, action=0, sync=0)
    statuses = []
    original_overrides = dict(main.app.dependency_overrides)
    original_action = main.checked_action
    original_sync = main.ScryfallSyncService.sync_card_by_name

    def forbidden(kind):
        def trap(*args, **kwargs):
            observed[kind] += 1
            raise AssertionError("Rejected browser request crossed ASGI boundary")
        return trap

    async def trapped_receive():
        observed["body"] += 1
        raise AssertionError("Rejected browser request consumed ASGI body")

    async def observed_send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])
        await send(message)

    sql_trap = forbidden("sql")
    main.app.dependency_overrides[main.get_repo] = forbidden("dependency")
    main.checked_action = forbidden("action")
    main.ScryfallSyncService.sync_card_by_name = forbidden("sync")
    event.listen(main.engine, "before_cursor_execute", sql_trap)
    try:
        reject_phase = True
        await real_origin_call(self, scope, trapped_receive, observed_send)
    finally:
        reject_phase = False
        event.remove(main.engine, "before_cursor_execute", sql_trap)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original_overrides)
        main.checked_action = original_action
        main.ScryfallSyncService.sync_card_by_name = original_sync
    equal = world() == before
    record({"event": "atomic_rejection", "status": statuses, "observations": observed,
            "complete_root_controller_sql_equal": equal})
    assert statuses == [403] and not any(observed.values()) and equal


BrowserOriginMiddleware.__call__ = observed_origin_call


closure_recorded = False


def closure(phase):
    global closure_recorded
    if closure_recorded:
        record({"event": "closure_fallback_skipped", "phase": phase})
        return
    closure_recorded = True
    import main
    pools = []
    for engine in engines:
        engine.dispose()
        pools.append(engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else None)
    database_fds = []
    for descriptor in Path("/proc/self/fd").iterdir():
        try:
            target = str(descriptor.readlink())
        except FileNotFoundError:
            continue
        if target.startswith(str(BACKEND / "mtg_lab.db")):
            database_fds.append(descriptor.name)
    record({"event": "closure", "phase": phase, "original_shutdown_succeeded": phase == "lifespan_after_original_shutdown", "engines_disposed": len(engines), "checkedout": pools,
            "jobs": len(main.SIM_JOBS), "cancel_events_before_cleanup": len(main.SIM_JOB_CANCEL_EVENTS),
            "active_matches_saved": len(main.ACTIVE_MATCHES),
            "native_database_fds": database_fds,
            "nonmain_threads": sum(t.is_alive() and t is not threading.main_thread() for t in threading.enumerate()),
            "unexpected_native_denials": denials[len(canaries):]})


import main


@contextmanager
def sql_operands(name, operands):
    assert not getattr(sql_role, "operands", {}), "Nested native SQL role"
    sql_role.name, sql_role.operands = name, operands
    try:
        yield
    finally:
        sql_role.name, sql_role.operands = None, {}


from persistence.capacity import DatabaseOwner
original_owner_backup = DatabaseOwner.backup


def observed_owner_backup(owner, destination, *, timeout=5.0):
    primary = BACKEND / "mtg_lab.db"
    expected = primary.with_name(primary.name + ".before-capacity-" + owner.epoch + ".db")
    owner.require(ready=False)
    assert owner.path == primary and Path(destination) == expected
    assert primary.resolve() == primary and expected.parent.resolve() == BACKEND
    assert not primary.is_symlink() and not expected.is_symlink()
    operands = {primary.as_uri() + "?mode=ro": "owner_backup_source_ro",
                str(expected): "owner_backup_destination",
                expected.as_uri() + "?mode=ro": "owner_backup_verify_ro"}
    with sql_operands("live_owner_capacity_backup", operands):
        return original_owner_backup(owner, destination, timeout=timeout)


DatabaseOwner.backup = observed_owner_backup
import os
import persistence.capacity as _native_capacity

_production_state = dict(owner=None, pool=None, shutdown=False, delegating=False,
                         close_returned=False, before_close=None, dispose_events=[],
                         original_lifespan_returned=False, failure_type=None, close_thread=None)
_original_native_owner_close = DatabaseOwner.close


def _production_pool_counts(pool):
    return {name: getattr(pool, name)() if callable(getattr(pool, name, None)) else None
            for name in ("checkedout", "checkedin")}


def _production_disposed(engine):
    # Acquire-time and inherited observer/atexit disposal cannot qualify shutdown.
    if (engine is main.engine and _production_state["shutdown"] and _production_state["delegating"]
            and threading.get_ident() == _production_state["close_thread"]):
        _production_state["dispose_events"].append(dict(
            engine_exact=True, retired_pool_counts=_production_pool_counts(_production_state["pool"])))


def _observe_native_owner_close(owner):
    tracked = owner is _production_state["owner"] and _production_state["shutdown"]
    if tracked:
        _production_state["before_close"] = dict(
            exact_engine=owner.engine is main.engine,
            exact_pool=owner.pool is _production_state["pool"] is main.engine.pool,
            pool_counts=_production_pool_counts(owner.pool),
            registered=_native_capacity._OWNERS.get(main.engine) is owner,
            producers=len(owner.producers), admissions_open=owner.admissions_open,
            owner_fd_present=owner.fd is not None)
        _production_state["delegating"] = True
        _production_state["close_thread"] = threading.get_ident()
    try:
        result = _original_native_owner_close(owner)
        if tracked:
            _production_state["close_returned"] = True
        return result
    finally:
        if tracked:
            _production_state["delegating"] = False


DatabaseOwner.close = _observe_native_owner_close
event.listen(main.engine, "engine_disposed", _production_disposed)


def _production_first_row():
    owner = _production_state["owner"]
    row = dict(event="production_first_shutdown", backend_pid=os.getpid(),
               before_observer_cleanup=True, verified=False,
               original_lifespan_returned=_production_state["original_lifespan_returned"],
               native_owner_close_returned=_production_state["close_returned"],
               native_dispose_events=list(_production_state["dispose_events"]),
               before_native_close=_production_state["before_close"],
               failure_type=_production_state["failure_type"])
    if owner is None:
        row["status"] = "no_genuine_live_owner_observed"
        return row
    database_fds = []
    for descriptor in Path("/proc/self/fd").iterdir():
        try:
            target = str(descriptor.readlink())
        except FileNotFoundError:
            continue
        if target.startswith(str(BACKEND / "mtg_lab.db")):
            database_fds.append(descriptor.name)
    row.update(epoch=owner.epoch, owner_fd_closed=owner.fd is None,
               owner_ready=owner.ready, admissions_open=owner.admissions_open,
               producers=len(owner.producers),
               owner_registry_absent=main.engine not in _native_capacity._OWNERS,
               workers=len(main.SIM_JOB_WORKERS), cancel_events=len(main.SIM_JOB_CANCEL_EVENTS),
               jobs=len(main.SIM_JOBS), native_database_backup_lock_fds=database_fds)
    before = row["before_native_close"]
    events = row["native_dispose_events"]
    row["verified"] = bool(
        row["original_lifespan_returned"] and row["native_owner_close_returned"]
        and row["failure_type"] is None and before is not None
        and before["exact_engine"] and before["exact_pool"] and before["registered"]
        and before["owner_fd_present"] and before["pool_counts"]["checkedout"] == 0
        and type(before["pool_counts"]["checkedin"]) is int
        and before["producers"] == 0 and not before["admissions_open"]
        and len(events) == 1 and events[0]["engine_exact"]
        and events[0]["retired_pool_counts"]["checkedin"] == 0
        and row["owner_fd_closed"] and not row["owner_ready"] and not row["admissions_open"]
        and row["owner_registry_absent"] and row["producers"] == row["workers"]
        == row["cancel_events"] == row["jobs"] == 0 and not database_fds)
    row["status"] = "verified_before_observer_assist" if row["verified"] else "not_verified"
    return row


original_lifespan = main.app.router.lifespan_context


@asynccontextmanager
async def observed_lifespan(app):
    try:
        async with original_lifespan(app) as state:
            owner = _native_capacity.owner_for_engine(main.engine)
            _production_state["owner"], _production_state["pool"] = owner, owner.pool
            record(dict(event="production_owner_live", backend_pid=os.getpid(), epoch=owner.epoch))
            try:
                yield state
            finally:
                _production_state["shutdown"] = True
        _production_state["original_lifespan_returned"] = True
    except BaseException as exc:
        _production_state["failure_type"] = type(exc).__name__
        raise
    finally:
        row = _production_first_row()
        record(row)
        _production_state["shutdown"] = False
        # A failed pre-assist row is immutable and cannot be repaired by atexit.
        if not row["verified"]:
            raise AssertionError("Production-first native shutdown not verified")
    # Original observer-assisted cleanup happens ONLY after the genuine proof.
    closure("lifespan_after_original_shutdown")


main.app.router.lifespan_context = observed_lifespan
atexit.register(lambda: closure("atexit_fallback"))
sys.argv = ["uvicorn", *sys.argv[3:]]
runpy.run_module("uvicorn", run_name="__main__")
