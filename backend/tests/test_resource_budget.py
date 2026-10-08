"""Pure policy checks; fake candidates are not native gameplay evidence."""
import ast
import __future__
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from analytics.resource_budget import (
    RESOURCE_LIMITS, ResourceBudget, SimulationResourceLimit, checked_json, checked_text,
)
from analytics.service import AnalyticsService


@pytest.mark.parametrize("value", [None, True, False, 0, -12, 1.25, float("inf"),
    "plain", "quote\" slash\\ newline\n", chr(0x7F), chr(0xE9), chr(0x1F600),
    [], {}, [1, (2, 3)], {None: 0, True: 1, 2.5: 2}, {"nested": [True, None]}])
def test_exact_default_json_boundary(value):
    encoded = json.dumps(value)
    size = len(encoded.encode("utf-8"))
    assert checked_json(value, size, "result_json") == encoded
    with pytest.raises(SimulationResourceLimit, match="resource_limit:result_json"):
        checked_json(value, size - 1, "result_json")


def test_escaped_preflight_prevents_original_encoder_call():
    value = {"text": chr(0x1F600) * 100}
    calls = []
    with pytest.raises(SimulationResourceLimit):
        checked_json(value, 1000, "snapshot_json", encoder=lambda: calls.append(True))
    assert not calls


def test_checked_writer_uses_original_encoder_exactly_once():
    calls = []
    value = {"x": chr(0xE9)}

    def encode():
        calls.append(True)
        return json.dumps(value)

    assert checked_json(value, 100, "snapshot_json", encoder=encode) == json.dumps(value)
    assert calls == [True]


def test_raw_utf8_not_character_count():
    value = chr(0x1F600)
    assert checked_text(value, 4, "error") == value
    with pytest.raises(SimulationResourceLimit, match="resource_limit:error"):
        checked_text(value, 3, "error")


def test_cycle_rejected_but_shared_alias_encoded_twice():
    value = {}
    value["cycle"] = value
    with pytest.raises(SimulationResourceLimit):
        checked_json(value, 1000, "result_json")
    shared = [1]
    repeated = {"a": shared, "b": shared}
    assert checked_json(repeated, 1000, "result_json") == json.dumps(repeated)


@pytest.mark.parametrize("options,dimension", [
    ({"nodes": 1, "scalar": 8192}, "trace_nodes"),
    ({"depth": 0, "scalar": 8192}, "trace_depth"),
    ({"scalar": 0}, "trace_scalar")])
def test_trace_preflight_limits(options, dimension):
    with pytest.raises(SimulationResourceLimit, match="resource_limit:" + dimension):
        checked_json({"x": ["value"]}, 1000, "trace_entry", **options)


def test_trace_inputs_reject_lki_scalar_before_copy():
    player = SimpleNamespace(hand=[], battlefield=[], mana_pool={})
    item = SimpleNamespace(payload={"__source_lki": {"oracle_text": "x" * 8193}},
                           id="i", label="s", effect_key="x", source_card_id="missing")
    state = SimpleNamespace(cards={}, players={1: player, 2: player}, stack=[item])
    budget = ResourceBudget()
    with pytest.raises(SimulationResourceLimit, match="resource_limit:trace_scalar"):
        budget.trace_inputs(state, 1, {"type": "pass_priority"}, "")


def test_trace_prefix_and_order_are_counted():
    limits = dict(RESOURCE_LIMITS, action_log_growth_reserve=2)
    budget = ResourceBudget(limits)
    old = SimpleNamespace(log=["a"])
    new = SimpleNamespace(log=["a", "bb"], cards={})
    budget.begin_game(old.log)
    budget.accept_candidate(old, new, "T")
    assert new.log == ["a", "T", "bb"]
    assert budget.game_bytes == budget.batch_bytes == 4
    assert budget.game_entries == budget.batch_entries == 3


def test_cumulative_limit_survives_game_reset_and_rejects_before_insert():
    budget = ResourceBudget(dict(RESOURCE_LIMITS, batch_log_utf8_bytes=5, action_log_growth_reserve=2))
    old = SimpleNamespace(log=["a"])
    budget.begin_game(old.log)
    budget.accept_candidate(old, SimpleNamespace(log=["a", "bb"], cards={}), "T")
    budget.begin_game(old.log)
    candidate = SimpleNamespace(log=["a", "bb"], cards={})
    with pytest.raises(SimulationResourceLimit, match="resource_limit:batch_log"):
        budget.accept_candidate(old, candidate, "T")
    assert candidate.log == ["a", "bb"] and old.log == ["a"]


