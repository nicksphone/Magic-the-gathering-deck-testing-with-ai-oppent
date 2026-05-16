from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

PRIORS_PATH = Path(__file__).resolve().parent / "data" / "log_priors.json"


def load_log_priors() -> dict[str, Any]:
    if not PRIORS_PATH.exists():
        return {"generated_at": None, "samples": {"games": 0, "logs": 0}, "cards": {}}
    try:
        payload = json.loads(PRIORS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "samples": {"games": 0, "logs": 0}, "cards": {}}
    if not isinstance(payload, dict):
        return {"generated_at": None, "samples": {"games": 0, "logs": 0}, "cards": {}}
    payload.setdefault("generated_at", None)
    payload.setdefault("samples", {"games": 0, "logs": 0})
    payload.setdefault("cards", {})
    return payload


def save_log_priors(payload: dict[str, Any]) -> dict[str, Any]:
    PRIORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = dict(payload or {})
    out["generated_at"] = datetime.now(UTC).isoformat()
    out.setdefault("samples", {"games": 0, "logs": 0})
    out.setdefault("cards", {})
    PRIORS_PATH.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    return out


def build_priors_from_logs(logs: list[list[str]]) -> dict[str, Any]:
    card_turns: dict[str, list[int]] = {}
    card_seen: dict[str, int] = {}
    total_logs = 0
    games = 0

    for lines in logs:
        if not lines:
            continue
        games += 1
        total_logs += len(lines)
        current_turn = 1
        for line in lines:
            if "AI TRACE {" in line and "\"turn\":" in line:
                try:
                    trace_json = line.split("AI TRACE ", 1)[1]
                    data = json.loads(trace_json)
                    current_turn = int(data.get("turn", current_turn) or current_turn)
                    hand = data.get("hand") or []
                    for name in hand:
                        key = str(name).strip().lower()
                        if key:
                            card_seen[key] = card_seen.get(key, 0) + 1
                except Exception:
                    pass
                continue
            marker = " casts/activates "
            if marker in line:
                try:
                    name = line.split(marker, 1)[1].strip().rstrip(".")
                except Exception:
                    continue
                key = name.lower()
                if not key:
                    continue
                card_turns.setdefault(key, []).append(max(1, current_turn))

    cards: dict[str, Any] = {}
    for name, turns in card_turns.items():
        casts = len(turns)
        avg_turn = sum(turns) / casts
        early = sum(1 for t in turns if t <= 3)
        mid = sum(1 for t in turns if 4 <= t <= 7)
        late = sum(1 for t in turns if t >= 8)
        if casts >= 3:
            cards[name] = {
                "casts": casts,
                "seen_in_logs": int(card_seen.get(name, 0)),
                "avg_turn": round(avg_turn, 3),
                "early_turn_cast_rate": round(early / casts, 3),
                "mid_turn_cast_rate": round(mid / casts, 3),
                "late_turn_cast_rate": round(late / casts, 3),
                "preferred_min_turn": max(1, int(round(avg_turn - 1.0))),
            }

    return {
        "generated_at": None,
        "samples": {"games": games, "logs": total_logs},
        "cards": cards,
    }

