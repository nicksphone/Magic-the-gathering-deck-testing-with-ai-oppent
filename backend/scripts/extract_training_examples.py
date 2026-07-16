from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract labeled AI training examples from verbose H2H logs")
    p.add_argument("--games-jsonl", required=True, help="Path to games.jsonl from debug_head_to_head.py")
    p.add_argument("--out", default="", help="Optional output jsonl path")
    return p.parse_args()


def _parse_trace_line(line: str) -> dict | None:
    if not line.startswith("AI TRACE "):
        return None
    try:
        return json.loads(line[len("AI TRACE ") :])
    except Exception:
        return None


def _feature_row(game: dict, trace: dict) -> dict:
    action = trace.get("action") or {}
    life = trace.get("life") or {}
    return {
        "game": game.get("game"),
        "winner": game.get("winner"),
        "pid": trace.get("pid"),
        "turn": trace.get("turn"),
        "step": trace.get("step"),
        "active_player": trace.get("active_player"),
        "priority_player": trace.get("priority_player"),
        "hand": list(trace.get("hand") or []),
        "hand_size": len(trace.get("hand") or []),
        "opp_hand": list(trace.get("opp_hand") or []),
        "opp_hand_size": len(trace.get("opp_hand") or []),
        "battlefield": list(trace.get("battlefield") or []),
        "opp_battlefield": list(trace.get("opp_battlefield") or []),
        "graveyard_count": int(trace.get("graveyard_count") or 0),
        "opp_graveyard_count": int(trace.get("opp_graveyard_count") or 0),
        "library_count": int(trace.get("library_count") or 0),
        "opp_library_count": int(trace.get("opp_library_count") or 0),
        "life": {
            "self": life.get("self"),
            "opp": life.get("opp"),
        },
        "mana_pool": dict(trace.get("mana_pool") or {}),
        "legal_non_pass": bool(trace.get("legal_non_pass")),
        "legal_action_types": list(trace.get("legal_action_types") or []),
        "legal_has_land": bool(trace.get("legal_has_land")),
        "board_role_hint": _board_role_hint(trace),
        "board_snapshot": _board_snapshot(trace),
        "action_type": action.get("type"),
        "action_card_name": action.get("card_name"),
        "selected_face_index": action.get("selected_face_index"),
        "reasoning": trace.get("reasoning", ""),
        "reason_code": trace.get("reason_code", "unknown"),
    }


def _board_snapshot(trace: dict) -> dict:
    battlefield = list(trace.get("battlefield") or [])
    opp_battlefield = list(trace.get("opp_battlefield") or [])
    return {
        "battlefield_count": len(battlefield),
        "opp_battlefield_count": len(opp_battlefield),
        "hand_count": len(trace.get("hand") or []),
        "opp_hand_count": len(trace.get("opp_hand") or []),
        "battlefield_tapped": sum(1 for card in battlefield if card.get("tapped")),
        "opp_battlefield_tapped": sum(1 for card in opp_battlefield if card.get("tapped")),
        "graveyard_count": int(trace.get("graveyard_count") or 0),
        "opp_graveyard_count": int(trace.get("opp_graveyard_count") or 0),
        "library_count": int(trace.get("library_count") or 0),
        "opp_library_count": int(trace.get("opp_library_count") or 0),
        "battlefield_types": dict(_count_types(battlefield)),
        "opp_battlefield_types": dict(_count_types(opp_battlefield)),
    }


def _board_role_hint(trace: dict) -> str:
    life = trace.get("life") or {}
    self_life = int(life.get("self", 20) or 20)
    opp_life = int(life.get("opp", 20) or 20)
    battlefield = list(trace.get("battlefield") or [])
    opp_battlefield = list(trace.get("opp_battlefield") or [])
    self_creatures = sum(1 for card in battlefield if "Creature" in (card.get("types") or []))
    opp_creatures = sum(1 for card in opp_battlefield if "Creature" in (card.get("types") or []))
    hand_size = len(trace.get("hand") or [])
    step = str(trace.get("step") or "").lower()
    if opp_life <= 7 or (self_creatures > 0 and self_creatures * 2 >= opp_life):
        return "race"
    if self_creatures > opp_creatures and self_life > 10:
        return "convert"
    if self_life <= 8 and opp_creatures > self_creatures:
        return "stabilize"
    if hand_size >= 4 and opp_creatures >= self_creatures and self_life > 10:
        return "control"
    if step in {"beginning_of_combat", "declare_attackers", "declare_blockers", "combat_damage", "end_combat"} and self_creatures >= opp_creatures:
        return "race"
    return "normal"


def _count_types(cards: list[dict]) -> Counter:
    counts: Counter = Counter()
    for card in cards:
        for card_type in card.get("types") or []:
            counts[str(card_type)] += 1
    return counts


def extract_examples_from_games_jsonl(path: Path) -> list[dict]:
    examples: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            game = json.loads(line)
            for log_line in game.get("log", []):
                trace = _parse_trace_line(log_line)
                if trace is None:
                    continue
                examples.append(_feature_row(game, trace))
    return examples


def main() -> int:
    args = parse_args()
    path = Path(args.games_jsonl)
    if not path.exists():
        raise SystemExit(f"games.jsonl not found: {path}")

    examples = extract_examples_from_games_jsonl(path)
    out_path = Path(args.out) if args.out else path.with_name("training_examples.jsonl")
    with out_path.open("w", encoding="utf-8") as out:
        for row in examples:
            out.write(json.dumps(row, ensure_ascii=True) + "\n")
    print(json.dumps({"output": str(out_path), "examples": len(examples)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