def test_clone_headroom_rejects_before_an_action():
    budget = ResourceBudget(dict(RESOURCE_LIMITS, game_log_utf8_bytes=5, action_log_growth_reserve=5))
    budget.begin_game(["a"])
    with pytest.raises(SimulationResourceLimit, match="resource_limit:game_log"):
        budget.before_clone()


def test_monotonic_deadline():
    now = [0]
    budget = ResourceBudget(dict(RESOURCE_LIMITS, deadline_seconds=10), clock=lambda: now[0])
    now[0] = 10
    with pytest.raises(SimulationResourceLimit, match="resource_limit:deadline"):
        budget.check_deadline()


def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        ResourceBudget(dict(RESOURCE_LIMITS, deadline_seconds=-1))


def test_resource_error_is_not_swallowed_by_progress_callback():
    snapshots = []
    repo = SimpleNamespace(save_snapshot=lambda *args: snapshots.append(args))

    def fail_progress(done, total):
        raise SimulationResourceLimit("result_json")

    # Internal protocol test, not a valid API tick range or native-game certificate.
    deck = [{"quantity": 60, "card_name": "Island"}]
    with pytest.raises(SimulationResourceLimit, match="resource_limit:result_json"):
        AnalyticsService(repo).run_batch(deck, deck, matches=1, max_ticks=0,
                                       progress_callback=fail_progress)
    assert not snapshots


def admission_policy():
    from fastapi import HTTPException
    # Execute the actual admission function without importing main or opening SQL.
    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_start_batch_job")
    state = dict(_reap_simulation_workers=lambda: None, json=json, HTTPException=HTTPException,
                 SimulationResourceLimit=SimulationResourceLimit,
                 checked_json=checked_json, RESOURCE_LIMITS=RESOURCE_LIMITS,
                 SIM_JOBS={}, SIM_JOB_CANCEL_EVENTS={}, SIM_JOB_WORKERS={}, SIM_SHUTTING_DOWN=False,
                 SIM_JOBS_LOCK=threading.Lock(), SIM_WORK_SLOT=threading.BoundedSemaphore(1))
    exec(compile(ast.Module(body=[node], type_ignores=[]), "actual-admission-policy", "exec",
                 flags=__future__.annotations.compiler_flag), state)
    return state


