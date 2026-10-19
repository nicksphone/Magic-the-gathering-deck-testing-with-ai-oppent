"""Synthetic protocol for a prospective frozen current-source producer epoch.

These are not matrix games. Final217 whole-source identity/qualification is
pending; no measured source or recorded header may be rewritten to older code.
"""
import json

from scripts import build_ai_log_priors as builder
from tests.test_ai_native_training_export import reseal, run_export
from tests.test_ai_native_training_export_current_layout import (
    _bind_producer, _capsule_path, _write_capsule,
)
from tests.test_ai_native_training_export_replay_v2 import _replay_v2_packet


PROSPECTIVE_MEASURED_PRODUCER_TUPLE = {
    "scripts/matchup_round_robin.py":
        "8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
    "scripts/regression_matrix_replay.py":
        "d29588861eb7a471ae3616fd79a4591c4b56050cc4ef9d1fe9db0e7ee3228b10",
    "scripts/build_ai_log_priors.py":
        "1c9ecff41a97544329d81ac1188b7cb345ad491fac1159a31b7b4e48a25b64e2",
}


def _current_source_packet(tmp_path):
    packet = _replay_v2_packet(tmp_path)
    _bind_producer(packet, PROSPECTIVE_MEASURED_PRODUCER_TUPLE)
    reseal(packet)
    return packet


def test_current_producer_reader_epoch_exports_raw_without_rewriting_recorded_source(tmp_path):
    packet = _current_source_packet(tmp_path)
    header_before = packet["contract"].read_bytes()
    assert json.loads(header_before)["source_binding"]["backend_files"]["scripts/build_ai_log_priors.py"] == (
        "1c9ecff41a97544329d81ac1188b7cb345ad491fac1159a31b7b4e48a25b64e2")
    before = {path: path.read_bytes() for path in packet["root"].rglob("*.json")}
    assert run_export(packet) == {
        "status": "exported_private_training", "games": 110,
        "priors_saved": False, "task33_complete": False,
    }
    records = list(builder._training_records(packet["destination"], examples=False))
    assert len(records) == 110
    assert [row["log"] for _, row in records] == packet["logs"]
    assert all(row["game"] == "game-01.json" and row["seed"] is None for _, row in records)
    assert packet["contract"].read_bytes() == header_before
    assert before == {path: path.read_bytes() for path in before}
    contexts, unavailable = builder._qualified_export_contexts(packet["destination"])
    assert unavailable == {}
    assert contexts["samples"]["games"] == 110
    assert contexts["cards"]["protocol token"]["casts"] == 330


def test_current_producer_reader_epoch_rejects_conflicting_physical_context(tmp_path):
    packet = _current_source_packet(tmp_path)
    capsule = json.loads(_capsule_path(packet, 0).read_bytes())
    trace = json.loads(capsule["raw_log"][0].removeprefix("AI TRACE "))
    assert trace["pid"] == 1 and trace["opponent_archetype"] == "Control"
    trace["opponent_archetype"] = "Aggro"
    capsule["raw_log"][0] = "AI TRACE " + json.dumps(trace, separators=(",", ":"))
    _write_capsule(packet, 0, capsule)
    reseal(packet)
    header_before = packet["contract"].read_bytes()
    before = {path: path.read_bytes() for path in packet["root"].rglob("*.json")}
    assert run_export(packet)["status"] == "unavailable"
    assert not packet["destination"].exists()
    assert packet["contract"].read_bytes() == header_before
    assert before == {path: path.read_bytes() for path in before}
