"""Synthetic native-format protocol fixtures, NOT games or learned data."""
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

import pytest

from ai.log_priors import build_priors_from_logs
from scripts import build_ai_log_priors as builder


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def protocol_packet(tmp_path):
    root = tmp_path / "closed-protocol-envelope"
    root.mkdir()
    metrics = ("missed_land_drops", "unused_mana_passes", "lethal_misses", "bad_blocks",
               "stall_streaks", "redundant_removal_casts")
    binding = {"schema_version": 1, "source_base_commit": "7" * 40,
               "backend_files": {"scripts/matchup_round_robin.py":
                   "9061cc3b92c136a6d44bd3bb9b3ecef3297dde125f04e18ccb36e49cabb0775b"}}
    binding["backend_sha256"] = digest(binding["backend_files"])
    contract = {"schema_version": 2, "mode": "matrix", "source_root": str(tmp_path / "source"),
        "source_binding": binding, "harness_files": {k: "1" * 64 for k in
            ("matrix_policy.py", "parent_matrix_harness.py", "parent_matrix_launch.py")},
        "runtime_inventory": {"directories": ["/protocol/runtime"], "files": {"/protocol/runtime/x.py": "2" * 64}},
        "fixtures": {**{k: "/protocol/" + k for k in ("raw155", "rulings", "provenance")},
                     **{k + "_sha256": "3" * 64 for k in ("raw155", "rulings", "provenance")}},
        "limits": {"deadline_seconds": 100}, "package_origin": "/protocol/packages",
        "parity_receipt": "/protocol/parity.json", "parity_receipt_sha256": "4" * 64}
    decks = [{"name": f"Protocol deck {i:02d}", "classification_status": "resolved",
              "archetype": "Aggro" if i % 2 else "Control", "mainboard": [{"quantity": 60}],
              "sideboard": []} for i in range(11)]
    export = {"schema_version": 1, "source_commit": "4" * 40, "decks": decks,
              "decks_sha256": digest(decks), "sideboard_mode": "fixed_no_swaps"}
    closure = {"source_base_commit": binding["source_base_commit"], "binding_sha256": digest(binding),
               "before_sha256": binding["backend_sha256"], "after_sha256": binding["backend_sha256"],
               "equal": True, "ordinary_files": 1}
    manifest = {"export_sha256": digest(export), "input_export_base_commit": export["source_commit"],
        "source_base_commit": binding["source_base_commit"], "source_binding_sha256": digest(binding),
        "backend_before_sha256": binding["backend_sha256"], "sideboard_mode": "fixed_no_swaps",
        "difficulty": "master", "max_ticks": 200, "limits": contract["limits"], "seeds": [12],
        "planned_series": 110, "planned_pairs": 55,
        "source_scope": "explicit current ordinary backend binding; file provenance, not live CodeRef authority",
        "roster": [{"name": d["name"], "classification_status": d["classification_status"],
                    "archetype": d["archetype"], "content_sha256": digest(d),
                    "mainboard_cards": 60, "sideboard_cards": 0} for d in decks]}
    series, logs = [], []
    for a, b in combinations(decks, 2):
        for seat in (1, 2):
            k = len(series)
            context = "Aggro" if k % 2 else "Control"
            raw = []
            for index in range(3):
                trace = {"pid": seat, "player_name": f"Player {'A' if seat == 1 else 'B'}",
                    "turn": 2 if context == "Aggro" else 8, "action_index": index,
                    "opp_archetype": context, "opponent_context_scope": "predeclared_offline_benchmark",
                    "action": {"type": "cast_spell", "card_name": "Protocol Token"}, "hand": []}
                raw += ["AI TRACE " + json.dumps(trace, separators=(",", ":")),
                        trace["player_name"] + " casts/activates Protocol Token."]
            result = {"winner": 1, "turn": 8, "ticks": 3, "log_hash": "5" * 64,
                      "log": raw, "timeout": False, "starting_player": 1}
            raw_bytes = json.dumps(raw, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
            receipt = {"reference": "game-01.json", "complete": True, "bytes": len(raw_bytes),
                       "raw_sha256": sha256(raw_bytes).hexdigest()}
            path = root / f"runtime/games/series-{k:05d}/game-01.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(canonical({"schema_version": 1, "result": result, "raw_log": raw,
                                       "raw_sha256": receipt["raw_sha256"]}))
            quality = {"counts": {pid: dict.fromkeys(metrics, 0) for pid in ("1", "2")},
                       "availability": {pid: dict.fromkeys(metrics, True) for pid in ("1", "2")}}
            game = {**{key: value for key, value in result.items() if key != "log"},
                    "seed": 123, "evidence": receipt, "evidence_complete": True, "quality": quality}
            series.append({"deck_a": a["name"], "deck_b": b["name"], "deck_a_seat": seat,
                "seat_one": a["name"] if seat == 1 else b["name"],
                "seat_two": b["name"] if seat == 1 else a["name"], "seed_token": 12,
                "root_seed": 456, "sideboard_mode": "fixed_no_swaps", "status": "resolved", "games": [game]})
            logs.append(raw)
    summary = {"schema_version": 1, "manifest": manifest, "measured_source": closure,
               "complete": True, "status": "completed_schedule", "attempted_series": 110,
               "not_run_series": 0, "pairs": [], "series": series}
    contract_path = tmp_path / "contract.json"
    contract_path.write_bytes(canonical(contract))
    parent = {"contract_sha256": sha256(contract_path.read_bytes()).hexdigest(),
              "actual_launch": True, "returncode": 0, "closed": True, "timeout": False}
    child = {"status": "completed_schedule", "complete": True, "attempted_series": 110,
             "not_run_series": 0, "source_equal": True, "measured_source": closure,
             "closed": True, "sql_handles": 7, "live_threads": 0}
    values = {"parent-outcome.json": parent, "runtime/outcome.json": child,
              "runtime/matrix-summary.json": summary, "runtime/prepared-boards.json": export}
    for relative, value in values.items():
        (root / relative).write_bytes(canonical(value))
    packet = {"root": root, "contract": contract_path, "inventory": tmp_path / "sealed-files.json",
              "destination": tmp_path / "private-training", "values": values, "logs": logs,
              "expected_source_base": binding["source_base_commit"],
              "expected_backend_sha256": binding["backend_sha256"],
              "expected_contract_sha256": parent["contract_sha256"]}
    reseal(packet)
    return packet