def test_new_oversized_request_leaves_admission_maps_and_slot_unchanged():
    from fastapi import HTTPException
    state = admission_policy()
    calls = []
    request = {"padding": chr(0x1F600) * (RESOURCE_LIMITS["request_json_bytes"] // 12 + 1)}
    payload = SimpleNamespace(model_dump=lambda **kwargs: request)
    repo = SimpleNamespace(get_simulation_job=lambda key: None,
                           count_simulation_jobs=lambda: calls.append("count"))
    with pytest.raises(HTTPException) as caught:
        state["_start_batch_job"](payload, repo, "new-key")
    assert caught.value.status_code == 413
    assert caught.value.detail == dict(code="simulation_request_too_large",
                                      limit=RESOURCE_LIMITS["request_json_bytes"], dimension="request_json")
    assert calls == []
    assert state["SIM_JOBS"] == state["SIM_JOB_CANCEL_EVENTS"] == state["SIM_JOB_WORKERS"] == {}
    assert state["SIM_WORK_SLOT"].acquire(blocking=False)
    state["SIM_WORK_SLOT"].release()


def test_existing_legacy_oversized_request_replay_is_not_erased():
    state = admission_policy()
    request = {"padding": "x" * (RESOURCE_LIMITS["request_json_bytes"] + 1)}
    original = dict(status="completed", request=request)
    state["SIM_JOBS"]["legacy"] = original
    payload = SimpleNamespace(model_dump=lambda **kwargs: request)
    repo = SimpleNamespace(get_simulation_job=lambda key: None)
    assert state["_start_batch_job"](payload, repo, "legacy") == {"job_id": "legacy", "status": "completed"}
    assert state["SIM_JOBS"]["legacy"] is original


def test_shutdown_fence_precedes_even_oversized_new_request():
    from fastapi import HTTPException
    state = admission_policy()
    state.update(SIM_SHUTTING_DOWN=True, HTTPException=HTTPException)
    request = {"padding": "x" * (RESOURCE_LIMITS["request_json_bytes"] + 1)}
    payload = SimpleNamespace(model_dump=lambda **kwargs: request)
    with pytest.raises(HTTPException) as caught:
        state["_start_batch_job"](payload, object(), None)
    assert caught.value.status_code == 503
    assert state["SIM_JOBS"] == state["SIM_JOB_CANCEL_EVENTS"] == state["SIM_JOB_WORKERS"] == {}


@pytest.mark.parametrize("case,expected", [("oversized_result", "resource_limit:result_json"),
                                         ("oversized_error", "resource_limit:error"),
                                         ("bounded", None)])
def test_actual_worker_failure_envelope_uses_bounded_persistence(case, expected):
    from contextlib import nullcontext
    import time
    from persistence.repository import Repository

    class SessionSpy:
        def get(self, *args):
            return None
        def add(self, row):
            rows.append(row)
        def commit(self):
            pass
        def refresh(self, row):
            pass

    class Service:
        def __init__(self, repo):
            pass
        def run_batch(self, *args, **kwargs):
            if case == "oversized_error":
                raise ValueError("x" * 1025)
            return {"padding": "x" * 1048577} if case == "oversized_result" else {"ok": True}

    tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text())
    start = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_start_batch_job")
    runner = next(n for n in start.body if isinstance(n, ast.FunctionDef) and n.name == "_runner")
    rows = []
    repo = Repository(SessionSpy())
    job = dict(job_id="j", status="queued", request={}, result=None)
    slot = threading.BoundedSemaphore(1)
    assert slot.acquire(blocking=False)
    state = dict(SIM_JOBS={"j": job}, SIM_JOBS_LOCK=threading.Lock(),
                 SIM_JOB_CANCEL_EVENTS={"j": threading.Event()}, SIM_WORK_SLOT=slot,
                 job_id="j", cancel_event=threading.Event(), deck_a=[], deck_b=[],
                 payload=SimpleNamespace(matches=1, difficulty="casual", max_ticks=500),
                 Session=lambda engine: nullcontext(None), engine=None,
                 Repository=lambda session: repo, AnalyticsService=Service,
                 _persist_job=repo.save_simulation_job, _prune_simulation_jobs=lambda: None,
                 SimulationCancelled=type("SimulationCancelled", (Exception,), {}),
                 SimulationResourceLimit=SimulationResourceLimit, checked_text=checked_text,
                 RESOURCE_LIMITS=RESOURCE_LIMITS, time=time)
    exec(compile(ast.Module(body=[runner], type_ignores=[]), "actual-worker-envelope", "exec"), state)
    state["_runner"]()
    assert job["status"] == ("failed" if expected else "completed")
    assert job.get("error") == expected
    assert job["result"] == (None if expected else {"ok": True})
    assert rows[-1].status == job["status"] and rows[-1].error == expected
    assert state["SIM_JOB_CANCEL_EVENTS"] == {}
    assert slot.acquire(blocking=False)
    slot.release()


def test_diagnostics_deadline_before_first_pair_and_snapshot(monkeypatch):
    import analytics.service as service
    monkeypatch.setattr(service, "RESOURCE_LIMITS", dict(RESOURCE_LIMITS, deadline_seconds=0))
    snapshots = []
    repo = SimpleNamespace(save_snapshot=lambda *args: snapshots.append(args))
    with pytest.raises(SimulationResourceLimit, match="resource_limit:deadline"):
        AnalyticsService(repo).run_ai_diagnostics([{}, {}])
    assert snapshots == []


def test_result_preflight_rejects_before_a_writer():
    budget = ResourceBudget(dict(RESOURCE_LIMITS, result_json_bytes=20))
    with pytest.raises(SimulationResourceLimit, match="resource_limit:result_json"):
        budget.checked_result({"padding": "x" * 30})
