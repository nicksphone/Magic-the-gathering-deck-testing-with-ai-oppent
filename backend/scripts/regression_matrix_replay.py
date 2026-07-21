from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.replay_tools import classify_first_divergence, classify_log_line, classify_timeout_state, first_log_divergence, normalize_log_line
from card_data.hydration import hydrate_deck_cards
from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from decks.selection import select_representative_decks
from game_state.state import MatchFactory
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session


def _stable_seed(left_name: str, right_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{left_name}::{right_name}::{index}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


_normalize_log_line = normalize_log_line
_select_regression_matrix_decks = select_representative_decks


def _drift_excerpt(drift: dict, drift_label: dict | None) -> dict:
    return {
        "index": drift.get("index", -1),
        "category": (drift_label or {}).get("category", "unknown"),
        "line_a": drift.get("a", ""),
        "line_b": drift.get("b", ""),
        "context_before": drift.get("context_before", []),
    }


def run_game(deck_a: list[dict], deck_b: list[dict], seed: int, difficulty: str, max_ticks: int) -> dict:
    state = MatchFactory.from_decks(deck_a, deck_b, seed=seed)
    engine_rules = RulesEngine()
    ai_a = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_a), opponent_archetype=guess_archetype(deck_b))
    ai_b = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_b), opponent_archetype=guess_archetype(deck_a))
    ticks = 0
    while state.winner is None and ticks < max_ticks:
        pid = 1 if state.pregame_pending and 1 not in state.kept_hands else (2 if state.pregame_pending else state.priority_player)
        legal = engine_rules.legal_moves(state, pid)
        if not legal:
            action = {"type": "pass_priority"}
        else:
            agent = ai_a if pid == 1 else ai_b
            action = agent.choose_action(state, legal, pid).action
            legal_types = {m["type"] for m in legal}
            if action.get("type") not in legal_types:
                action = {"type": "pass_priority"}
        engine_rules.take_action(state, pid, action)
        if state.step == state.step.COMBAT_DAMAGE:
            engine_rules.take_action(state, state.active_player, {"type": "combat_damage"})
        ticks += 1

    normalized_log = [normalize_log_line(line) for line in state.log]
    log_hash = hashlib.sha256("\n".join(normalized_log).encode("utf-8")).hexdigest()
    return {
        "winner": state.winner,
        "turn": state.turn,
        "ticks": ticks,
        "log_hash": log_hash,
        "log": normalized_log,
        "timeout": state.winner is None,
    }


def run_match(deck_a: list[dict], deck_b: list[dict], seed: int, difficulty: str, max_ticks: int, best_of: int) -> dict:
    """Run a seeded match while preserving each game's independent replay seed."""
    wins = {1: 0, 2: 0}
    games: list[dict] = []
    needed = best_of // 2 + 1
    for game_index in range(best_of):
        game = run_game(deck_a, deck_b, seed + game_index, difficulty, max_ticks)
        games.append(game)
        if game["winner"] in wins:
            wins[game["winner"]] += 1
        if max(wins.values()) >= needed:
            break
    winner = 1 if wins[1] >= needed else (2 if wins[2] >= needed else None)
    match_hash = hashlib.sha256(
        "\n".join(game["log_hash"] for game in games).encode("utf-8")
    ).hexdigest()
    return {
        "winner": winner,
        "wins": {"deck_a": wins[1], "deck_b": wins[2]},
        "games_played": len(games),
        "timeout": any(game["timeout"] for game in games),
        "turns": sum(int(game["turn"] or 0) for game in games),
        "log_hash": match_hash,
        "log": [line for game in games for line in game["log"]],
        "games": games,
    }
def main() -> None:
    p = argparse.ArgumentParser(description="Deterministic replay regression matrix")
    p.add_argument("--matches-per-pair", type=int, default=3)
    p.add_argument("--difficulty", default="master")
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--output", default="training_runs/regression_matrix_replay.json")
    p.add_argument("--max-decks", type=int, default=12)
    p.add_argument("--best-of", type=int, choices=(1, 3, 5, 7, 9), default=1)
    args = p.parse_args()

    with Session(engine) as session:
        repo = Repository(session)
        ensure_builtin_decks(repo)
        ensure_expansion_top_decks(repo)
        rows = repo.list_decks()

    selected_decks = select_representative_decks(rows, args.max_decks, guess_archetype_fn=guess_archetype)
    with Session(engine) as session:
        hydration_repo = Repository(session)
        decks = [
            {**deck, "mainboard": hydrate_deck_cards(hydration_repo, deck["mainboard"])}
            for deck in selected_decks
        ]

    summary = {
        "decks": len(decks),
        "pairs": 0,
        "games": 0,
        "matches": 0,
        "best_of": args.best_of,
        "determinism_failures": 0,
        "drift_labels": {},
        "pair_results": [],
    }
    drift_labels = Counter()
    anomaly_counts = Counter()

    for left, right in combinations(decks, 2):
        summary["pairs"] += 1
        pair = {"deck_a": left["name"], "deck_b": right["name"], "games": []}
        for i in range(max(1, args.matches_per_pair)):
            seed = _stable_seed(left["name"], right["name"], i)
            a = run_match(left["mainboard"], right["mainboard"], seed, args.difficulty, args.max_ticks, args.best_of)
            b = run_match(left["mainboard"], right["mainboard"], seed, args.difficulty, args.max_ticks, args.best_of)
            deterministic_ok = a["winner"] == b["winner"] and a["turns"] == b["turns"] and a["log_hash"] == b["log_hash"]
            if not deterministic_ok:
                summary["determinism_failures"] += 1
                drift = first_log_divergence(a.get("log", []), b.get("log", []))
                drift_label = classify_first_divergence(drift)
                drift_labels[drift_label["category"]] += 1
                anomaly_counts[drift_label["action_a"]] += 1
            else:
                drift = None
                drift_label = None
            pair["games"].append({
                "seed": seed,
                "winner": a["winner"],
                "turns": a["turns"],
                "games_played": a["games_played"],
                "wins": a["wins"],
                "timeout": a["timeout"],
                "termination_status": classify_timeout_state(a.get("log", []), bool(a["timeout"])),
                "deterministic": deterministic_ok,
                "drift": drift,
                "drift_label": drift_label,
                "drift_excerpt": _drift_excerpt(drift, drift_label) if drift else None,
            })
            summary["matches"] += 1
            summary["games"] += a["games_played"]
        summary["pair_results"].append(pair)

    summary["drift_labels"] = dict(drift_labels)
    summary["anomaly_counts"] = dict(anomaly_counts)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(out),
        "matches": summary["matches"],
        "games": summary["games"],
        "best_of": summary["best_of"],
        "determinism_failures": summary["determinism_failures"],
        "drift_labels": summary["drift_labels"],
    }))


if __name__ == "__main__":
    main()
