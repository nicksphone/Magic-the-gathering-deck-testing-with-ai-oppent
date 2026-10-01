"""Offline paired ablation: reuse/log-copy savings without changing decisions."""
from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

import argparse
from contextlib import ExitStack, nullcontext
from copy import deepcopy
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from ai import agent as agent_module, pending_effects
from game_state.serializers import deserialize_match_snapshot, serialize_match_snapshot
from rules_engine.engine import RulesEngine


def _reference_planning_copy(state):
    log = getattr(state, "log", None)
    return deepcopy(state, {id(log): []} if isinstance(log, list) else {})


def benchmark(snapshot: dict, player_id: int, iterations: int = 5, *, archetype: str = "Control",
              difficulty: str = "master", opponent_archetype: str | None = None,
              reference_mode: str = "full") -> dict:
    if player_id not in (1, 2) or iterations < 1:
        raise ValueError("Choose player 1/2 and a positive iteration count")
    if reference_mode not in {"full", "copy-only", "card-fields", "hotpaths"}:
        raise ValueError("Choose full, copy-only, card-fields or hotpaths reference mode")
    reference_key = {"full": "reference_ablation", "copy-only": "reference_copy", "card-fields": "reference_card_fields", "hotpaths": "reference_hotpaths"}[reference_mode]
    rows = {"optimized": [], reference_key: []}
    decisions = []
    unchanged = True
    for iteration in range(iterations):
        # Alternate ordering to reduce systematic cold-cache/timing bias.
        order = list(rows) if iteration % 2 == 0 else list(reversed(rows))
        for mode in order:
            state = deserialize_match_snapshot(snapshot)
            before = serialize_match_snapshot(state)
            moves = RulesEngine().legal_moves(state, player_id)
            agent = agent_module.AIAgent(archetype=archetype, difficulty=difficulty,
                                         opponent_archetype=opponent_archetype)
            with ExitStack() as scope:
                if mode == reference_key:
                    if reference_mode in {"card-fields", "hotpaths"}:
                        scope.enter_context(patch.object(pending_effects, "_copy_card_field", deepcopy))
                        if reference_mode == "hotpaths":
                            from rules_engine import continuous
                            for name in ("_iter_pt_modifiers", "_iter_pt_setters", "_iter_keyword_grants",
                                         "_iter_keyword_removals", "_iter_keyword_cant_removals"):
                                parser = getattr(continuous, name)
                                scope.enter_context(patch.object(continuous, name, parser.uncached))
                    elif reference_mode == "full":
                        scope.enter_context(patch.object(pending_effects, "decision_projection_scope", lambda *_: nullcontext()))
                        scope.enter_context(patch.object(agent_module, "planning_copy", deepcopy))
                    else:
                        scope.enter_context(patch.object(agent_module, "planning_copy", _reference_planning_copy))
                    if reference_mode not in {"card-fields", "hotpaths"}:
                        scope.enter_context(patch.object(pending_effects, "planning_copy", _reference_planning_copy))
                settles = scope.enter_context(patch.object(pending_effects, "_settle_announced_stack", wraps=pending_effects._settle_announced_stack))
                start = perf_counter()
                decision = agent.choose_action(state, moves, player_id)
                elapsed = perf_counter() - start
                rows[mode].append({"seconds": elapsed, "settle_calls": settles.call_count})
            decisions.append({"action": decision.action, "reasoning": decision.reasoning})
            unchanged = unchanged and serialize_match_snapshot(state) == before
    timing = {mode: {"median_seconds": median(row["seconds"] for row in samples),
                     "min_seconds": min(row["seconds"] for row in samples),
                     "max_seconds": max(row["seconds"] for row in samples),
                     "settle_calls": [row["settle_calls"] for row in samples]} for mode, samples in rows.items()}
    optimized_time = timing["optimized"]["median_seconds"]
    return {"iterations_per_mode": iterations, "player_id": player_id, "archetype": archetype,
            "difficulty": difficulty, "opponent_archetype": opponent_archetype,
            "reference_mode": reference_mode, "actions_and_reasoning_equal": all(row == decisions[0] for row in decisions),
            "authoritative_state_unchanged": unchanged, "timing": timing,
            "median_speedup_ratio": timing[reference_key]["median_seconds"] / optimized_time if optimized_time else None,
            "scope": "single-snapshot performance ablation; not strength, balance or worst-case latency evidence"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Private engine snapshot JSON, not a public card view")
    parser.add_argument("--player", type=int, choices=(1, 2), default=1)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--archetype", default="Control")
    parser.add_argument("--opponent-archetype")
    parser.add_argument("--reference-mode", choices=("full", "copy-only", "card-fields", "hotpaths"), default="full")
    parser.add_argument("--difficulty", choices=("casual", "strong", "master"), default="master")
    parser.add_argument("--output", default="training_runs/ai_decision_benchmark.json")
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    snapshot = json.loads(Path(args.snapshot).read_text())
    result = benchmark(snapshot.get("state", snapshot), args.player, args.iterations,
                       archetype=args.archetype, difficulty=args.difficulty,
                       opponent_archetype=args.opponent_archetype, reference_mode=args.reference_mode)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "equal_decisions": result["actions_and_reasoning_equal"],
                      "unchanged_state": result["authoritative_state_unchanged"],
                      "median_speedup_ratio": result["median_speedup_ratio"]}))
    return 0 if result["actions_and_reasoning_equal"] and result["authoritative_state_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
