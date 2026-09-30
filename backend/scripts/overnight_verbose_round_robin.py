from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import copy
import json
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import re
from typing import TextIO

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.decision_quality import (
    build_decision_quality_artifact,
    build_trace_payload,
    deck_artifact_entries,
    summarize_trace_rows,
)
from analytics.decision_taxonomy import decision_reason_code, has_actionable_move, has_meaningful_move, is_actionable_move
from analytics.replay_tools import classify_timeout_state
from analytics.service import AnalyticsService
from card_data.hydration import hydrate_deck_cards
from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from decks.selection import select_representative_decks
from game_state.state import MatchFactory, pregame_actor
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.continuous import effective_power
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
    for k in ["card_id", "card_name", "ability_index", "selected_face_index", "x_value"]:
        if k in action:
            out[k] = action[k]
    if isinstance(action.get("attackers"), list):
        out["attackers"] = list(action["attackers"])
    if isinstance(action.get("blocks"), dict):
        out["blocks"] = {str(key): value for key, value in action["blocks"].items()}
    if isinstance(action.get("targets"), dict) and action.get("targets"):
        out["targets"] = action["targets"]
    if isinstance(action.get("cost_choice"), dict) and action.get("cost_choice"):
        out["cost_choice"] = action["cost_choice"]
    return out


def hand_snapshot(state, pid: int) -> list[str]:
    names = [state.cards[cid].name for cid in state.players[pid].hand]
    names.sort()
    return names


def life_snapshot(state, pid: int) -> dict[str, int]:
    opponent_pid = 1 if pid == 2 else 2
    return {
        "self": state.players[pid].life,
        "opp": state.players[opponent_pid].life,
    }


def lethal_attack_available(state, pid: int, legal_moves: list[dict]) -> bool:
    """Return open-board lethal evidence from a validated attack declaration."""
    opponent_pid = 1 if pid == 2 else 2
    if any("Creature" in state.cards[cid].types for cid in state.players[opponent_pid].battlefield):
        return False
    attack_move = next((move for move in legal_moves if move.get("type") == "attack"), None)
    if attack_move is None:
        return False
    declaration = dict(attack_move)
    declaration["attackers"] = list(attack_move.get("attackers") or attack_move.get("options") or [])
    simulated_state = copy.deepcopy(state)
    RulesEngine().take_action(simulated_state, pid, declaration)
    legal_power = sum(max(0, effective_power(simulated_state, cid)) for cid in simulated_state.attackers)
    return legal_power >= state.players[opponent_pid].life


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
                "keywords": list(getattr(card, "keywords", []) or []),
                "loyalty": getattr(card, "loyalty", None),
                "selected_face_index": getattr(card, "selected_face_index", None),
            }
        )
    return sorted(out, key=lambda item: (item["name"], item["id"]))


def _deck_artifact(deck_pool: list[dict]) -> list[dict]:
    return sorted(
        [
            {"id": deck.get("id"), "name": deck["name"], "archetype": deck["archetype"]}
            for deck in deck_pool
        ],
        key=lambda deck: (deck["name"], str(deck["id"])),
    )


def _game_identity(left: dict, right: dict) -> dict:
    return {
        "deck_a": left["name"],
        "deck_a_id": left.get("id"),
        "deck_a_archetype": left["archetype"],
        "deck_b": right["name"],
        "deck_b_id": right.get("id"),
        "deck_b_archetype": right["archetype"],
    }


def _build_overnight_trace_payload(
    state,
    pid: int,
    legal_moves: list[dict],
    action: dict,
    reasoning: str,
    reason_code: str,
) -> dict:
    """Extend the shared authoritative trace with overnight-only diagnostics."""
    opponent_pid = 1 if pid == 2 else 2
    payload = build_trace_payload(state, pid, legal_moves, action, reasoning)
    payload.update(
        {
            "graveyard_count": len(state.players[pid].graveyard),
            "opp_graveyard_count": len(state.players[opponent_pid].graveyard),
            "library_count": len(state.players[pid].library),
            "opp_library_count": len(state.players[opponent_pid].library),
            "legal_non_pass_count": sum(1 for move in legal_moves if is_actionable_move(move)),
            "legal_action_types": sorted(
                {str(move.get("type")) for move in legal_moves if is_actionable_move(move)}
            ),
            "reason_code": reason_code,
        }
    )
    return payload


