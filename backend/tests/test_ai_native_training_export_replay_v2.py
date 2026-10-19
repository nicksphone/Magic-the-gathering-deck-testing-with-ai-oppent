"""Synthetic exporter protocol for the reviewed replay-v2 tuple, NOT games.

The replay postimage has separate parent-qualified native20 evidence. These
synthetic envelopes do not transfer that evidence or constitute eligible data.
"""
import json

from scripts import build_ai_log_priors as builder
from tests.test_ai_native_training_export import reseal, run_export
from tests.test_ai_native_training_export_current_layout import (
    _bind_producer, _capsule_path, _current_packet, _write_capsule,
)


REVIEWED_REPLAY_V2_PRODUCER_TUPLE = {
    "scripts/matchup_round_robin.py":
        "8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
    "scripts/regression_matrix_replay.py":
        "d29588861eb7a471ae3616fd79a4591c4b56050cc4ef9d1fe9db0e7ee3228b10",
    "scripts/build_ai_log_priors.py":
        "68f2d13b6922d4329f9f1a3c9d0064c47cf6933bce94434ecb66f7592cbf2fb7",
}


def _replay_v2_packet(tmp_path):
    packet = _current_packet(tmp_path)
    _bind_producer(packet, REVIEWED_REPLAY_V2_PRODUCER_TUPLE)
    reseal(packet)
    return packet


def test_reviewed_replay_v2_exports_exact_raw_without_rewriting_producer_identity(tmp_path):
    packet = _replay_v2_packet(tmp_path)
    before = {path: path.read_bytes() for path in packet["root"].rglob("*.json")}
    header_before = packet["contract"].read_bytes()
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


def test_reviewed_replay_v2_rejects_conflicting_physical_opponent_context(tmp_path):
    packet = _replay_v2_packet(tmp_path)
    capsule = json.loads(_capsule_path(packet, 0).read_bytes())
    trace = json.loads(capsule["raw_log"][0].removeprefix("AI TRACE "))
    assert trace["pid"] == 1 and trace["opponent_archetype"] == "Control"
    trace["opponent_archetype"] = "Aggro"
    capsule["raw_log"][0] = "AI TRACE " + json.dumps(trace, separators=(",", ":"))
    _write_capsule(packet, 0, capsule)
    reseal(packet)
    before = {path: path.read_bytes() for path in packet["root"].rglob("*.json")}
    assert run_export(packet)["status"] == "unavailable"
    assert not packet["destination"].exists()
    assert before == {path: path.read_bytes() for path in before}
