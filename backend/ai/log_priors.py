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
    card_role_turns: dict[str, dict[str, list[int]]] = {}
    card_seen: dict[str, int] = {}
    total_logs = 0
    games = 0

    for lines in logs:
        if not lines:
            continue
        games += 1
        total_logs += len(lines)
        current_turn = 1
        current_board_role = "normal"
        for line in lines:
            if "AI TRACE {" in line and "\"turn\":" in line:
                try:
                    trace_json = line.split("AI TRACE ", 1)[1]
                    data = json.loads(trace_json)
                except Exception:
                    continue
                current_turn = int(data.get("turn", current_turn) or current_turn)
                current_board_role = _board_role_hint(data)
                hand = data.get("hand") or []
                for name in hand:
                    key = str(name).strip().lower()
                    if key:
                        card_seen[key] = card_seen.get(key, 0) + 1
                continue
            marker = " casts/activates "
            if marker in line:
                try:
                    name = line.split(marker, 1)[1].strip().rstrip(".")
                except Exception:
                    continue
                _record_card_timing(card_turns, card_role_turns, name, current_turn, current_board_role)

    return _build_priors_payload(card_turns, card_role_turns, card_seen, games, total_logs)


def build_priors_from_examples(examples: list[dict[str, Any]]) -> dict[str, Any]:
    card_turns: dict[str, list[int]] = {}
    card_role_turns: dict[str, dict[str, list[int]]] = {}
    card_seen: dict[str, int] = {}
    games_seen: set[Any] = set()
    total_logs = 0
    for row in examples:
        if not isinstance(row, dict):
            continue
        card_name = str(row.get("action_card_name") or "").strip()
        action_type = str(row.get("action_type") or "").strip()
        if not card_name or action_type not in {"cast_spell", "activate_ability", "play_land"}:
            continue
        turn = int(row.get("turn", 1) or 1)
        board_role = str(row.get("board_role_hint") or "normal").strip().lower() or "normal"
        _record_card_timing(card_turns, card_role_turns, card_name, turn, board_role)
        key = card_name.lower()
        card_seen[key] = card_seen.get(key, 0) + 1
        if row.get("game") is not None:
            games_seen.add(row.get("game"))
        total_logs += 1
    return _build_priors_payload(card_turns, card_role_turns, card_seen, len(games_seen), total_logs)


def _record_card_timing(
    card_turns: dict[str, list[int]],
    card_role_turns: dict[str, dict[str, list[int]]],
    name: str,
    turn: int,
    role: str,
) -> None:
    key = str(name).strip().lower()
    if not key:
        return
    current_turn = max(1, int(turn or 1))
    current_role = (role or "normal").strip().lower() or "normal"
    card_turns.setdefault(key, []).append(current_turn)
    card_role_turns.setdefault(key, {}).setdefault(current_role, []).append(current_turn)


def _build_priors_payload(
    card_turns: dict[str, list[int]],
    card_role_turns: dict[str, dict[str, list[int]]],
    card_seen: dict[str, int],
    games: int,
    total_logs: int,
) -> dict[str, Any]:
    cards: dict[str, Any] = {}
    for name, turns in card_turns.items():
        casts = len(turns)
        avg_turn = sum(turns) / casts
        early = sum(1 for t in turns if t <= 3)
        mid = sum(1 for t in turns if 4 <= t <= 7)
        late = sum(1 for t in turns if t >= 8)
        if casts < 3:
            continue
        role_rows: dict[str, Any] = {}
        for role, role_turns in card_role_turns.get(name, {}).items():
            role_casts = len(role_turns)
            if role_casts < 2:
                continue
            role_avg = sum(role_turns) / role_casts
            role_rows[role] = {
                "casts": role_casts,
                "avg_turn": round(role_avg, 3),
                "early_turn_cast_rate": round(sum(1 for t in role_turns if t <= 3) / role_casts, 3),
                "mid_turn_cast_rate": round(sum(1 for t in role_turns if 4 <= t <= 7) / role_casts, 3),
                "late_turn_cast_rate": round(sum(1 for t in role_turns if t >= 8) / role_casts, 3),
                "preferred_min_turn": max(1, int(round(role_avg - 1.0))),
            }
        cards[name] = {
            "casts": casts,
            "seen_in_logs": int(card_seen.get(name, 0)),
            "avg_turn": round(avg_turn, 3),
            "early_turn_cast_rate": round(early / casts, 3),
            "mid_turn_cast_rate": round(mid / casts, 3),
            "late_turn_cast_rate": round(late / casts, 3),
            "preferred_min_turn": max(1, int(round(avg_turn - 1.0))),
            "board_roles": role_rows,
        }

    return {
        "generated_at": None,
        "samples": {"games": games, "logs": total_logs},
        "cards": cards,
    }


def _board_role_hint(trace: dict) -> str:
    try:
        my_life = int(((trace.get("life") or {}).get("self", 20)) or 20)
        opp_life = int(((trace.get("life") or {}).get("opp", 20)) or 20)
    except Exception:
        my_life = 20
        opp_life = 20
    my_creatures = _count_creatures(trace.get("battlefield"))
    opp_creatures = _count_creatures(trace.get("opp_battlefield"))
    my_power = _sum_power(trace.get("battlefield"))
    opp_power = _sum_power(trace.get("opp_battlefield"))
    my_hand = len(trace.get("hand") or [])
    opp_hand = len(trace.get("opp_hand") or [])
    step = str(trace.get("step") or "").lower()
    if opp_life <= 7 or (my_power >= opp_life and opp_life <= 10):
        return "race"
    if my_life <= 8 and opp_power > my_power + 1:
        return "stabilize"
    if opp_power >= my_power + 3 and opp_creatures >= my_creatures and my_life <= 12:
        return "stabilize"
    if my_power >= opp_power + 2 and my_creatures >= opp_creatures and my_life > 8:
        return "convert"
    if my_hand - opp_hand >= 2 and opp_power <= my_power and my_life > 10:
        return "control"
    if my_life <= 8 and opp_power > my_power:
        return "defend"
    if "combat" in step and my_power > opp_power:
        return "convert"
    return "normal"


def _count_creatures(cards: Any) -> int:
    if not isinstance(cards, list):
        return 0
    total = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        types = card.get("types") or []
        if isinstance(types, list) and any(str(t).lower() == "creature" for t in types):
            total += 1
    return total


def _sum_power(cards: Any) -> int:
    if not isinstance(cards, list):
        return 0
    total = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        types = card.get("types") or []
        if not (isinstance(types, list) and any(str(t).lower() == "creature" for t in types)):
            continue
        try:
            total += max(0, int(card.get("power", 0) or 0))
        except Exception:
            continue
    return total
