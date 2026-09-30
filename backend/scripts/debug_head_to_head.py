from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.decision_quality import build_trace_payload
from analytics.decision_taxonomy import decision_reason_code, has_actionable_move, has_meaningful_move, is_actionable_move
from card_data.hydration import hydrate_deck_cards as hydrate_deck
from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from game_state.state import MatchFactory, pregame_actor
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def build_debug_trace_payload(state, pid: int, legal: list[dict], action: dict, reasoning: str) -> dict:
    opponent = 1 if pid == 2 else 2
    trace = build_trace_payload(state, pid, legal, action, reasoning)
    trace.update({
        "graveyard_count": len(state.players[pid].graveyard),
        "opp_graveyard_count": len(state.players[opponent].graveyard),
        "library_count": len(state.players[pid].library),
        "opp_library_count": len(state.players[opponent].library),
        "legal_non_pass_count": sum(1 for move in legal if is_actionable_move(move)),
        "legal_action_types": sorted({str(move.get("type")) for move in legal if is_actionable_move(move)}),
        "reason_code": decision_reason_code(
            action, reasoning,
            legal_non_pass=has_actionable_move(legal),
            meaningful_non_pass=has_meaningful_move(legal),
            active_player=state.active_player,
            player_id=pid,
            step=state.step,
            stack_empty=not bool(state.stack),
        ),
    })
    return trace


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Head-to-head verbose MTG debug runner")
    p.add_argument("--deck-a", required=True, help="Saved deck name")
    p.add_argument("--deck-b", required=True, help="Saved deck name")
    p.add_argument("--matches", type=int, default=10)
    p.add_argument("--difficulty", default="master")
    p.add_argument("--max-ticks", type=int, default=6000)
    p.add_argument("--seed", type=int, default=None, help="Reproducible root seed; game N uses seed + N - 1")
    p.add_argument("--out-dir", default="diagnostics")
    return p.parse_args()


def load_named_deck(repo: Repository, name: str) -> list[dict]:
    rows = repo.list_decks()
    for r in rows:
        if r.name.strip().lower() == name.strip().lower():
            return json.loads(r.mainboard_json)
    names = sorted({r.name for r in rows})
    raise SystemExit(f"Deck not found: {name}. Available: {', '.join(names)}")


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
        ensure_builtin_decks(repo)
        ensure_expansion_top_decks(repo)
        deck_a = hydrate_deck(repo, load_named_deck(repo, args.deck_a))
        deck_b = hydrate_deck(repo, load_named_deck(repo, args.deck_b))
        a_arch = guess_archetype(deck_a)
        b_arch = guess_archetype(deck_b)

        with games_path.open("w", encoding="utf-8") as out:
            for game_idx in range(args.matches):
                game_seed = args.seed + game_idx if args.seed is not None else None
                state = MatchFactory.from_decks(deck_a, deck_b, player_a_name=args.deck_a, player_b_name=args.deck_b, seed=game_seed)
                state.mechanic_choice_players = {1, 2}
                a_agent = AIAgent(difficulty=args.difficulty, archetype=a_arch, opponent_archetype=b_arch)
                b_agent = AIAgent(difficulty=args.difficulty, archetype=b_arch, opponent_archetype=a_arch)
                ticks = 0

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

                    trace = build_debug_trace_payload(state, pid, legal, action, reasoning)
                    state.log.append(f"AI TRACE {json.dumps(trace, separators=(',', ':'))}")

                    engine_rules.take_action(state, pid, action)
                    ticks += 1

                if state.winner in (1, 2):
                    wins[state.winner] += 1
                else:
                    wins["timeout"] += 1

                record = {
                    "game": game_idx + 1,
                    "seed": game_seed,
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
        "root_seed": args.seed,
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
