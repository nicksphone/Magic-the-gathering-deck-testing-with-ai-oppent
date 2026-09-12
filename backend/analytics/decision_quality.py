from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from analytics.decision_taxonomy import has_actionable_move, has_meaningful_move
from rules_engine.continuous import effective_power, effective_toughness
from rules_engine.engine import RulesEngine
from game_state.state import Zone


DECISION_QUALITY_METRICS = (
    "missed_land_drops",
    "unused_mana_passes",
    "lethal_misses",
    "bad_blocks",
    "stall_streaks",
)
_TRACE_METRICS = DECISION_QUALITY_METRICS
UNAVAILABLE_REASON = "complete per-player AI decision trace evidence absent"


def _step_key(step: object) -> str:
    return str(step or "").split(".")[-1].strip().lower()


def _mana_total(mana_pool: object) -> int | None:
    if not isinstance(mana_pool, dict):
        return None
    total = 0
    for value in mana_pool.values():
        if value is None or isinstance(value, (bool, list, tuple, set, dict)):
            return None
        try:
            amount = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        total += max(0, amount)
    return total


def compact_action(action: dict[str, Any]) -> dict[str, Any]:
    out = {"type": action.get("type")}
    for key in ("card_id", "card_name", "ability_index", "selected_face_index", "x_value"):
        if key in action:
            out[key] = action[key]
    for key in ("attackers", "blocks", "targets", "cost_choice"):
        if key in action:
            out[key] = action[key]
    return out


def _battlefield_snapshot(state: Any, pid: int) -> list[dict[str, Any]]:
    return [
        {
            "id": cid,
            "name": state.cards[cid].name,
            "types": list(getattr(state.cards[cid], "types", []) or []),
            "tapped": bool(getattr(state.cards[cid], "tapped", False)),
            "power": effective_power(state, cid),
            "toughness": effective_toughness(state, cid),
        }
        for cid in state.players[pid].battlefield
    ]


def _resolution_is_paused(state: Any) -> bool:
    return bool(
        getattr(state, "pending_replacement_choice", None)
        or getattr(state, "pending_trigger_order", None)
    )


def _resolve_stack_bounded(engine: RulesEngine, state: Any, *, limit: int = 32) -> bool:
    for _ in range(limit):
        if _resolution_is_paused(state):
            return False
        if not state.stack:
            return True
        engine.next_step(state)
    return not state.stack and not _resolution_is_paused(state)


def _lethal_attack_available(state: Any, pid: int, legal_moves: list[dict[str, Any]]) -> bool | None:
    if _step_key(state.step) != "declare_attackers":
        return False
    opponent_pid = 1 if pid == 2 else 2
    if any("Creature" in state.cards[cid].types for cid in state.players[opponent_pid].battlefield):
        return False
    attack_move = next((move for move in legal_moves if move.get("type") == "attack"), None)
    if attack_move is None:
        return False
    declaration = dict(attack_move)
    declaration["attackers"] = list(attack_move.get("attackers") or attack_move.get("options") or [])
    if not declaration["attackers"]:
        return False

    try:
        simulated_state = copy.deepcopy(state)
        engine = RulesEngine()
        engine.take_action(simulated_state, pid, declaration)
        if not simulated_state.attackers:
            return False
        if not _resolve_stack_bounded(engine, simulated_state):
            return None
        if simulated_state.winner is not None:
            return simulated_state.winner == pid
        if any(
            "Creature" in simulated_state.cards[cid].types
            for cid in simulated_state.players[opponent_pid].battlefield
        ):
            return None
        simulated_state.step = simulated_state.step.DECLARE_BLOCKERS
        simulated_state.priority_player = opponent_pid
        simulated_state.blockers_declared = False
        engine.take_action(simulated_state, opponent_pid, {"type": "block", "blocks": {}})
        if not _resolve_stack_bounded(engine, simulated_state):
            return None
        if simulated_state.winner is not None:
            return simulated_state.winner == pid
        engine.take_action(simulated_state, pid, {"type": "combat_damage"})
        if _resolution_is_paused(simulated_state) or simulated_state.stack:
            return None
        return simulated_state.winner == pid or simulated_state.players[opponent_pid].life <= 0
    except Exception:
        return None


