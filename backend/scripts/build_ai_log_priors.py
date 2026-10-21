from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import json
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from ai.log_priors import (_cast_context, _opponent_archetype, build_priors_from_examples,
                           build_priors_from_logs, save_log_priors)


def _training_records(root: Path, *, examples: bool):
    if not root.exists():
        return
    for path in sorted(root.rglob("*.jsonl")):
        if not any(name in path.name for name in (("training_examples", "examples") if examples else ("games",))):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if isinstance(row, dict):
                yield path, row


def _read_training_run_logs(root: Path) -> list[list[str]]:
    return [[str(item) for item in row["log"]] for _, row in _training_records(root, examples=False)
            if isinstance(row.get("log"), list) and row["log"]]


def _read_training_run_examples(root: Path) -> list[dict]:
    return [row for _, row in _training_records(root, examples=True)
            if row.get("board_role_hint") and row.get("action_type")]


def _qualified_export_contexts(root: Path) -> tuple[dict, dict]:
    """Require explicit game/action provenance; never invent execution IDs."""
    import math
    candidates: dict[tuple, list[dict]] = {}
    unavailable = Counter()

    def record(path, row):
        context = _opponent_archetype(row)
        if context is None:
            unavailable["unknown_or_missing_context"] += 1
            return
        game, index = row.get("game"), row.get("action_index")
        if (type(game) not in (str, int) or game == "" or type(index) is not int or index < 0
                or type(row.get("pid")) is not int or row["pid"] not in (1, 2)
                or type(row.get("turn")) is not int or row["turn"] < 1):
            unavailable["missing_action_provenance"] += 1
            return
        try:
            math.isfinite(row["turn"])
        except OverflowError:
            unavailable["invalid_context_turn"] += 1
            return
        key = (str(path.parent.relative_to(root)), type(game).__name__, game, index)
        value = {"pid": row["pid"], "turn": row["turn"], "action_type": row["action_type"],
                 "action_card_name": row["action_card_name"].strip().lower(),
                 "opponent_archetype": context}
        candidates.setdefault(key, []).append(value)

    for path, game in _training_records(root, examples=False):
        pending = None
        for line in game.get("log", []) if isinstance(game.get("log"), list) else []:
            if not isinstance(line, str):
                continue
            if "AI TRACE " in line:
                pending = None
                try:
                    parsed = json.loads(line.split("AI TRACE ", 1)[1])
                    if isinstance(parsed, dict):
                        pending = parsed
                except (ValueError, IndexError):
                    pass
            elif " casts/activates " in line:
                actor, name = line.split(" casts/activates ", 1)
                name = name.strip().rstrip(".")
                context = _cast_context(pending, actor.strip(), name)
                if context is not None:
                    record(path, {"game": game.get("game"), "action_index": pending.get("action_index"),
                                  "pid": pending.get("pid"), "turn": pending.get("turn"),
                                  "action_type": pending["action"]["type"], "action_card_name": name,
                                  "opponent_archetype": context})
                else:
                    unavailable["unassociated_or_unknown_log_context"] += 1
                pending = None
    for path, row in _training_records(root, examples=True):
        if (isinstance(row.get("action_type"), str) and row["action_type"]
                and isinstance(row.get("action_card_name"), str) and row["action_card_name"].strip()):
            record(path, row)
    rows = []
    accepted_games = set()
    for identity, values in candidates.items():
        if any(value != values[0] for value in values[1:]):
            unavailable["conflicting_action_provenance"] += len(values)
        elif values[0]["action_type"] in {"cast_spell", "activate_ability"}:
            rows.append(values[0])
            accepted_games.add(identity[:-1])
    payload = build_priors_from_examples(rows)
    payload["samples"]["games"] = len(accepted_games)
    return payload, dict(sorted(unavailable.items()))


