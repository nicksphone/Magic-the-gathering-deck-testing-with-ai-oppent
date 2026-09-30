"""Offline seeded decision-latency telemetry; no card/hand data in output."""
from __future__ import annotations

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

import argparse
import json
import math
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from ai.agent import AIAgent
from card_data.hydration import hydrate_deck_cards
from decks.builtin_decks import BUILTIN_DECKS
from scripts.regression_matrix_replay import run_game


def latency_summary(rows: list[dict], target_seconds: float) -> dict:
    if not math.isfinite(target_seconds) or target_seconds <= 0:
        raise ValueError("Decision target must be positive and finite")
    values = sorted(row["seconds"] for row in rows)
    return {"decisions": len(values), "target_seconds": target_seconds,
            "over_target": sum(value > target_seconds for value in values),
            **{name: values[math.ceil(q * len(values)) - 1] if values else None
               for name, q in (("p50_seconds", .5), ("p95_seconds", .95),
                               ("p99_seconds", .99), ("max_seconds", 1))}}


def profile_game(deck_a: list[dict], deck_b: list[dict], seed: int, *,
                 difficulty: str = "master", max_ticks: int = 2400,
                 starting_player: int = 1, target_seconds: float = 1.0) -> dict:
    """Single-process diagnostic: observe decisions without a time cutoff."""
    latency_summary([], target_seconds)
    if max_ticks < 1:
        raise ValueError("Tick cap must be positive")
    rows = []
    choose = AIAgent.choose_action

    def timed_choose(agent, state, moves, player_id):
        start = perf_counter()
        decision = choose(agent, state, moves, player_id)
        elapsed = perf_counter() - start
        rows.append({"seconds": elapsed, "archetype": agent.archetype,
                     "player_id": player_id, "turn": state.turn, "step": state.step.value,
                     "battlefield_count": sum(len(p.battlefield) for p in state.players.values()),
                     "legal_moves": len(moves), "action_type": decision.action["type"],
                     "history_lines": len(state.log)})
        return decision

    with patch.object(AIAgent, "choose_action", timed_choose):
        game = run_game(deck_a, deck_b, seed, difficulty, max_ticks,
                        starting_player=starting_player)
    return {"seed": seed, "difficulty": difficulty, "max_ticks": max_ticks,
            "game": {key: value for key, value in game.items() if key != "log"},
            "latency": latency_summary(rows, target_seconds),
            "by_archetype": {style: latency_summary([row for row in rows if row["archetype"] == style], target_seconds)
                             for style in sorted({row["archetype"] for row in rows})},
            "decisions": rows,
            "scope": "Offline built-in metadata; decision time, not HTTP latency, AI strength or balance. "
                     "Targets are diagnostics, never gameplay cutoffs. Run in a dedicated process."}


def _builtin(name):
    entries = [{"quantity": int(q), "card_name": card}
               for q, card in (line.split(" ", 1) for line in BUILTIN_DECKS[name].strip().splitlines())]
    return hydrate_deck_cards(None, entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck-a", choices=sorted(BUILTIN_DECKS), default="Blue Control")
    parser.add_argument("--deck-b", choices=sorted(BUILTIN_DECKS), default="Ramp")
    parser.add_argument("--seed", type=int, default=111)
    parser.add_argument("--difficulty", choices=("casual", "strong", "master"), default="master")
    parser.add_argument("--max-ticks", type=int, default=2400)
    parser.add_argument("--starting-player", type=int, choices=(1, 2), default=1)
    parser.add_argument("--target-seconds", type=float, default=1.0)
    parser.add_argument("--output", default="training_runs/ai_latency.json")
    args = parser.parse_args()
    if args.max_ticks < 1 or not math.isfinite(args.target_seconds) or args.target_seconds <= 0:
        parser.error("Tick cap and finite decision target must be positive")
    result = profile_game(_builtin(args.deck_a), _builtin(args.deck_b), args.seed,
                          difficulty=args.difficulty, max_ticks=args.max_ticks,
                          starting_player=args.starting_player, target_seconds=args.target_seconds)
    result.update(deck_a=args.deck_a, deck_b=args.deck_b)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "game": result["game"], "latency": result["latency"]}))
    return 1 if result["game"]["timeout"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