def _simulate_block_line(
    state: Any,
    pid: int,
    action: dict[str, Any],
) -> tuple[Any, dict[str, list[str]]] | None:
    simulated_state = copy.deepcopy(state)
    engine = RulesEngine()
    if not any(move.get("type") == "block" for move in engine.legal_moves(simulated_state, pid)):
        return None
    engine.take_action(simulated_state, pid, action)
    accepted_blocks = {
        attacker_id: list(blocker_ids)
        for attacker_id, blocker_ids in simulated_state.blocks.items()
    }
    if not _resolve_stack_bounded(engine, simulated_state):
        return None
    engine.take_action(
        simulated_state,
        simulated_state.active_player,
        {"type": "combat_damage"},
    )
    if (
        _resolution_is_paused(simulated_state)
        or simulated_state.stack
        or simulated_state.attackers
        or simulated_state.blocks
    ):
        return None
    return simulated_state, accepted_blocks


def _player_lost(state: Any, pid: int) -> bool:
    return state.winner not in (None, pid) or state.players[pid].life <= 0


def _validated_bad_blocks(state: Any, pid: int, action: dict[str, Any]) -> int | None:
    """Count clearly dominated chumps using chosen and no-block engine outcomes."""
    if action.get("type") != "block":
        return 0
    if (
        _step_key(getattr(state, "step", None)) != "declare_blockers"
        or getattr(state, "priority_player", None) != pid
        or getattr(state, "active_player", None) == pid
        or getattr(state, "blockers_declared", False)
        or getattr(state, "stack", None)
        or not isinstance(action.get("blocks"), dict)
    ):
        return None

    requested_blocks = action["blocks"]
    requested_count = sum(len(value) if isinstance(value, list) else 1 for value in requested_blocks.values())
    if len(getattr(state, "attackers", [])) > 16 or requested_count > 16:
        return None

    try:
        chosen_result = _simulate_block_line(state, pid, action)
        baseline_result = _simulate_block_line(state, pid, {"type": "block", "blocks": {}})
        if chosen_result is None or baseline_result is None:
            return None
        chosen_state, accepted_blocks = chosen_result
        baseline_state, baseline_blocks = baseline_result
        if baseline_blocks:
            return None
        if _player_lost(baseline_state, pid):
            return 0
        if _player_lost(chosen_state, pid):
            return None
    except Exception:
        return None

    return sum(
        1
        for attacker_id, blocker_ids in accepted_blocks.items()
        if chosen_state.cards.get(attacker_id) is not None
        and chosen_state.cards[attacker_id].zone == Zone.BATTLEFIELD
        and any(
            chosen_state.cards.get(blocker_id) is not None
            and chosen_state.cards[blocker_id].zone == Zone.GRAVEYARD
            for blocker_id in blocker_ids
        )
    )


def build_trace_payload(
    state: Any,
    pid: int,
    legal_moves: list[dict[str, Any]],
    action: dict[str, Any],
    reasoning: str = "",
) -> dict[str, Any]:
    """Capture authoritative decision evidence before mutating match state."""
    opponent_pid = 1 if pid == 2 else 2
    legal_non_pass = has_actionable_move(legal_moves)
    meaningful_non_pass = has_meaningful_move(legal_moves)
    stall_actionable = (
        meaningful_non_pass
        and pid == state.active_player
        and _step_key(state.step) in {"precombat_main", "postcombat_main"}
        and not state.stack
    )
    return {
        "trace": True,
        "pid": pid,
        "turn": state.turn,
        "step": str(state.step),
        "active_player": state.active_player,
        "priority_player": state.priority_player,
        "hand": sorted(state.cards[cid].name for cid in state.players[pid].hand),
        "opp_hand": sorted(state.cards[cid].name for cid in state.players[opponent_pid].hand),
        "battlefield": _battlefield_snapshot(state, pid),
        "opp_battlefield": _battlefield_snapshot(state, opponent_pid),
        "mana_pool": dict(state.players[pid].mana_pool),
        "life": {"self": state.players[pid].life, "opp": state.players[opponent_pid].life},
        "legal_non_pass": legal_non_pass,
        "legal_has_land": any(move.get("type") == "play_land" for move in legal_moves),
        "lethal_attack_available": _lethal_attack_available(state, pid, legal_moves),
        "bad_blocks": _validated_bad_blocks(state, pid, action),
        "stall_actionable_options": bool(stall_actionable),
        "action": compact_action(action),
        "reasoning": reasoning,
    }


