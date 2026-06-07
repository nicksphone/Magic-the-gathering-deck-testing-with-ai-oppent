from __future__ import annotations

import argparse
import hashlib
import json
import re
from itertools import combinations
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from game_state.state import MatchFactory
from persistence.db import engine
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)


def _stable_seed(left_name: str, right_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{left_name}::{right_name}::{index}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _normalize_log_line(line: str) -> str:
    return UUID_RE.sub("<id>", line)


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

    normalized_log = [_normalize_log_line(line) for line in state.log]
    log_hash = hashlib.sha256("\n".join(normalized_log).encode("utf-8")).hexdigest()
    return {
        "winner": state.winner,
        "turn": state.turn,
        "ticks": ticks,
        "log_hash": log_hash,
        "log": normalized_log,
        "timeout": state.winner is None,
    }


def first_log_divergence(a_lines: list[str], b_lines: list[str]) -> dict:
    a_lines = [_normalize_log_line(line) for line in a_lines]
    b_lines = [_normalize_log_line(line) for line in b_lines]
    shared = min(len(a_lines), len(b_lines))
    idx = 0
    while idx < shared and a_lines[idx] == b_lines[idx]:
        idx += 1
    if idx == shared and len(a_lines) == len(b_lines):
        return {"index": -1, "a": "", "b": "", "context_before": [], "context_after_a": [], "context_after_b": []}
    start = max(0, idx - 2)
    return {
        "index": idx,
        "a": a_lines[idx] if idx < len(a_lines) else "<EOF>",
        "b": b_lines[idx] if idx < len(b_lines) else "<EOF>",
        "context_before": a_lines[start:idx],
        "context_after_a": a_lines[idx : min(len(a_lines), idx + 3)],
        "context_after_b": b_lines[idx : min(len(b_lines), idx + 3)],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Deterministic replay regression matrix")
    p.add_argument("--matches-per-pair", type=int, default=3)
    p.add_argument("--difficulty", default="master")
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--output", default="training_runs/regression_matrix_replay.json")
    p.add_argument("--max-decks", type=int, default=12)
    args = p.parse_args()

    with Session(engine) as session:
        repo = Repository(session)
        rows = repo.list_decks()

    decks = []
    seen: set[str] = set()
    for row in rows:
        key = (row.name or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        decks.append({"name": row.name, "mainboard": json.loads(row.mainboard_json)})
        if len(decks) >= max(2, args.max_decks):
            break

    summary = {
        "decks": len(decks),
        "pairs": 0,
        "games": 0,
        "determinism_failures": 0,
        "pair_results": [],
    }

    for left, right in combinations(decks, 2):
        summary["pairs"] += 1
        pair = {"deck_a": left["name"], "deck_b": right["name"], "games": []}
        for i in range(max(1, args.matches_per_pair)):
            seed = _stable_seed(left["name"], right["name"], i)
            a = run_game(left["mainboard"], right["mainboard"], seed, args.difficulty, args.max_ticks)
            b = run_game(left["mainboard"], right["mainboard"], seed, args.difficulty, args.max_ticks)
            deterministic_ok = a["winner"] == b["winner"] and a["turn"] == b["turn"] and a["log_hash"] == b["log_hash"]
            if not deterministic_ok:
                summary["determinism_failures"] += 1
                drift = first_log_divergence(a.get("log", []), b.get("log", []))
            else:
                drift = None
            pair["games"].append({
                "seed": seed,
                "winner": a["winner"],
                "turn": a["turn"],
                "timeout": a["timeout"],
                "deterministic": deterministic_ok,
                "drift": drift,
            })
            summary["games"] += 1
        summary["pair_results"].append(pair)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(out),
        "games": summary["games"],
        "determinism_failures": summary["determinism_failures"],
    }))


if __name__ == "__main__":
    main()
