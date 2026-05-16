from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize card play logic from H2H games.jsonl traces")
    p.add_argument("--games-jsonl", required=True, help="Path to games.jsonl from debug_head_to_head.py")
    p.add_argument("--out", default="", help="Optional output json path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.games_jsonl)
    if not path.exists():
        raise SystemExit(f"games.jsonl not found: {path}")

    total_games = 0
    timeouts = 0
    winners = Counter()
    action_types = Counter()
    cast_by_card = Counter()
    play_land_count = Counter()
    pass_with_options = Counter()
    missed_land_windows = Counter()
    per_player_actions = defaultdict(Counter)

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total_games += 1
            row = json.loads(line)
            winner = row.get("winner")
            winners[str(winner)] += 1
            if winner is None:
                timeouts += 1

            for log_line in row.get("log", []):
                if not log_line.startswith("AI TRACE "):
                    continue
                payload = json.loads(log_line[len("AI TRACE ") :])
                pid = str(payload.get("pid"))
                act = (payload.get("action") or {})
                atype = str(act.get("type", "unknown"))
                action_types[atype] += 1
                per_player_actions[pid][atype] += 1

                if atype == "cast_spell":
                    name = str(act.get("card_name") or "unknown_card")
                    cast_by_card[name] += 1
                elif atype == "play_land":
                    play_land_count[pid] += 1
                elif atype == "pass_priority" and bool(payload.get("legal_non_pass")):
                    pass_with_options[pid] += 1

                if bool(payload.get("legal_has_land")) and atype != "play_land":
                    missed_land_windows[pid] += 1

    summary = {
        "games": total_games,
        "timeouts": timeouts,
        "winners": dict(winners),
        "actions": dict(action_types),
        "per_player_actions": {k: dict(v) for k, v in per_player_actions.items()},
        "pass_with_options": dict(pass_with_options),
        "missed_land_windows": dict(missed_land_windows),
        "top_cast_cards": [{"card": c, "count": n} for c, n in cast_by_card.most_common(50)],
        "land_plays": dict(play_land_count),
    }

    out_path = Path(args.out) if args.out else path.with_name("card_play_analytics.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out_path), "games": total_games, "timeouts": timeouts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

