"""Pure actual admission function with schema-valid payload and trusted low policy."""
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from analytics.schemas import BatchSimulationRequest
from analytics.resource_budget import RESOURCE_LIMITS, SimulationResourceLimit
from test_resource_budget import admission_policy


@pytest.mark.parametrize("key", [None, "new-resource-key"])
def test_oversized_new_request_returns_413_without_admission_mutation(key):
    state = admission_policy()
    state.update(HTTPException=HTTPException, SimulationResourceLimit=SimulationResourceLimit,
                 RESOURCE_LIMITS=dict(RESOURCE_LIMITS, request_json_bytes=128))
    # Real schema-valid canonical payload. Trusted test DATA reduces the cap only;
    # this is not a supported client/operator knob or a current API oversized-body proof.
    payload = BatchSimulationRequest(deck_a=[dict(card_name="Island", quantity=60)],
                                     deck_b=[dict(card_name="Plains", quantity=60)],
                                     matches=1, difficulty="casual", max_ticks=500)
    calls = []
    repo = SimpleNamespace(get_simulation_job=lambda key: None,
                           count_simulation_jobs=lambda: calls.append("count"))
    with pytest.raises(HTTPException) as caught:
        state["_start_batch_job"](payload, repo, key)
    assert caught.value.status_code == 413
    assert caught.value.detail == dict(code="simulation_request_too_large", limit=128,
                                      dimension="request_json")
    assert calls == []
    assert state["SIM_JOBS"] == state["SIM_JOB_CANCEL_EVENTS"] == state["SIM_JOB_WORKERS"] == {}
    assert state["SIM_WORK_SLOT"].acquire(blocking=False)
    state["SIM_WORK_SLOT"].release()
