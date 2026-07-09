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
    if "attacks" in low:
        return "attack"
    if "blocks" in low:
        return "block"
    if "resolves" in low:
        return "resolve"
    if "draws a card" in low:
        return "draw"
    if "damage" in low:
        return "damage"
    if "trigger" in low:
        return "trigger"
    return "unknown"


def classify_first_divergence(drift: dict) -> dict:
    left = str(drift.get("a") or "")
    right = str(drift.get("b") or "")
    left_label = classify_log_line(left)
    right_label = classify_log_line(right)
    if left_label == right_label:
        category = left_label if left_label != "unknown" else "unknown"
    else:
        category = "action_mismatch"
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
    }