def _deck_quality_key(deck: dict) -> tuple[str, str]:
    deck_id = deck.get("id")
    return ("id", f"{type(deck_id).__name__}:{deck_id}") if deck_id is not None else ("name", str(deck["name"]))


def _decision_quality_game_summary(log: list[str], left: dict, right: dict) -> dict:
    summary = summarize_trace_rows(({"log": log},))
    return {
        "decks": [
            {
                "deck_ref": left,
                "counts": summary["counts"]["1"],
                "availability": summary["availability"]["1"],
            },
            {
                "deck_ref": right,
                "counts": summary["counts"]["2"],
                "availability": summary["availability"]["2"],
            },
        ]
    }


def _decision_quality_artifact(game_summaries: list[dict], decks: list[dict]) -> dict:
    entries = deck_artifact_entries(decks)
    keys_by_legacy_identity: dict[tuple[str, str], list[str]] = {}
    for deck, entry in zip(decks, entries, strict=True):
        keys_by_legacy_identity.setdefault(_deck_quality_key(deck), []).append(entry["deck_key"])

    normalized_games = []
    for game in game_summaries:
        raw_evidence = game.get("decks") or []
        evidence_rows = []
        if isinstance(raw_evidence, dict):
            for legacy_key, evidence in raw_evidence.items():
                matching = keys_by_legacy_identity.get(legacy_key, [])
                if len(matching) != 1:
                    raise ValueError(f"ambiguous decision-quality deck identity: {legacy_key!r}")
                evidence_rows.append({**evidence, "deck_key": matching[0]})
        else:
            for evidence in raw_evidence:
                deck_ref = evidence.get("deck_ref")
                matching = [
                    entry["deck_key"]
                    for deck, entry in zip(decks, entries, strict=True)
                    if deck is deck_ref
                ]
                if len(matching) != 1:
                    raise ValueError("decision-quality evidence does not reference one pool deck")
                evidence_rows.append(
                    {
                        "deck_key": matching[0],
                        "counts": evidence.get("counts") or {},
                        "availability": evidence.get("availability") or {},
                    }
                )
        normalized_games.append({"decks": evidence_rows})
    return build_decision_quality_artifact(decks, normalized_games)