def losing_blocks(payload: dict[str, Any]) -> int | None:
    """Read the producer-validated count for a selected block assignment."""
    action = payload.get("action")
    if not isinstance(action, dict) or action.get("type") != "block":
        return 0
    value = payload.get("bad_blocks")
    if type(value) is not int or value < 0:
        return None
    return value


def parse_trace_row(row: object) -> tuple[list[dict[str, Any]], bool]:
    """Parse one game's trace lines without trusting JSONL or payload shapes."""
    if not isinstance(row, dict) or not isinstance(row.get("log"), list):
        return [], True
    payloads: list[dict[str, Any]] = []
    malformed = False
    for log_line in row["log"]:
        if not isinstance(log_line, str):
            malformed = True
            continue
        if not log_line.startswith("AI TRACE "):
            continue
        try:
            payload = json.loads(log_line[len("AI TRACE ") :])
        except (TypeError, json.JSONDecodeError):
            malformed = True
            continue
        if not isinstance(payload, dict):
            malformed = True
            continue
        payloads.append(payload)
    return payloads, malformed


def summarize_trace_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize authoritative AI trace evidence by player id."""
    expected_pids = ("1", "2")
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    evidence_complete = {
        pid: {metric: True for metric in _TRACE_METRICS}
        for pid in expected_pids
    }
    rows_consumed = 0

    for row in rows:
        rows_consumed += 1
        row_trace_seen: set[str] = set()
        malformed_trace = False
        stall_runs = {pid: 0 for pid in expected_pids}
        land_opportunities: set[tuple[str, int]] = set()
        land_plays: set[tuple[str, int]] = set()
        completed_turns: set[int] = set()
        row_evidence_complete = {
            pid: {metric: True for metric in _TRACE_METRICS}
            for pid in expected_pids
        }
        if isinstance(row, dict) and "_trace_payloads" in row:
            payloads = row["_trace_payloads"]
            malformed_trace = bool(row.get("_trace_malformed"))
        else:
            payloads, malformed_trace = parse_trace_row(row)
        for payload in payloads:
            pid = str(payload.get("pid"))
            if pid not in expected_pids:
                continue
            row_trace_seen.add(pid)
            action = payload.get("action")
            raw_action_type = action.get("type") if isinstance(action, dict) else None
            action_type = (
                raw_action_type
                if isinstance(raw_action_type, str) and raw_action_type.strip()
                else None
            )
            step = _step_key(payload.get("step"))

            turn = payload.get("turn")
            if type(turn) is int and turn >= 0 and step in {"end_step", "cleanup"}:
                completed_turns.add(turn)

            if not step:
                row_evidence_complete[pid]["missed_land_drops"] = False
                row_evidence_complete[pid]["lethal_misses"] = False
            if action_type is None:
                row_evidence_complete[pid]["missed_land_drops"] = False
                row_evidence_complete[pid]["unused_mana_passes"] = False
                row_evidence_complete[pid]["lethal_misses"] = False
                row_evidence_complete[pid]["bad_blocks"] = False

            if step in {"precombat_main", "postcombat_main"}:
                if not (
                    isinstance(payload.get("legal_non_pass"), bool)
                    and isinstance(payload.get("legal_has_land"), bool)
                    and action_type is not None
                    and type(turn) is int
                    and turn >= 0
                ):
                    row_evidence_complete[pid]["missed_land_drops"] = False
                else:
                    turn_key = (pid, turn)
                    if payload["legal_non_pass"] and payload["legal_has_land"]:
                        land_opportunities.add(turn_key)
                    if action_type == "play_land":
                        land_plays.add(turn_key)

            if action_type == "pass_priority":
                mana_pool = payload.get("mana_pool")
                mana_total = _mana_total(mana_pool)
                if not isinstance(payload.get("legal_non_pass"), bool) or mana_total is None:
                    row_evidence_complete[pid]["unused_mana_passes"] = False
                elif payload["legal_non_pass"] and mana_total > 0:
                    counts[pid]["unused_mana_passes"] += 1

            stall_actionable = payload.get("stall_actionable_options")
            if action_type is None or not isinstance(stall_actionable, bool):
                row_evidence_complete[pid]["stall_streaks"] = False
                stall_runs[pid] = 0
            elif action_type == "pass_priority" and stall_actionable:
                stall_runs[pid] += 1
            else:
                if stall_runs[pid] >= 3:
                    counts[pid]["stall_streaks"] += 1
                stall_runs[pid] = 0

            if step == "declare_attackers":
                lethal_available = payload.get("lethal_attack_available")
                if not isinstance(lethal_available, bool):
                    row_evidence_complete[pid]["lethal_misses"] = False
                elif lethal_available and action_type != "attack":
                    counts[pid]["lethal_misses"] += 1

            bad_blocks = losing_blocks(payload)
            if bad_blocks is None:
                row_evidence_complete[pid]["bad_blocks"] = False
            else:
                counts[pid]["bad_blocks"] += bad_blocks

        for pid in expected_pids:
            counts[pid]["missed_land_drops"] += sum(
                1
                for turn_pid, turn in land_opportunities - land_plays
                if turn_pid == pid and turn in completed_turns
            )
            if stall_runs[pid] >= 3:
                counts[pid]["stall_streaks"] += 1
            for metric in _TRACE_METRICS:
                evidence_complete[pid][metric] = (
                    evidence_complete[pid][metric]
                    and not malformed_trace
                    and pid in row_trace_seen
                    and row_evidence_complete[pid][metric]
                )

    return {
        "counts": {
            pid: {metric: int(counts[pid][metric]) for metric in _TRACE_METRICS}
            for pid in expected_pids
        },
        "availability": {
            pid: {
                metric: bool(rows_consumed and evidence_complete[pid][metric])
                for metric in _TRACE_METRICS
            }
            for pid in expected_pids
        },
    }


class DecisionQualityAccumulator:
    """Online shared parser and decision-quality summary accumulator."""

    def __init__(self) -> None:
        self._rows_consumed = 0
        self._counts = {pid: Counter() for pid in ("1", "2")}
        self._availability = {
            pid: {metric: True for metric in _TRACE_METRICS}
            for pid in ("1", "2")
        }
        self._producer_evidence_seen = {
            pid: {"bad_blocks": False, "stall_streaks": False}
            for pid in ("1", "2")
        }

    def invalidate_all(self) -> None:
        for metrics in self._availability.values():
            for metric in _TRACE_METRICS:
                metrics[metric] = False

    def invalidate_metric(self, pid: str, metric: str) -> None:
        self._availability[pid][metric] = False

    def consume_row(self, row: object) -> list[dict[str, Any]]:
        self._rows_consumed += 1
        payloads, malformed = parse_trace_row(row)
        for payload in payloads:
            pid = str(payload.get("pid"))
            if pid in self._producer_evidence_seen:
                if "bad_blocks" in payload:
                    self._producer_evidence_seen[pid]["bad_blocks"] = True
                if "stall_actionable_options" in payload:
                    self._producer_evidence_seen[pid]["stall_streaks"] = True
        summary = summarize_trace_rows(({
            "_trace_payloads": payloads,
            "_trace_malformed": malformed,
        },))
        for pid in ("1", "2"):
            self._counts[pid].update(summary["counts"][pid])
            for metric in _TRACE_METRICS:
                self._availability[pid][metric] = (
                    self._availability[pid][metric]
                    and summary["availability"][pid][metric]
                )
        return payloads

    def finish(self) -> dict[str, Any]:
        if not self._rows_consumed:
            self.invalidate_all()
        for pid, evidence in self._producer_evidence_seen.items():
            for metric, seen in evidence.items():
                if not seen:
                    self._availability[pid][metric] = False
        availability = {
            pid: dict(metrics) for pid, metrics in self._availability.items()
        }
        counts = {
            pid: {metric: int(self._counts[pid][metric]) for metric in _TRACE_METRICS}
            for pid in ("1", "2")
        }
        return {
            "counts": counts,
            "availability": availability,
            "unavailable_metrics": {
                pid: {
                    metric: UNAVAILABLE_REASON
                    for metric, available in availability[pid].items()
                    if not available
                }
                for pid in ("1", "2")
            },
        }


def deck_artifact_entries(decks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return collision-safe, deterministic identities in source pool order."""
    candidates = [
        (
            f"source:{deck.get('source', '')}:id:{type(deck.get('id')).__name__}:"
            f"{deck.get('id')}"
        )
        if deck.get("id") is not None
        else None
        for deck in decks
    ]
    frequencies = Counter(candidate for candidate in candidates if candidate is not None)
    entries = []
    for index, (deck, candidate) in enumerate(zip(decks, candidates, strict=True)):
        deck_key = candidate if candidate is not None and frequencies[candidate] == 1 else f"pool:{index}"
        entries.append(
            {
                "deck_id": deck.get("id"),
                "deck_name": str(deck.get("name", "")),
                "deck_key": deck_key,
            }
        )
    return entries


