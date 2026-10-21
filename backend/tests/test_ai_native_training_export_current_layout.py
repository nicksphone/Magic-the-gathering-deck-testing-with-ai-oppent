"""Synthetic current-layout envelope protocol, NOT games or eligible training data.

The three producer hashes come from Jason's frozen f277 composition. The test
envelope, runtime/harness seals, results and metric counts remain synthetic.
"""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts import build_ai_log_priors as builder
from tests.test_ai_native_training_export import (
    canonical, digest, protocol_packet, reseal, run_export,
)


CURRENT_PRODUCER_TUPLE = {
    "scripts/matchup_round_robin.py":
        "8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
    "scripts/regression_matrix_replay.py":
        "d447992fb786b37d1a37174cc3c7b8693b196dda5072cf0ac247173053adb298",
    "scripts/build_ai_log_priors.py":
        "68f2d13b6922d4329f9f1a3c9d0064c47cf6933bce94434ecb66f7592cbf2fb7",
}


def _summary(packet):
    return packet["values"]["runtime/matrix-summary.json"]


def _bind_producer(packet, files):
    header = json.loads(packet["contract"].read_bytes())
    binding = header["source_binding"]
    binding["backend_files"] = deepcopy(files)
    binding["backend_sha256"] = digest(files)
    packet["expected_backend_sha256"] = binding["backend_sha256"]
    packet["contract"].write_bytes(canonical(header))
    packet["expected_contract_sha256"] = sha256(packet["contract"].read_bytes()).hexdigest()
    packet["values"]["parent-outcome.json"]["contract_sha256"] = packet["expected_contract_sha256"]
    closure = {
        "source_base_commit": binding["source_base_commit"],
        "binding_sha256": digest(binding),
        "before_sha256": binding["backend_sha256"],
        "after_sha256": binding["backend_sha256"],
        "equal": True,
        "ordinary_files": len(files),
    }
    for relative in ("runtime/outcome.json", "runtime/matrix-summary.json"):
        packet["values"][relative]["measured_source"] = deepcopy(closure)
    manifest = _summary(packet)["manifest"]
    manifest["source_binding_sha256"] = digest(binding)
    manifest["backend_before_sha256"] = binding["backend_sha256"]


def _capsule_path(packet, index):
    return packet["root"] / f"runtime/games/series-{index:05d}/game-01.json"


def _write_capsule(packet, index, capsule):
    raw = capsule["raw_log"]
    encoded = json.dumps(raw, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
    capsule["raw_sha256"] = sha256(encoded).hexdigest()
    capsule["result"]["log"] = deepcopy(raw)
    _capsule_path(packet, index).write_bytes(canonical(capsule))
    _summary(packet)["series"][index]["games"][0]["evidence"].update(
        bytes=len(encoded), raw_sha256=capsule["raw_sha256"])
    packet["logs"][index] = deepcopy(raw)


def _rewrite_traces(packet, change):
    for index, series in enumerate(_summary(packet)["series"]):
        capsule = json.loads(_capsule_path(packet, index).read_bytes())
        for ordinal in range(0, len(capsule["raw_log"]), 2):
            trace = json.loads(capsule["raw_log"][ordinal].removeprefix("AI TRACE "))
            change(trace, series)
            capsule["raw_log"][ordinal] = "AI TRACE " + json.dumps(trace, separators=(",", ":"))
        _write_capsule(packet, index, capsule)


def _remove_context(trace, series):
    trace.pop("opp_archetype", None)
    trace.pop("opponent_archetype", None)


def _mark_unresolved(packet, name):
    export = packet["values"]["runtime/prepared-boards.json"]
    deck = next(row for row in export["decks"] if row["name"] == name)
    deck["classification_status"] = "unknown"
    export["decks_sha256"] = digest(export["decks"])
    manifest = _summary(packet)["manifest"]
    manifest["export_sha256"] = digest(export)
    row = next(row for row in manifest["roster"] if row["name"] == name)
    row["classification_status"] = "unknown"
    row["content_sha256"] = digest(deck)


def _current_packet(tmp_path):
    packet = protocol_packet(tmp_path)
    _bind_producer(packet, CURRENT_PRODUCER_TUPLE)
    # Deliberately opposite to the old exported labels: only this actual-agent
    # configuration map, not export.archetype, may bind a known trace context.
    effective = {f"Protocol deck {i:02d}": "Control" if i % 2 else "Aggro" for i in range(11)}
    _summary(packet)["manifest"]["effective_archetypes"] = effective

    def bind(trace, series):
        trace.pop("opp_archetype")
        opponent = series["seat_two"] if trace["pid"] == 1 else series["seat_one"]
        trace["opponent_archetype"] = effective[opponent]

    _rewrite_traces(packet, bind)
    reseal(packet)
    return packet


def test_current_tuple_exports_exact_raw_without_claiming_data_or_rebuild(tmp_path):
    packet = _current_packet(tmp_path)
    # The producer-reader hash is not the executing consumer's future hash;
    # unrelated bound files may differ without weakening their supplied seals.
    files = dict(CURRENT_PRODUCER_TUPLE, **{"protocol/unrelated.py": "6" * 64})
    _bind_producer(packet, files)
    reseal(packet)
    before = {path: path.read_bytes() for path in packet["root"].rglob("*.json")}
    report = run_export(packet)
    assert report == {"status": "exported_private_training", "games": 110,
                      "priors_saved": False, "task33_complete": False}
    records = list(builder._training_records(packet["destination"], examples=False))
    assert len(records) == 110
    assert [row["log"] for _, row in records] == packet["logs"]
    assert all(row["game"] == "game-01.json" and row["seed"] is None for _, row in records)
    assert before == {path: path.read_bytes() for path in before}
    assert packet["destination"].stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path, _ in records)
    contexts, unavailable = builder._qualified_export_contexts(packet["destination"])
    assert unavailable == {}
    assert contexts["samples"]["games"] == 110
    assert contexts["cards"]["protocol token"]["casts"] == 330


