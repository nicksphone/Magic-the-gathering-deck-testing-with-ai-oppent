from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import re

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.replay_tools import classify_timeout_state
from analytics.service import AnalyticsService
from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from decks.selection import select_representative_decks
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
    p.add_argument("--max-decks", type=int, default=0, help="Cap the selected deck pool after source filtering")
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


def battlefield_snapshot(state, pid: int) -> list[dict]:
    """Keep round-robin traces compact while retaining tactical board state."""
    out: list[dict] = []
    for cid in state.players[pid].battlefield:
        card = state.cards[cid]
        out.append(
            {
                "id": cid,
                "name": card.name,
                "types": list(getattr(card, "types", []) or []),
                "tapped": bool(getattr(card, "tapped", False)),
                "power": getattr(card, "power", None),
                "toughness": getattr(card, "toughness", None),
                "loyalty": getattr(card, "loyalty", None),
                "selected_face_index": getattr(card, "selected_face_index", None),
            }
        )
    return sorted(out, key=lambda item: (item["name"], item["id"]))


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
        ensure_builtin_decks(repo)
        ensure_expansion_top_decks(repo)
        analytics = AnalyticsService(repo)
        rows = repo.list_decks()

        wanted = {x.strip().lower() for x in args.sources.split(",") if x.strip()}
        selected = [r for r in rows if (r.source or "").strip().lower() in wanted]
        if len(selected) < 2:
            raise SystemExit(f"Need at least 2 decks from sources={sorted(wanted)}; found {len(selected)}")
        if args.max_decks and args.max_decks > 0:
            selected = select_representative_decks(selected, args.max_decks, guess_archetype_fn=guess_archetype)

        deck_pool: list[dict] = []
        for row in selected:
            if isinstance(row, dict):
                mainboard = row["mainboard"]
                deck_pool.append({"id": row.get("id"), "name": row["name"], "mainboard": mainboard})
            else:
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
                        meaningful_non_pass = any(
                            m.get("type") in {"play_land", "cast_spell", "activate_loyalty", "attack", "block"}
                            for m in legal
                        )
                        legal_has_land = any(m.get("type") == "play_land" for m in legal)
                        acted_type = action.get("type")
                        if (
                            acted_type == "pass_priority"
                            and meaningful_non_pass
                            and pid == state.active_player
                            and str(state.step) in {"Step.PRECOMBAT_MAIN", "Step.POSTCOMBAT_MAIN"}
                            and not state.stack
                        ):
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
                            "active_player": getattr(state, "active_player", None),
                            "priority_player": getattr(state, "priority_player", None),
                            "hand": hand_snapshot(state, pid),
                            "opp_hand": hand_snapshot(state, 1 if pid == 2 else 2),
                            "battlefield": battlefield_snapshot(state, pid),
                            "opp_battlefield": battlefield_snapshot(state, 1 if pid == 2 else 2),
                            "mana_pool": dict(state.players[pid].mana_pool),
                            "graveyard_count": len(state.players[pid].graveyard),
                            "opp_graveyard_count": len(state.players[1 if pid == 2 else 2].graveyard),
                            "library_count": len(state.players[pid].library),
                            "opp_library_count": len(state.players[1 if pid == 2 else 2].library),
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

                    termination_status = classify_timeout_state(state.log, bool(state.winner is None))
                    if termination_status != "resolved":
                        pair_counts[termination_status] += 1
                        if termination_status == "timeout_long_game":
                            pair_counts["long_game_timeouts"] += 1
                        else:
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
                        "termination_status": termination_status,
                        "passed_with_options": passed_with_options,
                        "missed_land_windows": missed_land_windows,
                        "stall_streaks": int(stalled_pass_streak >= 3),
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
                    "long_game_timeouts": int(pair_counts["long_game_timeouts"]),
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
            "long_game_timeouts": int(global_counts["long_game_timeouts"]),
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
            "anomaly_clusters_json": str(run_dir / "anomaly-clusters.json"),
        },
    }
    _write_anomaly_clusters(anomalies_path, run_dir / "anomaly-clusters.json")
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["output"], indent=2))
    return 0


def _write_anomaly_clusters(anomaly_games_path: Path, out_path: Path) -> None:
    clusters: Counter = Counter()
    samples: dict[str, list[dict]] = {}
    if not anomaly_games_path.exists():
        out_path.write_text(json.dumps({"total_games": 0, "clusters": []}, indent=2), encoding="utf-8")
        return
    with anomaly_games_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            labels = _cluster_labels(row)
            key = "+".join(sorted(labels))
            clusters[key] += 1
            samples.setdefault(key, [])
            if len(samples[key]) < 3:
                samples[key].append(
                    {
                        "deck_a": row.get("deck_a"),
                        "deck_b": row.get("deck_b"),
                        "game_index": row.get("game_index"),
                        "winner": row.get("winner"),
                        "turns": row.get("turns"),
                    }
                )
    payload = {
        "total_games": int(sum(clusters.values())),
        "clusters": [{"label": k, "count": int(v), "samples": samples.get(k, [])} for k, v in clusters.most_common()],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _cluster_labels(row: dict) -> list[str]:
    """Classify recorded anomalies from structured counters, not every pass log line."""
    log_text = "\n".join(row.get("log", []) or [])
    labels: list[str] = []
    if re.search(r"invalid targets", log_text, re.IGNORECASE):
        labels.append("invalid_targets")
    if re.search(r"cannot pay|cannot satisfy chosen costs", log_text, re.IGNORECASE):
        labels.append("cannot_pay")
    if int(row.get("missed_land_windows", 0) or 0) > 0:
        labels.append("land_miss")
    if int(row.get("stall_streaks", 0) or 0) > 0:
        labels.append("stall")
    elif int(row.get("passed_with_options", 0) or 0) > 0:
        labels.append("pass_with_legal_action")
    if row.get("termination_status") == "timeout_long_game":
        labels.append("long_game")
    return labels or ["other"]


if __name__ == "__main__":
    raise SystemExit(run())
