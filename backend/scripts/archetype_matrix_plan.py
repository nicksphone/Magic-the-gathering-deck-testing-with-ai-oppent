"""Plan/analyze only. Never launches games or imports the rules/AI engine."""
import argparse
import ast
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import random
import re

SEEDS = list(range(2026111801, 2026111821))
EXCLUSIONS = {name: "Seed-only admission stops on Rift Bolt suspend and Searing Blaze linked/landfall damage; no rules bypass"
              for name in ("Burn", "Mono Red Aggro")}
STATUSES = {"resolved", "draw", "timeout", "tick_limit", "turn_limit", "error", "replay_divergence"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build_plan(revision, builtin_source):
    if type(revision) is not str or not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Full measured revision required")
    tree = ast.parse(builtin_source)
    decks = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.AnnAssign)
                                 and isinstance(n.target, ast.Name) and n.target.id == "BUILTIN_DECKS"))
    names = sorted(decks)
    if len(names) != 11 or not set(EXCLUSIONS).issubset(names):
        raise ValueError("Roster changed; review the plan before execution")
    source_decks = decks
    decks = {name: source_decks[name] for name in names if name not in EXCLUSIONS}
    names = sorted(decks)
    cells = []
    for a, b in combinations(names, 2):
        for seed in SEEDS:
            for seat in (1, 2):
                identity = {"deck_a": a, "deck_b": b, "seed": seed, "deck_a_seat": seat}
                cells.append({"cell_id": digest(identity), **identity})
    plan = {"schema": 1, "run_id": "archetype-admitted-20261116-v2", "revision": revision,
            "builtin_sha256": hashlib.sha256(builtin_source.encode()).hexdigest(),
            "source_decks": source_decks, "decks": decks, "excluded_decks": EXCLUSIONS.copy(),
            "seeds": SEEDS.copy(), "cells": cells,
            "policy": {"unit": "single_game", "difficulty": "master", "sideboard": "none",
                       "max_seconds": 120, "max_ticks": 10000, "max_turns": 100,
                       "workers": 2, "cpu_cores_per_worker": 1, "max_cpu_seconds_per_game": 90,
                       "max_memory_bytes_per_worker": 2147483648,
                       "shuffle_policy": "engine_seed_with_seats_swapped_not_deck_fixed",
                       "crash_or_host_sleep": "invalidate_run_new_id_no_resume",
                       "health_gate": {"crashes": 0, "illegal_accepted_actions": 0,
                                       "replay_divergences": 0, "parity_divergences": 0,
                                       "missing_traces": 0, "missing_cells": 0,
                                       "max_resource_limit_fraction": 0.01, "max_resource_limit_cells": 14,
                                       "all_decks_admitted": True, "accepts_ai_strength": False},
                       "timeout_score": None, "draw_score": 0.5, "deck_out": "engine_rules",
                       "resume": False, "retries": 0, "legacy_results": "forbidden",
                       "ci": "paired_seed_cluster_percentile_bootstrap_95", "bootstrap_replicates": 2000,
                       "bootstrap_seed": 271828}, "execution_implemented": False}
    return plan


def admission_report():
    """Committed seed-only readiness/known-gap screen, no DB/network/game run."""
    from decks.builtin_decks import BUILTIN_DECKS
    from scripts.matchup_round_robin import _template_inventory, admit_execution_rows
    from card_data.seed_cards import SEED_CARD_DATA, seed_card_payload
    from card_data.hydration import ready_for_match
    from rules_engine.coverage import deck_pair_coverage
    results = []
    for name, text in sorted(BUILTIN_DECKS.items()):
        boards, missing = {}, []
        for board, inventory in _template_inventory(text).items():
            rows = []
            for card, count in inventory.items():
                if card not in SEED_CARD_DATA:
                    missing.append(card)
                    continue
                row = {**seed_card_payload(card), "card_name": card, "quantity": count}
                rows.append(row)
                if not ready_for_match(row):
                    missing.append(card)
            boards[board] = rows
        if not missing:
            admit_execution_rows([{"name": name, **boards}])
        gaps = deck_pair_coverage(boards["mainboard"] + boards["sideboard"], [])["known_unsupported_cards"]
        results.append({"deck": name, "canonical_missing": sorted(set(missing)),
                        "known_gaps": [{"card": g["card_name"], "reasons": g["mechanics"]} for g in gaps],
                        "screen": "stop" if missing or gaps else "pass_known_gap_screen"})
    return {"scope": "seed-only canonical readiness and exploratory known-gap screen; not runtime certification",
            "decks": results, "excluded_decks": EXCLUSIONS.copy(),
            "original_roster_runnable": all(row["screen"] == "pass_known_gap_screen" for row in results),
            "matrix_runnable": all(row["screen"] == "pass_known_gap_screen" for row in results if row["deck"] not in EXCLUSIONS)}


