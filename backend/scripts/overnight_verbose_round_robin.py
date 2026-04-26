from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.service import AnalyticsService
from game_state.state import MatchFactory
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verbose overnight MTG AI diagnostics round-robin")
    p.add_argument("--matches-per-pair", type=int, default=1000)
    p.add_argument("--difficulty", type=str, default="master")
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--sources", type=str, default="builtin", help="comma list: builtin,user")
    p.add_argument("--output-dir", type=str, default="diagnostics")
    p.add_argument("--write-full-log-for-all-games", action="store_true")
    return p.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def compact_action(action: dict) -> dict:
    out = {"type": action.get("type")}
    for k in ["card_id", "card_name", "ability_index"]:
        if k in action:
            out[k] = action[k]
    if isinstance(action.get("targets"), dict) and action.get("targets"):
        out["targets"] = action["targets"]
    if isinstance(action.get("cost_choice"), dict) and action.get("cost_choice"):
        out["cost_choice"] = action["cost_choice"]
    return out


def hand_snapshot(state, pid: int) -> list[str]:
    names = [state.cards[cid].name for cid in state.players[pid].hand]
    names.sort()
    return names


def run() -> int:
    args = parse_args()
    init_db()

    out_base = Path(args.output_dir)
    if not out_base.is_absolute():
        out_base = Path(__file__).resolve().parent.parent / out_base
    run_dir = out_base / f"overnight-{now_utc()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    progress_path = run_dir / "progress.log"
    anomalies_path = run_dir / "anomaly_games.jsonl"
    all_games_path = run_dir / "all_games.jsonl"
    summary_path = run_dir / "summary.json"

    with Session(engine) as session:
        repo = Repository(session)
        analytics = AnalyticsService(repo)
        rows = repo.list_decks()

        wanted = {x.strip().lower() for x in args.sources.split(",") if x.strip()}
        selected = [r for r in rows if (r.source or "").strip().lower() in wanted]
        if len(selected) < 2:
            raise SystemExit(f"Need at least 2 decks from sources={sorted(wanted)}; found {len(selected)}")

        deck_pool: list[dict] = []
        for row in selected:
            mainboard = json.loads(row.mainboard_json)
            deck_pool.append({"id": row.id, "name": row.name, "mainboard": mainboard})

        total_pairs = len(list(combinations(deck_pool, 2)))
        total_games = total_pairs * args.matches_per_pair

        global_counts: Counter = Counter()
        top_errors: Counter = Counter()
        pair_summaries: list[dict] = []

        engine_rules = RulesEngine()
        game_counter = 0
        t0 = time.time()

        with progress_path.open("w", encoding="utf-8") as progress, anomalies_path.open("w", encoding="utf-8") as anomalies, all_games_path.open("w", encoding="utf-8") as all_games:
            progress.write(f"start_utc={datetime.now(timezone.utc).isoformat()}\n")
            progress.write(f"decks={len(deck_pool)} pairs={total_pairs} matches_per_pair={args.matches_per_pair} total_games={total_games}\n")
            progress.flush()

            for left, right in combinations(deck_pool, 2):
                pair_counts: Counter = Counter()
                pair_turns: list[int] = []
                pair_start = time.time()

                left_arch = guess_archetype(left["mainboard"])
                right_arch = guess_archetype(right["mainboard"])

                for game_idx in range(args.matches_per_pair):
                    state = MatchFactory.from_decks(left["mainboard"], right["mainboard"], player_a_name=left["name"], player_b_name=right["name"])
                    a_agent = AIAgent(difficulty=args.difficulty, archetype=left_arch)
                    b_agent = AIAgent(difficulty=args.difficulty, archetype=right_arch)

                    ticks = 0
                    passed_with_options = 0
                    missed_land_windows = 0
                    stalled_pass_streak = 0
                    while state.winner is None and ticks < args.max_ticks:
                        pid = 1 if state.pregame_pending and 1 not in state.kept_hands else (2 if state.pregame_pending else state.priority_player)
                        legal = engine_rules.legal_moves(state, pid)
                        if not legal:
                            action = {"type": "pass_priority"}
                        else:
                            agent = a_agent if pid == 1 else b_agent
                            decision = agent.choose_action(state, legal, pid)
                            action = decision.action

                        legal_non_pass = any(m.get("type") != "pass_priority" for m in legal)
                        legal_has_land = any(m.get("type") == "play_land" for m in legal)
                        acted_type = action.get("type")
                        if acted_type == "pass_priority" and legal_non_pass:
                            passed_with_options += 1
                            stalled_pass_streak += 1
                        else:
                            stalled_pass_streak = 0
                        if legal_has_land and acted_type != "play_land":
                            missed_land_windows += 1

                        # Verbose trace line for each AI decision point.
                        trace_line = {
                            "trace": True,
                            "pid": pid,
                            "turn": state.turn,
                            "step": str(state.step),
                            "hand": hand_snapshot(state, pid),
                            "mana_pool": dict(state.players[pid].mana_pool),
                            "legal_non_pass": legal_non_pass,
                            "legal_has_land": legal_has_land,
                            "action": compact_action(action),
                        }
                        state.log.append(f"AI TRACE {json.dumps(trace_line, separators=(',', ':'))}")

                        pre_len = len(state.log)
                        engine_rules.take_action(state, pid, action)
                        if state.step == state.step.COMBAT_DAMAGE:
                            engine_rules.take_action(state, state.active_player, {"type": "combat_damage"})
                        # Keep explicit mana payment lines in log as-is from mana.auto_pay_cost.
                        _ = state.log[pre_len:]
                        ticks += 1

                    if state.winner is None:
                        pair_counts["timeouts"] += 1
                    if passed_with_options > 0:
                        pair_counts["passed_with_options"] += passed_with_options
                    if missed_land_windows > 0:
                        pair_counts["missed_land_windows"] += missed_land_windows
                    if stalled_pass_streak >= 3:
                        pair_counts["stall_streaks"] += 1

                    analytics._scan_log_for_anomalies(state.log, pair_counts, top_errors)
                    pair_turns.append(state.turn)
                    game_counter += 1

                    game_record = {
                        "deck_a": left["name"],
                        "deck_b": right["name"],
                        "game_index": game_idx + 1,
                        "winner": state.winner,
                        "turns": state.turn,
                        "ticks": ticks,
                        "timeouts": int(state.winner is None),
                        "passed_with_options": passed_with_options,
                        "missed_land_windows": missed_land_windows,
                    }

                    has_anomaly = any(k in pair_counts for k in ["invalid_targets", "cost_failures", "additional_cost_failures", "repeated_error_bursts"]) and any(
                        x in "\n".join(state.log).lower() for x in ["invalid targets for", "cannot pay mana cost", "cannot satisfy chosen costs", "failed additional costs"]
                    )
                    has_behavior_anomaly = passed_with_options > 0 or missed_land_windows > 0 or stalled_pass_streak >= 3

                    if args.write_full_log_for_all_games:
                        game_record["log"] = state.log
                        all_games.write(json.dumps(game_record, ensure_ascii=True) + "\n")
                    elif has_anomaly or has_behavior_anomaly or state.winner is None:
                        game_record["log"] = state.log
                        anomalies.write(json.dumps(game_record, ensure_ascii=True) + "\n")

                    if game_counter % 50 == 0:
                        elapsed = time.time() - t0
                        rate = game_counter / max(1.0, elapsed)
                        remain = total_games - game_counter
                        eta_sec = remain / max(1e-6, rate)
                        progress.write(
                            f"games={game_counter}/{total_games} rate={rate:.2f}/s eta_min={eta_sec/60:.1f} now={datetime.now(timezone.utc).isoformat()}\n"
                        )
                        progress.flush()
                        anomalies.flush()
                        all_games.flush()

                avg_turns = round(sum(pair_turns) / max(1, len(pair_turns)), 2)
                pair_summary = {
                    "deck_a": left["name"],
                    "deck_b": right["name"],
                    "games": args.matches_per_pair,
                    "avg_turns": avg_turns,
                    "timeouts": int(pair_counts["timeouts"]),
                    "invalid_targets": int(pair_counts["invalid_targets"]),
                    "cost_failures": int(pair_counts["cost_failures"]),
                    "additional_cost_failures": int(pair_counts["additional_cost_failures"]),
                    "repeated_error_bursts": int(pair_counts["repeated_error_bursts"]),
                    "passed_with_options": int(pair_counts["passed_with_options"]),
                    "missed_land_windows": int(pair_counts["missed_land_windows"]),
                    "stall_streaks": int(pair_counts["stall_streaks"]),
                    "elapsed_sec": round(time.time() - pair_start, 2),
                }
                pair_summaries.append(pair_summary)
                global_counts.update(pair_counts)
                progress.write(f"pair_done {json.dumps(pair_summary, ensure_ascii=True)}\n")
                progress.flush()

    result = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "difficulty": args.difficulty,
        "matches_per_pair": args.matches_per_pair,
        "max_ticks": args.max_ticks,
        "sources": sorted({x.strip().lower() for x in args.sources.split(",") if x.strip()}),
        "totals": {
            "timeouts": int(global_counts["timeouts"]),
            "invalid_targets": int(global_counts["invalid_targets"]),
            "cost_failures": int(global_counts["cost_failures"]),
            "additional_cost_failures": int(global_counts["additional_cost_failures"]),
            "repeated_error_bursts": int(global_counts["repeated_error_bursts"]),
            "passed_with_options": int(global_counts["passed_with_options"]),
            "missed_land_windows": int(global_counts["missed_land_windows"]),
            "stall_streaks": int(global_counts["stall_streaks"]),
        },
        "top_errors": [{"message": m, "count": c} for m, c in top_errors.most_common(100)],
        "pair_summaries": sorted(
            pair_summaries,
            key=lambda x: x["timeouts"] * 5 + x["invalid_targets"] * 3 + x["cost_failures"] * 2 + x["repeated_error_bursts"],
            reverse=True,
        ),
        "output": {
            "run_dir": str(run_dir),
            "progress_log": str(progress_path),
            "anomaly_games_jsonl": str(anomalies_path),
            "all_games_jsonl": str(all_games_path),
        },
    }
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["output"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
