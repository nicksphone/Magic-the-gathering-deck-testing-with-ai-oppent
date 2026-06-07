from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from card_data.fallback_cards import fallback_card_payload
from game_state.state import MatchFactory
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def hand_snapshot(state, pid: int) -> list[str]:
    names = [state.cards[cid].name for cid in state.players[pid].hand]
    names.sort()
    return names


def battlefield_snapshot(state, pid: int) -> list[dict]:
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
    return sorted(out, key=lambda x: (x["name"], x["id"]))


def compact_action(action: dict) -> dict:
    out = {"type": action.get("type")}
    for k in ["card_id", "card_name", "ability_index", "selected_face_index"]:
        if k in action:
            out[k] = action[k]
    if isinstance(action.get("targets"), dict) and action.get("targets"):
        out["targets"] = action["targets"]
    if isinstance(action.get("cost_choice"), dict) and action.get("cost_choice"):
        out["cost_choice"] = action["cost_choice"]
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Head-to-head verbose MTG debug runner")
    p.add_argument("--deck-a", required=True, help="Saved deck name")
    p.add_argument("--deck-b", required=True, help="Saved deck name")
    p.add_argument("--matches", type=int, default=10)
    p.add_argument("--difficulty", default="master")
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--out-dir", default="diagnostics")
    return p.parse_args()


def load_named_deck(repo: Repository, name: str) -> list[dict]:
    rows = repo.list_decks()
    for r in rows:
        if r.name.strip().lower() == name.strip().lower():
            return json.loads(r.mainboard_json)
    names = sorted({r.name for r in rows})
    raise SystemExit(f"Deck not found: {name}. Available: {', '.join(names)}")


def hydrate_deck(repo: Repository, deck: list[dict]) -> list[dict]:
    names = [item["card_name"] for item in deck]
    cached = repo.get_cached_cards_by_names(names)
    out: list[dict] = []
    for item in deck:
        row = cached.get(item["card_name"].lower())
        card = dict(item)
        if row:
            card["oracle_text"] = row.oracle_text
            card["mana_cost"] = row.mana_cost
            card["type_line"] = row.type_line
            card["power"] = row.power
            card["toughness"] = row.toughness
            if getattr(row, "loyalty", None) is not None:
                card["loyalty"] = row.loyalty
            card["image_uri"] = row.image_uri
        else:
            fallback = fallback_card_payload(item["card_name"])
            if fallback:
                card.update({k: v for k, v in fallback.items() if v is not None})
        out.append(card)
    return out


def main() -> int:
    args = parse_args()
    init_db()

    out_base = Path(args.out_dir)
    if not out_base.is_absolute():
        out_base = Path(__file__).resolve().parent.parent / out_base
    run_dir = out_base / f"h2h-{args.deck_a.replace(' ', '_')}-vs-{args.deck_b.replace(' ', '_')}-{now_utc()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    games_path = run_dir / "games.jsonl"
    summary_path = run_dir / "summary.json"

    engine_rules = RulesEngine()
    wins = {1: 0, 2: 0, "timeout": 0}

    with Session(engine) as session:
        repo = Repository(session)
        deck_a = hydrate_deck(repo, load_named_deck(repo, args.deck_a))
        deck_b = hydrate_deck(repo, load_named_deck(repo, args.deck_b))
        a_arch = guess_archetype(deck_a)
        b_arch = guess_archetype(deck_b)

        with games_path.open("w", encoding="utf-8") as out:
            for game_idx in range(args.matches):
                state = MatchFactory.from_decks(deck_a, deck_b, player_a_name=args.deck_a, player_b_name=args.deck_b)
                a_agent = AIAgent(difficulty=args.difficulty, archetype=a_arch)
                b_agent = AIAgent(difficulty=args.difficulty, archetype=b_arch)
                ticks = 0

                while state.winner is None and ticks < args.max_ticks:
                    pid = 1 if state.pregame_pending and 1 not in state.kept_hands else (2 if state.pregame_pending else state.priority_player)
                    legal = engine_rules.legal_moves(state, pid)
                    if not legal:
                        action = {"type": "pass_priority"}
                        reasoning = "No legal action"
                    else:
                        agent = a_agent if pid == 1 else b_agent
                        decision = agent.choose_action(state, legal, pid)
                        action = decision.action
                        reasoning = decision.reasoning

                    trace = {
                        "trace": True,
                        "pid": pid,
                        "turn": state.turn,
                        "step": str(state.step),
                        "hand": hand_snapshot(state, pid),
                        "battlefield": battlefield_snapshot(state, pid),
                        "opp_battlefield": battlefield_snapshot(state, 1 if pid == 2 else 2),
                        "life": {
                            "self": state.players[pid].life,
                            "opp": state.players[1 if pid == 2 else 2].life,
                        },
                        "mana_pool": dict(state.players[pid].mana_pool),
                        "legal_non_pass": any(m.get("type") != "pass_priority" for m in legal),
                        "legal_has_land": any(m.get("type") == "play_land" for m in legal),
                        "action": compact_action(action),
                        "reasoning": reasoning,
                    }
                    state.log.append(f"AI TRACE {json.dumps(trace, separators=(',', ':'))}")

                    engine_rules.take_action(state, pid, action)
                    if state.step == state.step.COMBAT_DAMAGE:
                        engine_rules.take_action(state, state.active_player, {"type": "combat_damage"})
                    ticks += 1

                if state.winner in (1, 2):
                    wins[state.winner] += 1
                else:
                    wins["timeout"] += 1

                record = {
                    "game": game_idx + 1,
                    "winner": state.winner,
                    "turns": state.turn,
                    "ticks": ticks,
                    "life": {"1": state.players[1].life, "2": state.players[2].life},
                    "library": {"1": len(state.players[1].library), "2": len(state.players[2].library)},
                    "log": state.log,
                }
                out.write(json.dumps(record, ensure_ascii=True) + "\n")

    summary = {
        "deck_a": args.deck_a,
        "deck_b": args.deck_b,
        "matches": args.matches,
        "difficulty": args.difficulty,
        "wins": {"deck_a": wins[1], "deck_b": wins[2], "timeout": wins["timeout"]},
        "output": {
            "run_dir": str(run_dir),
            "games_jsonl": str(games_path),
            "summary_json": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