@pytest.mark.parametrize("pid", [1, 2], ids=["seat-one", "seat-two"])
def test_current_context_binds_physical_opponent_not_starting_player_or_export_label(tmp_path, pid):
    packet = _current_packet(tmp_path)

    def bind(trace, series):
        trace["pid"] = pid
        trace["player_name"] = "Player A" if pid == 1 else "Player B"
        opponent = series["seat_two"] if pid == 1 else series["seat_one"]
        trace["opponent_archetype"] = _summary(packet)["manifest"]["effective_archetypes"][opponent]

    _rewrite_traces(packet, bind)
    for index, series in enumerate(_summary(packet)["series"]):
        capsule = json.loads(_capsule_path(packet, index).read_bytes())
        capsule["result"]["starting_player"] = 3 - pid
        series["games"][0]["starting_player"] = 3 - pid
        for ordinal in range(1, len(capsule["raw_log"]), 2):
            capsule["raw_log"][ordinal] = ("Player A" if pid == 1 else "Player B") + " casts/activates Protocol Token."
        _write_capsule(packet, index, capsule)
    reseal(packet)
    assert run_export(packet)["status"] == "exported_private_training"
    records = list(builder._training_records(packet["destination"], examples=False))
    assert [row["log"] for _, row in records] == packet["logs"]
    contexts, unavailable = builder._qualified_export_contexts(packet["destination"])
    assert unavailable == {}
    assert contexts["samples"]["games"] == 110
    # Each physical seat faces every deck ten times; six Aggro/five Control
    # labels yield 60/50 games, with three independently indexed casts apiece.
    entry = contexts["cards"]["protocol token"]["opponent_archetypes"]
    assert entry["aggro"]["casts"] == 180
    assert entry["control"]["casts"] == 150


@pytest.mark.parametrize("missing", [
    "context", "unknown-map", "missing-map", "partial-map", "index", "unresolved",
])
def test_current_unknown_context_preserves_raw_and_reports_unavailable_learning(tmp_path, missing):
    packet = _current_packet(tmp_path)
    manifest = _summary(packet)["manifest"]
    if missing == "index":
        _rewrite_traces(packet, lambda trace, series: trace.pop("action_index"))
    elif missing == "unknown-map":
        manifest["effective_archetypes"] = dict.fromkeys(manifest["effective_archetypes"], "Unclassified")
        _rewrite_traces(packet, lambda trace, series: trace.update(opponent_archetype="Unclassified"))
    else:
        _rewrite_traces(packet, _remove_context)
        if missing == "missing-map":
            manifest.pop("effective_archetypes")
        elif missing == "partial-map":
            manifest["effective_archetypes"].pop("Protocol deck 00")
        elif missing == "unresolved":
            manifest["effective_archetypes"].pop("Protocol deck 00")
            _mark_unresolved(packet, "Protocol deck 00")
    reseal(packet)
    assert run_export(packet)["status"] == "exported_private_training"
    records = list(builder._training_records(packet["destination"], examples=False))
    assert [row["log"] for _, row in records] == packet["logs"]
    assert all(row["seed"] is None for _, row in records)
    contexts, unavailable = builder._qualified_export_contexts(packet["destination"])
    assert not contexts["cards"]
    assert contexts["samples"]["games"] == 0
    expected = "missing_action_provenance" if missing == "index" else "unassociated_or_unknown_log_context"
    assert unavailable == {expected: 330}