def _write_game_record(
    game_record: dict,
    *,
    all_games: TextIO,
    anomalies: TextIO,
    write_full_log: bool,
    qualifies_as_anomaly: bool,
) -> None:
    encoded = json.dumps(game_record, ensure_ascii=True) + "\n"
    if write_full_log:
        all_games.write(encoded)
    if qualifies_as_anomaly:
        anomalies.write(encoded)


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
                mainboard = hydrate_deck_cards(repo, row["mainboard"])
                deck_pool.append(
                    {
                        "id": row.get("id"),
                        "name": row["name"],
                        "mainboard": mainboard,
                        "archetype": guess_archetype(mainboard),
                    }
                )
            else:
                mainboard = hydrate_deck_cards(repo, json.loads(row.mainboard_json))
                deck_pool.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "mainboard": mainboard,
                        "archetype": guess_archetype(mainboard),
                    }
                )

        total_pairs = len(list(combinations(deck_pool, 2)))
        total_games = total_pairs * args.matches_per_pair

        global_counts: Counter = Counter()
        top_errors: Counter = Counter()
        pair_summaries: list[dict] = []
        decision_quality_games: list[dict] = []

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

                left_arch = left["archetype"]
                right_arch = right["archetype"]

                for game_idx in range(args.matches_per_pair):
                    state = MatchFactory.from_decks(left["mainboard"], right["mainboard"], player_a_name=left["name"], player_b_name=right["name"])
                    a_agent = AIAgent(difficulty=args.difficulty, archetype=left_arch)
                    b_agent = AIAgent(difficulty=args.difficulty, archetype=right_arch)

                    ticks = 0
                    passed_with_options = 0
                    missed_land_windows = 0
                    stalled_pass_streak = 0
                    reason_codes: Counter = Counter()
                    while state.winner is None and ticks < args.max_ticks:
                        pid = pregame_actor(state) if state.pregame_pending else state.priority_player
                        legal = engine_rules.legal_moves(state, pid)
                        if not legal:
                            action = {"type": "pass_priority"}
                            reasoning = "No legal action"
                        else:
                            agent = a_agent if pid == 1 else b_agent
                            decision = agent.choose_action(state, legal, pid)
                            action = decision.action
                            reasoning = decision.reasoning

                        legal_non_pass = has_actionable_move(legal)
                        meaningful_non_pass = has_meaningful_move(legal)
                        legal_has_land = any(m.get("type") == "play_land" for m in legal)
                        reason_code = decision_reason_code(
                            action,
                            reasoning,
                            legal_non_pass=legal_non_pass,
                            meaningful_non_pass=meaningful_non_pass,
                            active_player=getattr(state, "active_player", None),
                            player_id=pid,
                            step=state.step,
                            stack_empty=not bool(state.stack),
                        )
                        reason_codes[reason_code] += 1
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
                        trace_line = _build_overnight_trace_payload(
                            state,
                            pid,
                            legal,
                            action,
                            reasoning,
                            reason_code,
                        )
                        state.log.append(f"AI TRACE {json.dumps(trace_line, separators=(',', ':'))}")

                        pre_len = len(state.log)
                        engine_rules.take_action(state, pid, action)
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
                    decision_quality_games.append(_decision_quality_game_summary(state.log, left, right))
                    pair_turns.append(state.turn)
                    game_counter += 1

                    game_record = {
                        **_game_identity(left, right),
                        "game_index": game_idx + 1,
                        "winner": state.winner,
                        "turns": state.turn,
                        "ticks": ticks,
                        "timeouts": int(state.winner is None),
                        "termination_status": termination_status,
                        "passed_with_options": passed_with_options,
                        "missed_land_windows": missed_land_windows,
                        "stall_streaks": int(stalled_pass_streak >= 3),
                        "reason_codes": dict(reason_codes),
                        "pass_reason_codes": {
                            code: count
                            for code, count in reason_codes.items()
                            if code.startswith("pass_") or code == "hold_up_interaction"
                        },
                    }

                    has_anomaly = any(k in pair_counts for k in ["invalid_targets", "cost_failures", "additional_cost_failures", "repeated_error_bursts"]) and any(
                        x in "\n".join(state.log).lower() for x in ["invalid targets for", "cannot pay mana cost", "cannot satisfy chosen costs", "failed additional costs"]
                    )
                    has_behavior_anomaly = passed_with_options > 0 or missed_land_windows > 0 or stalled_pass_streak >= 3

                    qualifies_as_anomaly = has_anomaly or has_behavior_anomaly or state.winner is None
                    if args.write_full_log_for_all_games or qualifies_as_anomaly:
                        game_record["log"] = state.log
                    _write_game_record(
                        game_record,
                        all_games=all_games,
                        anomalies=anomalies,
                        write_full_log=args.write_full_log_for_all_games,
                        qualifies_as_anomaly=qualifies_as_anomaly,
                    )

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
        "decks": _deck_artifact(deck_pool),
        "decision_quality": _decision_quality_artifact(decision_quality_games, deck_pool),
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
        pass_reasons = row.get("pass_reason_codes") or {}
        if int(pass_reasons.get("hold_up_interaction", 0) or 0) > 0:
            labels.append("pass_hold_up_interaction")
        if int(pass_reasons.get("pass_with_meaningful_option", 0) or 0) > 0:
            labels.append("pass_with_legal_action")
        if not labels or labels[-1] not in {"pass_hold_up_interaction", "pass_with_legal_action"}:
            labels.append("pass_with_legal_action")
    if row.get("termination_status") == "timeout_long_game":
        labels.append("long_game")
    return labels or ["other"]


if __name__ == "__main__":
    raise SystemExit(run())
