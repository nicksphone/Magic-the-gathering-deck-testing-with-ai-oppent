"""Pure ownership protocol checks; the separate original31 gate proves real games."""
import __future__
import ast
from pathlib import Path
from types import SimpleNamespace
import json
import threading
import time

import pytest


class Rejected(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Request:
    def __init__(self, value=None):
        self.value = value or {}

    def model_dump(self, **kwargs):
        return self.value


@pytest.fixture
def policy():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    names = {"_reap_simulation_workers", "_prepare_simulation_admission",
             "_shutdown_simulation_workers", "_start_batch_job", "simulate_batch_start"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    state = dict(threading=threading, time=time, json=json, HTTPException=Rejected,
                 Depends=lambda dependency: None, get_repo=object(),
                 SIM_START_LOCK=threading.Lock(), SIM_JOBS_LOCK=threading.Lock(),
                 SIM_JOB_WORKERS={}, SIM_JOBS={}, SIM_SHUTTING_DOWN=False,
                 SIM_JOB_SHUTDOWN_TIMEOUT=1.0)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "actual-job-policy", "exec",
                 flags=__future__.annotations.compiler_flag), state)
    owned = []

    def worker(job, target):
        cancel = threading.Event()
        release = threading.Event()
        thread = threading.Thread(target=target, args=(cancel, release))
        state["SIM_JOB_WORKERS"][job] = (thread, cancel)
        owned.append((thread, cancel, release))
        return thread, cancel, release

    yield state, worker, owned
    for thread, cancel, release in owned:
        cancel.set()
        release.set()
    for thread, _cancel, _release in owned:
        if thread.ident is not None:
            thread.join(2)
            assert not thread.is_alive(), "pure protocol test left its owned thread alive"


def test_shutdown_cancels_and_joins_actual_thread(policy):
    state, worker, _ = policy
    thread, cancel, _ = worker("one", lambda event, release: event.wait())
    thread.start()
    state["_shutdown_simulation_workers"]()
    assert cancel.is_set() and not thread.is_alive()
    assert state["SIM_JOB_WORKERS"] == {} and state["SIM_SHUTTING_DOWN"]


def test_timeout_retains_live_worker_and_closed_admission(policy):
    state, worker, _ = policy
    state["SIM_JOB_SHUTDOWN_TIMEOUT"] = 0.01
    thread, cancel, _ = worker("stuck", lambda event, release: release.wait())
    thread.start()
    with pytest.raises(RuntimeError, match="workers to stop"):
        state["_shutdown_simulation_workers"]()
    assert thread.is_alive() and cancel.is_set()
    assert "stuck" in state["SIM_JOB_WORKERS"] and state["SIM_SHUTTING_DOWN"]


def test_admission_lock_timeout_is_truthful(policy):
    state, _worker, _ = policy
    state["SIM_JOB_SHUTDOWN_TIMEOUT"] = 0.01
    state["SIM_START_LOCK"].acquire()
    try:
        with pytest.raises(RuntimeError, match="fencing simulation admission"):
            state["_shutdown_simulation_workers"]()
        assert not state["SIM_SHUTTING_DOWN"]
    finally:
        state["SIM_START_LOCK"].release()


def test_startup_refuses_live_worker_before_reopening(policy):
    state, worker, _ = policy
    state["SIM_SHUTTING_DOWN"] = True
    thread, _cancel, _ = worker("live", lambda event, release: release.wait())
    thread.start()
    with pytest.raises(RuntimeError, match="still running"):
        state["_prepare_simulation_admission"]()
    assert state["SIM_SHUTTING_DOWN"] and thread.is_alive()


def test_startup_reaps_dead_worker_but_stays_fenced_until_initialization(policy):
    state, worker, _ = policy
    thread, _cancel, _ = worker("done", lambda event, release: None)
    thread.start()
    thread.join(2)
    state["_prepare_simulation_admission"]()
    assert not state["SIM_JOB_WORKERS"] and state["SIM_SHUTTING_DOWN"]


def test_shutdown_waits_for_registration_and_start_under_admission_lock(policy):
    state, worker, owned = policy
    registered, allow_start, shutdown_called, finished = [threading.Event() for _ in range(4)]
    failures = []

    def controlled_admit(payload, repo, key):
        def finish_after_cancel(cancel, release):
            cancel.wait()
            with state["SIM_JOBS_LOCK"]:
                finished.set()
        thread, _cancel, _ = worker("race", finish_after_cancel)
        registered.set()
        assert allow_start.wait(2)
        thread.start()
        return {"job_id": "race"}

    def start():
        try:
            state["simulate_batch_start"](Request(), object())
        except BaseException as exc:
            failures.append(exc)

    def shutdown():
        shutdown_called.set()
        try:
            state["_shutdown_simulation_workers"]()
        except BaseException as exc:
            failures.append(exc)

    state["_start_batch_job"] = controlled_admit
    starter, stopper = threading.Thread(target=start), threading.Thread(target=shutdown)
    try:
        starter.start()
        assert registered.wait(2)
        assert owned[0][0].ident is None
        stopper.start()
        assert shutdown_called.wait(2)
        assert not state["SIM_SHUTTING_DOWN"]
        allow_start.set()
        starter.join(2)
        stopper.join(2)
        assert not failures and not starter.is_alive() and not stopper.is_alive()
        assert finished.is_set() and not state["SIM_JOB_WORKERS"]
    finally:
        allow_start.set()
        for thread, cancel, release in owned:
            cancel.set()
            release.set()
        starter.join(2)
        if stopper.ident is not None:
            stopper.join(2)


def test_closed_admission_rejects_new_work_before_count_or_validation(policy):
    state, _worker, _ = policy
    state["SIM_SHUTTING_DOWN"] = True
    with pytest.raises(Rejected) as caught:
        state["_start_batch_job"](Request(), object(), None)
    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "simulation_shutting_down"
    assert not state["SIM_JOB_WORKERS"] and not state["SIM_JOBS"]


def test_existing_key_replay_and_conflict_still_precede_closed_admission(policy):
    state, _worker, _ = policy
    state["SIM_SHUTTING_DOWN"] = True
    repo = SimpleNamespace(get_simulation_job=lambda key: SimpleNamespace(request_json="{}", status="completed"))
    assert state["_start_batch_job"](Request(), repo, "a" * 32) == {"job_id": "a" * 32, "status": "completed"}
    with pytest.raises(Rejected) as caught:
        state["_start_batch_job"](Request({"matches": 2}), repo, "a" * 32)
    assert caught.value.status_code == 409


def test_product_registers_before_start_and_handler_uses_shared_lock():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    start = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_start_batch_job")
    registered = next(node.lineno for node in ast.walk(start) if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                              and target.value.id == "SIM_JOB_WORKERS" for target in node.targets))
    launched = next(node.lineno for node in ast.walk(start) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "start")
    assert registered < launched
    handler = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "simulate_batch_start")
    assert any(isinstance(node, ast.With) and any(isinstance(item.context_expr, ast.Name)
               and item.context_expr.id == "SIM_START_LOCK" for item in node.items) for node in ast.walk(handler))