def reseal(packet):
    for relative, value in packet["values"].items():
        (packet["root"] / relative).write_bytes(canonical(value))
    files = {p.relative_to(packet["root"]).as_posix(): sha256(p.read_bytes()).hexdigest()
             for p in packet["root"].rglob("*.json")}
    packet["inventory"].write_bytes(canonical({"schema_version": 1, "files": files}))
    packet["expected_inventory_sha256"] = sha256(packet["inventory"].read_bytes()).hexdigest()


def run_export(packet):
    return builder._export_native_matrix_training(**{k: v for k, v in packet.items()
        if k not in ("values", "logs")})


def test_native_export_preserves_raw_identity_seed_and_aggregate(tmp_path):
    p = protocol_packet(tmp_path)
    before = {f: f.read_bytes() for f in p["root"].rglob("*.json")}
    report = run_export(p)
    assert report["status"] == "exported_private_training"
    assert report["games"] == 110 and report["priors_saved"] is False
    records = list(builder._training_records(p["destination"], examples=False))
    assert len(records) == 110
    assert all(row["game"] == "game-01.json" and row["seed"] is None for _, row in records)
    assert [row["log"] for _, row in records] == p["logs"]
    assert before == {f: f.read_bytes() for f in before}
    assert canonical(build_priors_from_logs(p["logs"])) == canonical(build_priors_from_logs(
        builder._read_training_run_logs(p["destination"])))
    contexts, unavailable = builder._qualified_export_contexts(p["destination"])
    assert unavailable == {}
    assert contexts["cards"]["protocol token"]["opponent_archetypes"]["aggro"]["casts"] == 165
    assert (p["destination"].stat().st_mode & 0o777) == 0o700
    assert all((path.stat().st_mode & 0o777) == 0o600 for path, _ in records)


@pytest.mark.parametrize("which,key,value", [
    ("parent-outcome.json", "actual_launch", False), ("parent-outcome.json", "returncode", False),
    ("parent-outcome.json", "closed", False), ("parent-outcome.json", "timeout", True),
    ("runtime/outcome.json", "complete", False), ("runtime/outcome.json", "source_equal", False),
    ("runtime/outcome.json", "live_threads", 1), ("runtime/outcome.json", "closed", False),
    ("runtime/matrix-summary.json", "attempted_series", 109),
    ("runtime/matrix-summary.json", "not_run_series", 1),
    ("runtime/matrix-summary.json", "status", "stopped"),
    ("runtime/matrix-summary.json", "complete", 1),
])
def test_incomplete_execution_does_not_export(tmp_path, which, key, value):
    p = protocol_packet(tmp_path)
    p["values"][which][key] = value
    reseal(p)
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


@pytest.mark.parametrize("mutation", ["raw", "reference", "bytes", "complete", "duplicate", "quality",
    "closure", "export", "source_epoch", "contract_pin", "inventory_pin", "missing_seal", "extra_game"])