def build_decision_quality_artifact(
    decks: list[dict[str, Any]],
    game_summaries: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build the shared service/overnight decision-quality artifact schema."""
    entries = deck_artifact_entries(decks)
    known = {entry["deck_key"] for entry in entries}
    counts = {key: Counter() for key in known}
    availability = {
        key: {metric: True for metric in DECISION_QUALITY_METRICS}
        for key in known
    }
    participated: set[str] = set()

    for game in game_summaries:
        seen_in_game: set[str] = set()
        for evidence in game.get("decks", []):
            key = evidence.get("deck_key")
            if key not in known:
                raise ValueError(f"decision-quality game references unknown deck key: {key!r}")
            if key in seen_in_game:
                raise ValueError(f"duplicate decision-quality evidence for deck key: {key!r}")
            seen_in_game.add(key)
            participated.add(key)
            for metric in DECISION_QUALITY_METRICS:
                measured = (evidence.get("availability") or {}).get(metric) is True
                availability[key][metric] = availability[key][metric] and measured
                if measured:
                    counts[key][metric] += int((evidence.get("counts") or {}).get(metric, 0))

    per_deck = []
    for entry in entries:
        key = entry["deck_key"]
        metrics = {
            metric: int(counts[key][metric])
            if key in participated and availability[key][metric]
            else None
            for metric in DECISION_QUALITY_METRICS
        }
        unavailable = {
            metric: UNAVAILABLE_REASON
            for metric, value in metrics.items()
            if value is None
        }
        per_deck.append({**entry, "metrics": metrics, "unavailable_metrics": unavailable})

    participating_rows = [
        row for row in per_deck if row["deck_key"] in participated
    ]
    overall = {
        metric: (
            sum(int(row["metrics"][metric]) for row in participating_rows)
            if participating_rows
            and all(row["metrics"][metric] is not None for row in participating_rows)
            else None
        )
        for metric in DECISION_QUALITY_METRICS
    }
    return {
        "per_deck": per_deck,
        "overall": overall,
        "unavailable_metrics": {
            metric: UNAVAILABLE_REASON
            for metric, value in overall.items()
            if value is None
        },
    }