def _export_native_matrix_training(*, root: Path, contract: Path, inventory: Path,
                                  destination: Path, expected_source_base: str,
                                  expected_backend_sha256: str, expected_contract_sha256: str,
                                  expected_inventory_sha256: str) -> dict:
    """Explicit closed-matrix intake; hashes validate supplied proof, not its origin."""
    import hashlib
    import math
    import os
    import shutil
    from itertools import combinations
    from pathlib import PurePosixPath

    created = False

    def require(condition, reason):
        if not condition:
            raise ValueError(reason)

    def hex_string(value, length=64):
        return type(value) is str and len(value) == length and all(c in "0123456789abcdef" for c in value)

    def positive_finite_int(value):
        try:
            return type(value) is int and value >= 1 and math.isfinite(value)
        except OverflowError:
            return False

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

    def digest(value):
        return hashlib.sha256(canonical(value)).hexdigest()

    def ordinary(path):
        require(path.is_absolute() and path.resolve() == path
                and not any(p.is_symlink() for p in (path, *path.parents)), "nonordinary_native_path")

    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate_json_key")
            out[key] = value
        return out

    def parse(raw):
        def bad_constant(value):
            raise ValueError("nonfinite_json")
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
        require(type(value) is dict, "invalid_native_object")
        return value

    def sealed(relative):
        member = PurePosixPath(relative)
        require(type(relative) is str and not member.is_absolute() and ".." not in member.parts
                and member.as_posix() == relative and relative in files
                and hex_string(files[relative]), "missing_or_invalid_file_seal")
        path = root / relative
        ordinary(path)
        require(path.is_file(), "missing_native_member")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == files[relative], "native_file_seal_mismatch")
        return parse(raw)

    try:
        require(all(hex_string(v) for v in (expected_backend_sha256, expected_contract_sha256,
                    expected_inventory_sha256)) and hex_string(expected_source_base, 40), "missing_expected_epoch_or_seals")
        for path in (root, contract, inventory, destination):
            ordinary(path)
        require(root.is_dir() and not destination.exists() and destination.parent.is_dir(), "invalid_native_destination")
        require(not destination.is_relative_to(root) and not root.is_relative_to(destination), "native_destination_overlaps_input")
        raw_contract, raw_inventory = contract.read_bytes(), inventory.read_bytes()
        require(hashlib.sha256(raw_contract).hexdigest() == expected_contract_sha256
                and hashlib.sha256(raw_inventory).hexdigest() == expected_inventory_sha256, "input_seal_mismatch")
        header, seal = parse(raw_contract), parse(raw_inventory)
        require(type(seal.get("schema_version")) is int and seal["schema_version"] == 1
                and type(seal.get("files")) is dict, "invalid_sealed_inventory")
        files = seal["files"]
        require(type(header.get("schema_version")) is int and header["schema_version"] == 2
                and header.get("mode") == "matrix", "invalid_completed_matrix_header")
        require(all(k in header for k in ("source_root", "source_binding", "harness_files", "runtime_inventory",
                    "fixtures", "limits", "package_origin", "parity_receipt", "parity_receipt_sha256")), "incomplete_execution_header")
        source_root = Path(header["source_root"])
        ordinary(source_root)
        require(not destination.is_relative_to(source_root) and not source_root.is_relative_to(destination), "native_destination_overlaps_source")
        binding = header["source_binding"]
        require(type(binding) is dict and set(binding) == {"schema_version", "source_base_commit", "backend_files", "backend_sha256"}
                and type(binding["schema_version"]) is int and binding["schema_version"] == 1
                and binding["source_base_commit"] == expected_source_base
                and binding["backend_sha256"] == expected_backend_sha256
                and type(binding["backend_files"]) is dict and binding["backend_files"]
                and all(hex_string(v) for v in binding["backend_files"].values())
                and digest(binding["backend_files"]) == expected_backend_sha256, "source_epoch_mismatch")
        # These are the recorded producer's files, not this consumer's own hash.
        producer_context_tuple = tuple(binding["backend_files"].get(path) for path in (
            "scripts/matchup_round_robin.py", "scripts/regression_matrix_replay.py",
            "scripts/build_ai_log_priors.py"))
        current_context_layout = producer_context_tuple in {
            ("8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
             "d447992fb786b37d1a37174cc3c7b8693b196dda5072cf0ac247173053adb298",
             "68f2d13b6922d4329f9f1a3c9d0064c47cf6933bce94434ecb66f7592cbf2fb7"),
            ("8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
             "d29588861eb7a471ae3616fd79a4591c4b56050cc4ef9d1fe9db0e7ee3228b10",
             "68f2d13b6922d4329f9f1a3c9d0064c47cf6933bce94434ecb66f7592cbf2fb7"),
            ("8c844e5705dd653fe036fac87d552c9d31f69182bc38b8df5ca102ecbf5ffc59",
             "d29588861eb7a471ae3616fd79a4591c4b56050cc4ef9d1fe9db0e7ee3228b10",
             "1c9ecff41a97544329d81ac1188b7cb345ad491fac1159a31b7b4e48a25b64e2"),
        }
        require(current_context_layout or binding["backend_files"].get("scripts/matchup_round_robin.py") ==
                "9061cc3b92c136a6d44bd3bb9b3ecef3297dde125f04e18ccb36e49cabb0775b", "unsupported_native_layout_epoch")
        harness = header["harness_files"]
        require(type(harness) is dict and set(harness) == {"matrix_policy.py", "parent_matrix_harness.py", "parent_matrix_launch.py"}
                and all(hex_string(v) for v in harness.values()), "missing_harness_binding")
        runtime = header["runtime_inventory"]
        fixtures = header["fixtures"]
        require(type(runtime) is dict and type(runtime.get("files")) is dict and runtime["files"]
                and all(hex_string(v) for v in runtime["files"].values())
                and type(runtime.get("directories")) is list and runtime["directories"]
                and type(fixtures) is dict and all(type(fixtures.get(k)) is str and fixtures[k]
                    and hex_string(fixtures.get(k + "_sha256")) for k in ("raw155", "rulings", "provenance"))
                and type(header["limits"]) is dict and header["limits"]
                and all(type(v) is int and v >= 0 for v in header["limits"].values())
                and type(header["package_origin"]) is str and header["package_origin"]
                and type(header["parity_receipt"]) is str and header["parity_receipt"]
                and hex_string(header["parity_receipt_sha256"]), "incomplete_runtime_or_fixture_binding")
        parent = sealed("parent-outcome.json")
        require(parent.get("contract_sha256") == expected_contract_sha256 and parent.get("actual_launch") is True
                and type(parent.get("returncode")) is int and parent["returncode"] == 0
                and parent.get("closed") is True and parent.get("timeout") is False
                and not parent.get("stop_code") and not parent.get("reap_hold"), "parent_run_not_closed")
        child = sealed("runtime/outcome.json")
        summary = sealed("runtime/matrix-summary.json")
        expected_closure = {"source_base_commit": expected_source_base, "binding_sha256": digest(binding),
            "before_sha256": expected_backend_sha256, "after_sha256": expected_backend_sha256,
            "equal": True, "ordinary_files": len(binding["backend_files"])}
        for value in (child, summary):
            require(value.get("status") == "completed_schedule" and value.get("complete") is True
                    and type(value.get("attempted_series")) is int and value["attempted_series"] == 110
                    and type(value.get("not_run_series")) is int and value["not_run_series"] == 0
                    and canonical(value.get("measured_source")) == canonical(expected_closure)
                    and not value.get("stop_code"), "matrix_run_not_complete_or_source_closed")
        require(child.get("closed") is True and child.get("source_equal") is True
                and type(child.get("sql_handles")) is int and child["sql_handles"] >= 0
                and type(child.get("live_threads")) is int and child["live_threads"] == 0, "native_handles_not_closed")
        require(type(summary.get("schema_version")) is int and summary["schema_version"] == 1, "unsupported_summary_schema")
        export = sealed("runtime/prepared-boards.json")
        manifest = summary["manifest"]
        decks = export["decks"]
        require(type(decks) is list and len(decks) == 11 and export.get("decks_sha256") == digest(decks), "invalid_prepared_roster")
        roster = [{"name": d["name"], "classification_status": d["classification_status"], "archetype": d["archetype"],
                   "content_sha256": digest(d), "mainboard_cards": sum(c["quantity"] for c in d["mainboard"]),
                   "sideboard_cards": sum(c["quantity"] for c in d["sideboard"])} for d in decks]
        require(manifest["export_sha256"] == digest(export) and manifest["input_export_base_commit"] == export["source_commit"]
                and manifest["source_base_commit"] == expected_source_base and manifest["source_binding_sha256"] == digest(binding)
                and manifest["backend_before_sha256"] == expected_backend_sha256
                and canonical(manifest["limits"]) == canonical(header["limits"])
                and canonical(manifest["roster"]) == canonical(roster)
                and export["sideboard_mode"] == manifest["sideboard_mode"] == "fixed_no_swaps"
                and type(manifest["planned_series"]) is int and manifest["planned_series"] == 110
                and type(manifest["planned_pairs"]) is int and manifest["planned_pairs"] == 55
                and type(manifest["max_ticks"]) is int and manifest["max_ticks"] > 0
                and manifest["difficulty"] in ("casual", "strong", "master")
                and type(manifest.get("source_scope")) is str and manifest["source_scope"], "export_manifest_mismatch")
        names = [d["name"] for d in decks]
        require(all(type(n) is str and n for n in names) and len(set(names)) == 11
                and type(manifest["seeds"]) is list and len(manifest["seeds"]) == 1
                and type(manifest["seeds"][0]) is int and manifest["seeds"][0] >= 0, "invalid_explicit_schedule")
        if current_context_layout:
            effective_contexts = manifest.get("effective_archetypes", {})
            resolved_names = {d["name"] for d in decks if d["classification_status"] == "resolved"}
            require(type(effective_contexts) is dict and all(name in resolved_names and type(label) is str
                    for name, label in effective_contexts.items()), "invalid_effective_context_map")
        expected_schedule = {(a, b, seat, manifest["seeds"][0]) for a, b in combinations(sorted(names), 2) for seat in (1, 2)}
        actual_schedule, consumed, records = set(), set(), []
        metrics = ("missed_land_drops", "unused_mana_passes", "lethal_misses", "bad_blocks", "stall_streaks", "redundant_removal_casts")
        series = summary["series"]
        require(type(series) is list and len(series) == 110, "incomplete_series_records")
        for index, row in enumerate(series):
            seat, a, b = row["deck_a_seat"], row["deck_a"], row["deck_b"]
            require(type(seat) is int and seat in (1, 2) and type(row["seed_token"]) is int
                    and type(row["root_seed"]) is int and row["root_seed"] >= 0
                    and row["seat_one"] == (a if seat == 1 else b) and row["seat_two"] == (b if seat == 1 else a)
                    and row["sideboard_mode"] == "fixed_no_swaps" and row["status"] in ("resolved", "timeout", "draw_cap"), "invalid_series_identity")
            identity = (a, b, seat, row["seed_token"])
            require(identity in expected_schedule and identity not in actual_schedule, "duplicate_or_unexpected_series")
            actual_schedule.add(identity)
            games = row["games"]
            require(type(games) is list and 1 <= len(games) <= 6, "missing_native_games")
            for ordinal, game in enumerate(games, 1):
                receipt = game["evidence"]
                require(game.get("evidence_complete") is True and type(receipt) is dict
                        and set(receipt) == {"reference", "complete", "bytes", "raw_sha256"}
                        and receipt["complete"] is True and type(receipt["bytes"]) is int and receipt["bytes"] >= 0
                        and hex_string(receipt["raw_sha256"]) and receipt["reference"] == f"game-{ordinal:02d}.json"
                        and not game.get("stop_reason") and game.get("quality_available") is not False, "incomplete_native_receipt")
                quality = game["quality"]
                require(all(quality["availability"][pid].get(metric) is True
                            and type(quality["counts"][pid].get(metric)) is int and quality["counts"][pid][metric] >= 0
                            for pid in ("1", "2") for metric in metrics), "decision_quality_unavailable")
                relative = f"runtime/games/series-{index:05d}/" + receipt["reference"]
                require(relative not in consumed, "duplicate_native_game")
                capsule = sealed(relative)
                require(set(capsule) == {"schema_version", "result", "raw_log", "raw_sha256"}
                        and type(capsule["schema_version"]) is int and capsule["schema_version"] == 1
                        and type(capsule["result"]) is dict and type(capsule["raw_log"]) is list
                        and all(type(line) is str for line in capsule["raw_log"]), "unsupported_native_capsule")
                raw_bytes = json.dumps(capsule["raw_log"], ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                require(len(raw_bytes) == receipt["bytes"] and hashlib.sha256(raw_bytes).hexdigest()
                        == receipt["raw_sha256"] == capsule["raw_sha256"], "native_raw_receipt_mismatch")
                if current_context_layout:
                    for line in capsule["raw_log"]:
                        if "AI TRACE " not in line:
                            continue
                        try:
                            trace = json.loads(line.split("AI TRACE ", 1)[1])
                        except ValueError:
                            continue
                        if type(trace) is not dict:
                            continue
                        known_context = any(_opponent_archetype({key: trace.get(key)}) is not None
                                            for key in ("opp_archetype", "opponent_archetype"))
                        if not known_context:
                            continue
                        context, pid = _opponent_archetype(trace), trace.get("pid")
                        physical_contexts = {
                            1: _opponent_archetype({"opponent_archetype": effective_contexts.get(row["seat_two"])}),
                            2: _opponent_archetype({"opponent_archetype": effective_contexts.get(row["seat_one"])}),
                        }
                        require(context is not None and type(pid) is int and pid in (1, 2)
                                and row["seat_one"] in resolved_names and row["seat_two"] in resolved_names
                                and all(physical_contexts.values()) and physical_contexts[pid] == context,
                                "native_context_map_mismatch")
                result = capsule["result"]
                require(type(result.get("ticks")) is int and 0 <= result["ticks"] <= manifest["max_ticks"]
                        and positive_finite_int(result.get("turn"))
                        and (result.get("winner") is None or type(result["winner"]) is int and result["winner"] in (0, 1, 2))
                        and type(result.get("starting_player")) is int and result["starting_player"] in (1, 2)
                        and type(result.get("timeout")) is bool and hex_string(result.get("log_hash"))
                        and type(result.get("log")) is list and all(type(line) is str for line in result["log"]), "invalid_native_result")
                require(all(k in game and canonical(game[k]) == canonical(v) for k, v in result.items() if k != "log")
                        and all(k in result for k in ("winner", "turn", "ticks", "log_hash", "log", "timeout", "starting_player")), "native_result_summary_mismatch")
                consumed.add(relative)
                records.append((f"series-{index:05d}", {"game": receipt["reference"], "seed": result.get("seed"), "log": capsule["raw_log"]}))
        games_root = root / "runtime/games"
        ordinary(games_root)
        members = set()
        for path in games_root.rglob("*"):
            ordinary(path)
            if path.is_file():
                members.add(path.relative_to(root).as_posix())
        require(actual_schedule == expected_schedule and members == consumed, "unreferenced_or_missing_native_games")
        destination.mkdir(mode=0o700)
        created = True
        for directory, record in records:
            folder = destination / directory
            folder.mkdir(mode=0o700, exist_ok=True)
            path = folder / "games.jsonl"
            with path.open("ab") as handle:
                os.chmod(path, 0o600)
                handle.write(canonical(record) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        return {"status": "exported_private_training", "games": len(records), "priors_saved": False, "task33_complete": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        if created:
            shutil.rmtree(destination)
        return {"status": "unavailable", "reason": "native_envelope_not_qualified", "priors_saved": False, "task33_complete": False}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build replay timing priors")
    parser.add_argument("--training-root", type=Path, help="Explicit exports-only mode; never opens SQL")
    for flag in ("native-root", "native-contract", "native-inventory", "export-training-root"):
        parser.add_argument("--" + flag, type=Path)
    for flag in ("expected-source-base", "expected-backend-sha256", "expected-contract-sha256", "expected-inventory-sha256"):
        parser.add_argument("--" + flag)
    args = parser.parse_args(argv)
    native = {"root": args.native_root, "contract": args.native_contract, "inventory": args.native_inventory,
              "destination": args.export_training_root, "expected_source_base": args.expected_source_base,
              "expected_backend_sha256": args.expected_backend_sha256,
              "expected_contract_sha256": args.expected_contract_sha256,
              "expected_inventory_sha256": args.expected_inventory_sha256}
    if any(value is not None for value in native.values()):
        report = (_export_native_matrix_training(**native) if all(value is not None for value in native.values())
                  and args.training_root is None else {"status": "unavailable", "reason": "incomplete_native_cli_header", "priors_saved": False})
        print(json.dumps(report, indent=2))
        return
    training_root = args.training_root or Path(__file__).resolve().parents[1] / "training_runs"
    logs: list[list[str]] = []
    if args.training_root is None:
        # Preserve the legacy CLI; SQL is absent from imports and explicit offline runs.
        from sqlmodel import Session
        from persistence.db import engine
        from persistence.repository import Repository
        with Session(engine) as session:
            repo = Repository(session)
            for match in repo.list_matches():
                try:
                    decoded = json.loads(match.log_json)
                except Exception:
                    continue
                if isinstance(decoded, list) and decoded:
                    logs.append([str(item) for item in decoded])
    logs.extend(_read_training_run_logs(training_root))
    payload = build_priors_from_logs(logs)
    examples = _read_training_run_examples(training_root)
    if examples:
        example_payload = build_priors_from_examples(examples)
        payload = _merge_priors(payload, example_payload)
    context_payload, unavailable = _qualified_export_contexts(training_root)
    for name, row in payload["cards"].items():
        row.pop("opponent_archetypes", None)
        contexts = context_payload["cards"].get(name, {}).get("opponent_archetypes")
        if contexts:
            row["opponent_archetypes"] = contexts
    context_available = any(row.get("opponent_archetypes") for row in payload["cards"].values())
    if args.training_root is not None and not context_available:
        print(json.dumps({"context_available": False, "context_unavailable": unavailable,
                          "games": payload["samples"]["games"], "logs": payload["samples"]["logs"],
                          "cards": len(payload["cards"]), "saved": False,
                          "reason": "No qualified two-archetype timing rows; Task 3.3 data gap"}, indent=2))
        return
    saved = save_log_priors(payload)
    print(
        json.dumps(
            {
                "generated_at": saved.get("generated_at"),
                "games": saved.get("samples", {}).get("games", 0),
                "logs": saved.get("samples", {}).get("logs", 0),
                "cards": len(saved.get("cards", {})),
                "context_available": context_available,
                "context_unavailable": unavailable,
            },
            indent=2,
        )
    )


def _merge_priors(primary: dict, secondary: dict) -> dict:
    merged = {
        "generated_at": None,
        "samples": {
            "games": int(primary.get("samples", {}).get("games", 0) or 0) + int(secondary.get("samples", {}).get("games", 0) or 0),
            "logs": int(primary.get("samples", {}).get("logs", 0) or 0) + int(secondary.get("samples", {}).get("logs", 0) or 0),
        },
        "cards": {},
    }
    cards = merged["cards"]
    for source in (primary.get("cards", {}), secondary.get("cards", {})):
        if not isinstance(source, dict):
            continue
        for name, row in source.items():
            if not isinstance(row, dict):
                continue
            existing = cards.get(name)
            if not isinstance(existing, dict):
                cards[name] = deepcopy(row)
                continue
            cards[name] = _merge_card_rows(existing, row)
    return merged


def _merge_card_rows(left: dict, right: dict) -> dict:
    merged = deepcopy(left)
    left_casts = int(left.get("casts", 0) or 0)
    right_casts = int(right.get("casts", 0) or 0)
    total_casts = left_casts + right_casts
    if total_casts <= 0:
        return merged
    merged["casts"] = total_casts
    left_seen = int(left.get("seen_in_logs", 0) or 0)
    right_seen = int(right.get("seen_in_logs", 0) or 0)
    merged["seen_in_logs"] = left_seen + right_seen
    merged["avg_turn"] = round(
        ((float(left.get("avg_turn", 0.0) or 0.0) * left_casts) + (float(right.get("avg_turn", 0.0) or 0.0) * right_casts)) / total_casts,
        3,
    )
    for key in ("early_turn_cast_rate", "mid_turn_cast_rate", "late_turn_cast_rate"):
        merged[key] = round(
            ((float(left.get(key, 0.0) or 0.0) * left_casts) + (float(right.get(key, 0.0) or 0.0) * right_casts)) / total_casts,
            3,
        )
    merged["preferred_min_turn"] = max(1, int(round(merged["avg_turn"] - 1.0)))
    merged_roles = deepcopy(left.get("board_roles", {}) or {})
    for role, row in (right.get("board_roles", {}) or {}).items():
        if role not in merged_roles:
            merged_roles[role] = dict(row)
            continue
        existing = merged_roles[role]
        existing_casts = int(existing.get("casts", 0) or 0)
        row_casts = int(row.get("casts", 0) or 0)
        role_casts = existing_casts + row_casts
        if role_casts <= 0:
            continue
        existing_avg = float(existing.get("avg_turn", 0.0) or 0.0)
        row_avg = float(row.get("avg_turn", 0.0) or 0.0)
        existing["casts"] = role_casts
        existing["avg_turn"] = round(
            ((existing_avg * existing_casts) + (row_avg * row_casts)) / role_casts,
            3,
        )
        for key in ("early_turn_cast_rate", "mid_turn_cast_rate", "late_turn_cast_rate"):
            existing[key] = round(
                ((float(existing.get(key, 0.0) or 0.0) * existing_casts) + (float(row.get(key, 0.0) or 0.0) * row_casts)) / role_casts,
                3,
            )
        existing["preferred_min_turn"] = max(1, int(round(existing["avg_turn"] - 1.0)))
    merged["board_roles"] = merged_roles
    contexts = deepcopy(left.get("opponent_archetypes", {}) or {})
    for context, row in sorted((right.get("opponent_archetypes", {}) or {}).items()):
        contexts[context] = _merge_card_rows(contexts[context], row) if context in contexts else deepcopy(row)
        contexts[context].pop("board_roles", None)
        contexts[context].pop("seen_in_logs", None)
    if contexts:
        merged["opponent_archetypes"] = dict(sorted(contexts.items()))
    return merged


if __name__ == "__main__":
    main()