def paired_interval(scores, seed):
    rng = random.Random(seed)
    n = len(scores)
    samples = sorted(sum(rng.choice(scores) for _ in range(n)) / n for _ in range(2000))
    return [samples[49], samples[1949]]


def summarize(plan, records):
    # Rebuild the declared roster/schedule/policy to reject edited budgets/cells.
    builtin = "BUILTIN_DECKS: dict[str, str] = " + repr(plan["source_decks"])
    rebuilt = build_plan(plan["revision"], builtin)
    for key in ("schema", "run_id", "source_decks", "decks", "excluded_decks", "seeds", "cells", "policy", "execution_implemented"):
        if plan[key] != rebuilt[key]:
            raise ValueError("Plan differs from predeclared policy")
    if type(records) is not list:
        raise ValueError("Result list required")
    by_id = {}
    cells = {c["cell_id"]: c for c in plan["cells"]}
    for record in records:
        if type(record) is not dict or set(record) != {"cell_id", "revision", "status", "winner", "termination", "trace_sha256"}:
            raise ValueError("Exact result fields required")
        cid = record["cell_id"]
        if type(cid) is not str or cid not in cells or cid in by_id or record["revision"] != plan["revision"]:
            raise ValueError("Foreign, duplicate or wrong-revision result")
        status, winner = record["status"], record["winner"]
        if type(status) is not str or status not in STATUSES or type(record["termination"]) is not str:
            raise ValueError("Typed outcome required")
        if status == "resolved":
            if type(winner) is not int or winner not in (1, 2) or record["termination"] not in {"life", "deck_out", "other_rules"}:
                raise ValueError("Resolved result requires an engine winner/cause")
        elif winner is not None or (status == "draw" and record["termination"] != "engine_draw"):
            raise ValueError("Limits/errors are not wins or rules draws")
        if type(record["trace_sha256"]) is not str or not re.fullmatch("[0-9a-f]{64}", record["trace_sha256"]):
            raise ValueError("Complete trace digest required")
        by_id[cid] = record
    if set(by_id) != set(cells):
        raise ValueError("Incomplete matrix: no prefix summary or silent omissions")
    pairs = []
    for a, b in combinations(sorted(plan["decks"]), 2):
        selected = [c for c in plan["cells"] if (c["deck_a"], c["deck_b"]) == (a, b)]
        counts, points, blocks = Counter(), 0.0, {seed: [] for seed in SEEDS}
        causes, seat_wins = Counter(), {1: 0, 2: 0}
        for cell in selected:
            row = by_id[cell["cell_id"]]
            counts[row["status"]] += 1
            causes[row["termination"]] += 1
            if row["status"] == "resolved":
                score = float(row["winner"] == cell["deck_a_seat"])
                seat_wins[row["winner"]] += 1
            elif row["status"] == "draw":
                score = 0.5
            else:
                continue
            points += score
            blocks[cell["seed"]].append(score)
        unresolved = len(selected) - sum(len(v) for v in blocks.values())
        paired = [sum(v) / 2 for v in blocks.values() if len(v) == 2]
        pairs.append({"deck_a": a, "deck_b": b, "scheduled_games": len(selected), "outcomes": dict(counts),
                      "termination_counts": dict(causes), "wins_by_physical_seat": seat_wins,
                      "unresolved": unresolved, "score_identification_bounds": [points/len(selected), (points+unresolved)/len(selected)],
                      "complete_seed_pairs": len(paired),
                      "paired_score_ci95": paired_interval(paired, 271828 ^ int(digest([a,b])[:16],16)) if unresolved == 0 else None})
    return {"run_id": plan["run_id"], "revision": plan["revision"], "plan_sha256": digest(plan),
            "complete_matrix": True, "games": len(records), "pairs": pairs,
            "strength_claim": False}


def first_divergence(left, right):
    """Return only location/field names, never hidden-state values."""
    for index in range(max(len(left), len(right))):
        if index >= min(len(left), len(right)):
            return {"step": index, "fields": ["trace_length"]}
        fields = sorted(k for k in set(left[index]) | set(right[index])
                        if k not in left[index] or k not in right[index]
                        or digest(left[index][k]) != digest(right[index][k]))
        if fields:
            return {"step": index, "fields": fields}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("revision"); p.add_argument("output", type=Path)
    p = sub.add_parser("analyze"); p.add_argument("plan", type=Path); p.add_argument("results", type=Path); p.add_argument("output", type=Path)
    p = sub.add_parser("admission"); p.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        result = build_plan(args.revision, (Path(__file__).parents[1]/"decks/builtin_decks.py").read_text())
    elif args.command == "admission":
        result = admission_report()
    else:
        result = summarize(json.loads(args.plan.read_text()), json.loads(args.results.read_text()))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