@pytest.mark.parametrize("member,value", [
    ("scripts/matchup_round_robin.py", "1df4d3a9bbc3c2553c61c256f10e5c7d2993015bef2012be1afa83b119b34d53"),
    ("scripts/matchup_round_robin.py", "a9f93516dccabaefa9881ea1fc98de814163e80a654a894eac5e8c209d64c9fb"),
    ("scripts/matchup_round_robin.py", "0" * 64),
    ("scripts/regression_matrix_replay.py", "0" * 64),
    ("scripts/build_ai_log_priors.py", "0" * 64),
], ids=["uncomposed-1df", "resource-only-a9f", "unknown-matrix", "mixed-replay", "mixed-producer-reader"])
def test_current_mixed_producer_tuples_do_not_export_even_when_resealed(tmp_path, member, value):
    packet = _current_packet(tmp_path)
    files = dict(CURRENT_PRODUCER_TUPLE)
    files[member] = value
    _bind_producer(packet, files)
    reseal(packet)
    assert run_export(packet)["status"] == "unavailable"
    assert not packet["destination"].exists()


@pytest.mark.parametrize("mutation", [
    "map-type", "map-value", "foreign-key", "known-without-map", "wrong-opponent", "conflicting-alias",
])
def test_current_contradictory_context_is_rejected_not_silently_dropped_or_substituted(tmp_path, mutation):
    packet = _current_packet(tmp_path)
    manifest = _summary(packet)["manifest"]
    if mutation == "map-type":
        manifest["effective_archetypes"] = []
    elif mutation == "map-value":
        manifest["effective_archetypes"]["Protocol deck 00"] = False
    elif mutation == "foreign-key":
        manifest["effective_archetypes"]["Not in the admitted roster"] = "Aggro"
    elif mutation == "known-without-map":
        manifest.pop("effective_archetypes")
    else:
        capsule = json.loads(_capsule_path(packet, 0).read_bytes())
        trace = json.loads(capsule["raw_log"][0].removeprefix("AI TRACE "))
        # Series zero: deck00 at physical one (Aggro), deck01 at two (Control).
        assert trace["pid"] == 1 and trace["opponent_archetype"] == "Control"
        if mutation == "wrong-opponent":
            trace["opponent_archetype"] = "Aggro"
        else:
            trace["opp_archetype"] = "Aggro"
        capsule["raw_log"][0] = "AI TRACE " + json.dumps(trace, separators=(",", ":"))
        _write_capsule(packet, 0, capsule)
    reseal(packet)
    assert run_export(packet)["status"] == "unavailable"
    assert not packet["destination"].exists()


@pytest.mark.parametrize("mutation", [
    "whole-capsule-seal", "short-schedule", "bad-blocks-unavailable", "missing-metric", "bool-count", "source-after",
])
def test_current_layout_retains_full_seals_schedule_six_metrics_and_source_closure(tmp_path, mutation):
    packet = _current_packet(tmp_path)
    summary = _summary(packet)
    quality = summary["series"][0]["games"][0]["quality"]
    if mutation == "short-schedule":
        summary["attempted_series"] = 109
    elif mutation == "bad-blocks-unavailable":
        quality["availability"]["2"]["bad_blocks"] = False
    elif mutation == "missing-metric":
        quality["counts"]["1"].pop("redundant_removal_casts")
    elif mutation == "bool-count":
        quality["counts"]["1"]["bad_blocks"] = False
    elif mutation == "source-after":
        summary["measured_source"]["after_sha256"] = "0" * 64
    reseal(packet)
    if mutation == "whole-capsule-seal":
        inventory = json.loads(packet["inventory"].read_bytes())
        inventory["files"].pop("runtime/games/series-00000/game-01.json")
        packet["inventory"].write_bytes(canonical(inventory))
        packet["expected_inventory_sha256"] = sha256(packet["inventory"].read_bytes()).hexdigest()
    assert run_export(packet)["status"] == "unavailable"
    assert not packet["destination"].exists()