def test_bad_native_receipt_or_binding_cannot_qualify(tmp_path, mutation):
    p = protocol_packet(tmp_path)
    summary = p["values"]["runtime/matrix-summary.json"]
    game = summary["series"][0]["games"][0]
    if mutation == "raw": game["evidence"]["raw_sha256"] = "0" * 64
    elif mutation == "reference": game["evidence"]["reference"] = "../game-01.json"
    elif mutation == "bytes": game["evidence"]["bytes"] = True
    elif mutation == "complete": game["evidence"]["complete"] = False
    elif mutation == "duplicate": summary["series"][0]["games"].append(deepcopy(game))
    elif mutation == "quality": game["quality"]["availability"]["2"]["bad_blocks"] = False
    elif mutation == "closure": summary["measured_source"]["after_sha256"] = "0" * 64
    elif mutation == "export": summary["manifest"]["export_sha256"] = "0" * 64
    elif mutation == "source_epoch": p["expected_source_base"] = "8" * 40
    elif mutation == "contract_pin": p["expected_contract_sha256"] = "0" * 64
    elif mutation == "extra_game":
        path = p["root"] / "runtime/games/series-00000/game-02.json"
        path.write_bytes((path.with_name("game-01.json")).read_bytes())
    reseal(p)
    if mutation == "inventory_pin": p["expected_inventory_sha256"] = "0" * 64
    if mutation == "missing_seal":
        seal = json.loads(p["inventory"].read_bytes())
        seal["files"].pop("runtime/games/series-00000/game-01.json")
        p["inventory"].write_bytes(canonical(seal))
        p["expected_inventory_sha256"] = sha256(p["inventory"].read_bytes()).hexdigest()
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


def test_native_cli_missing_header_never_opens_sql_or_saves_prior(tmp_path, capsys):
    builder.main(["--native-root", str(tmp_path / "absent")])
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "unavailable" and report["priors_saved"] is False


def test_native_cli_exports_private_packet_without_saving_priors(tmp_path, capsys):
    p = protocol_packet(tmp_path)
    args = [item for key in ("root", "contract", "inventory", "destination", "expected_source_base",
                            "expected_backend_sha256", "expected_contract_sha256", "expected_inventory_sha256")
            for item in ["--" + ({"root": "native-root", "contract": "native-contract",
                                  "inventory": "native-inventory", "destination": "export-training-root"}
                                 .get(key, key.replace("_", "-"))), str(p[key])]]
    builder.main(args)
    assert json.loads(capsys.readouterr().out)["status"] == "exported_private_training"
    assert (p["destination"] / "series-00000/games.jsonl").exists()


@pytest.mark.parametrize("key,value", [("ticks", True), ("ticks", []), ("ticks", 201),
    ("turn", 10**400), ("turn", False), ("winner", True), ("starting_player", 3), ("timeout", 0)])
def test_malformed_result_even_with_consistent_receipts_is_unavailable(tmp_path, key, value):
    p = protocol_packet(tmp_path)
    path = p["root"] / "runtime/games/series-00000/game-01.json"
    capsule = json.loads(path.read_bytes())
    capsule["result"][key] = value
    path.write_bytes(canonical(capsule))
    p["values"]["runtime/matrix-summary.json"]["series"][0]["games"][0][key] = value
    reseal(p)
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


def test_capsule_whole_byte_seal_required_not_just_raw_receipt(tmp_path):
    p = protocol_packet(tmp_path)
    path = p["root"] / "runtime/games/series-00000/game-01.json"
    capsule = json.loads(path.read_bytes())
    capsule["result"]["winner"] = 2
    path.write_bytes(canonical(capsule))
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


def test_existing_destination_is_never_modified(tmp_path):
    p = protocol_packet(tmp_path)
    p["destination"].mkdir()
    marker = p["destination"] / "existing.txt"
    marker.write_text("keep")
    assert run_export(p)["status"] == "unavailable"
    assert marker.read_text() == "keep"


def test_native_symlink_member_cannot_qualify(tmp_path):
    p = protocol_packet(tmp_path)
    path = p["root"] / "runtime/games/series-00000/game-01.json"
    outside = tmp_path / "outside.json"
    path.rename(outside)
    path.symlink_to(outside)
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


def test_private_write_failure_leaves_no_partial_training_export(tmp_path, monkeypatch):
    import os
    p = protocol_packet(tmp_path)
    def fail(fd):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(os, "fsync", fail)
    assert run_export(p)["status"] == "unavailable"
    assert not p["destination"].exists()


@pytest.mark.parametrize("missing", ["context", "index"])
def test_no_context_or_index_is_not_inferred_from_manifest_or_position(tmp_path, missing):
    p = protocol_packet(tmp_path)
    for index, series in enumerate(p["values"]["runtime/matrix-summary.json"]["series"]):
        path = p["root"] / f"runtime/games/series-{index:05d}/game-01.json"
        capsule = json.loads(path.read_bytes())
        raw = capsule["raw_log"]
        for i in range(0, len(raw), 2):
            trace = json.loads(raw[i].split("AI TRACE ", 1)[1])
            trace.pop("opp_archetype" if missing == "context" else "action_index")
            raw[i] = "AI TRACE " + json.dumps(trace, separators=(",", ":"))
        encoded = json.dumps(raw, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
        capsule["raw_sha256"] = sha256(encoded).hexdigest()
        path.write_bytes(canonical(capsule))
        series["games"][0]["evidence"].update(raw_sha256=capsule["raw_sha256"], bytes=len(encoded))
    reseal(p)
    assert run_export(p)["status"] == "exported_private_training"
    contexts, unavailable = builder._qualified_export_contexts(p["destination"])
    assert not contexts["cards"] and unavailable
    assert all(row["seed"] is None for _, row in builder._training_records(p["destination"], examples=False))
