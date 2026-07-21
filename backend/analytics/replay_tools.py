from __future__ import annotations

import json
import re

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)


def normalize_log_line(line: str) -> str:
    return UUID_RE.sub("<id>", line)


def first_log_divergence(a_lines: list[str], b_lines: list[str]) -> dict:
    a_lines = [normalize_log_line(line) for line in a_lines]
    b_lines = [normalize_log_line(line) for line in b_lines]
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


def classify_log_line(line: str) -> str:
    if not line:
        return "unknown"
    if line.startswith("AI TRACE "):
        try:
            payload = json.loads(line[len("AI TRACE ") :])
            action = payload.get("action") or {}
            return str(action.get("type") or "unknown")
        except Exception:
            return "unknown"
    low = line.lower()
    if "mulligan" in low:
        return "mulligan"
    if "plays " in low and "land" in low:
        return "play_land"
    if "casts/activates" in low:
        return "cast_spell"
    if "passes priority" in low or low.endswith("pass priority.") or " passes priority" in low:
        return "pass_priority"
    if "attackers declared" in low or "attacks" in low:
        return "attack"
    if "blocks declared" in low or "blocks" in low:
        return "block"
    if "creates " in low or "enters the battlefield" in low:
        return "etb"
    if "sacrifices " in low:
        return "sacrifice"
    if "discards " in low:
        return "discard"
    if "resolves" in low:
        return "resolve"
    if "draws a card" in low:
        return "draw"
    if "damage" in low:
        return "damage"
    if "trigger" in low:
        return "trigger"
    if "dies" in low or "put into graveyard" in low:
        return "death"
    return "unknown"


def classify_first_divergence(drift: dict) -> dict:
    left = str(drift.get("a") or "")
    right = str(drift.get("b") or "")
    left_label = classify_log_line(left)
    right_label = classify_log_line(right)
    category = _classify_divergence_category(left, right, left_label, right_label)
    return {
        "category": category,
        "action_a": left_label,
        "action_b": right_label,
        "line_a": left,
        "line_b": right,
        "index": drift.get("index", -1),
        "context_before": drift.get("context_before", []),
        "context_after_a": drift.get("context_after_a", []),
        "context_after_b": drift.get("context_after_b", []),
        "trace_context_a": _trace_context_summary(left),
        "trace_context_b": _trace_context_summary(right),
    }


def classify_timeout_state(log: list[str], timeout: bool) -> str:
    if not timeout:
        return "resolved"
    if not log:
        return "timeout_unknown"
    lowered = [line.lower() for line in log]
    trace_count = sum(1 for line in log if line.startswith("AI TRACE "))
    trace_payloads = [_parse_ai_trace_payload(line) for line in log if line.startswith("AI TRACE ")]
    trace_payloads = [payload for payload in trace_payloads if payload]
    if trace_count >= 10 and not any(
        token in " ".join(lowered)
        for token in ["invalid targets", "cannot pay", "ward tax", "missed land-play window", "land in hand but no land play available"]
    ):
        if any(
            payload.get("legal_meaningful", payload.get("legal_non_pass"))
            and (payload.get("action") or {}).get("type") == "pass_priority"
            and str(payload.get("step", "")).split(".")[-1].lower() in {"precombat_main", "postcombat_main"}
            and int(payload.get("active_player", -1)) == int(payload.get("pid", -2))
            for payload in trace_payloads
        ):
            return "likely_stall"
        return "timeout_long_game"
    if any("passes priority" in line for line in lowered):
        pass_streak = 0
        for line in lowered:
            if "passes priority" in line:
                pass_streak += 1
                if pass_streak >= 4:
                    return "likely_stall"
            else:
                pass_streak = 0
    if any(token in " ".join(lowered) for token in ["invalid targets", "cannot pay", "ward tax", "missed land-play window", "land in hand but no land play available"]):
        return "timeout_rules_issue"
    return "timeout_unknown"


def _classify_divergence_category(left: str, right: str, left_label: str, right_label: str) -> str:
    if left_label != right_label:
        if "pass_priority" in {left_label, right_label}:
            return "pass_vs_action"
        if {left_label, right_label} == {"play_land", "cast_spell"}:
            return "land_vs_spell_choice"
        return "action_mismatch"

    low = f"{left} {right}".lower()
    left_payload = _parse_ai_trace_payload(left)
    right_payload = _parse_ai_trace_payload(right)
    if left_label == "pass_priority":
        if "main phase" in low or "stack=0" in low or "hold up" in low or "passes priority" in low:
            return "pass_loop"
        return "pass_priority"
    if left_label == "play_land":
        return "land_drop_mismatch" if left != right else "play_land"
    if left_label in {"attack", "block", "damage", "trigger", "etb", "sacrifice", "discard", "death"}:
        if left != right:
            return f"{left_label}_mismatch"
        return left_label
    if left_label == "cast_spell":
        if left_payload and right_payload:
            left_action = left_payload.get("action") or {}
            right_action = right_payload.get("action") or {}
            if left_action.get("selected_face_index") != right_action.get("selected_face_index"):
                return "face_choice_mismatch"
            left_targets = left_action.get("targets") or {}
            right_targets = right_action.get("targets") or {}
            if left_targets.get("target_stack_id") != right_targets.get("target_stack_id"):
                return "stack_target_mismatch"
            if left_targets.get("mode_text") != right_targets.get("mode_text"):
                return "mode_choice_mismatch"
            if left_targets.get("mode_texts") != right_targets.get("mode_texts"):
                return "mode_choice_mismatch"
        if "cannot pay" in low or "invalid targets" in low or "x value is required" in low or "ward tax" in low:
            return "cast_resolution_error"
        if left != right:
            return "cast_choice_mismatch"
        return "cast_spell"
    if left_label == "unknown":
        if "cannot pay" in low or "invalid targets" in low or "x value is required" in low:
            return "cast_resolution_error"
        return "unknown"
    return left_label


def _parse_ai_trace_payload(line: str) -> dict | None:
    if not line.startswith("AI TRACE "):
        return None
    try:
        payload = json.loads(line[len("AI TRACE ") :])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _trace_context_summary(line: str) -> dict:
    payload = _parse_ai_trace_payload(line)
    if not payload:
        return {}
    hand = list(payload.get("hand") or [])
    opp_hand = list(payload.get("opp_hand") or [])
    battlefield = list(payload.get("battlefield") or [])
    opp_battlefield = list(payload.get("opp_battlefield") or [])
    life = payload.get("life") or {}
    return {
        "pid": payload.get("pid"),
        "turn": payload.get("turn"),
        "step": payload.get("step"),
        "active_player": payload.get("active_player"),
        "priority_player": payload.get("priority_player"),
        "hand_size": len(hand),
        "opp_hand_size": len(opp_hand),
        "battlefield_size": len(battlefield),
        "opp_battlefield_size": len(opp_battlefield),
        "life_self": life.get("self"),
        "life_opp": life.get("opp"),
        "legal_non_pass": payload.get("legal_non_pass"),
        "legal_has_land": payload.get("legal_has_land"),
        "action_type": (payload.get("action") or {}).get("type"),
    }
