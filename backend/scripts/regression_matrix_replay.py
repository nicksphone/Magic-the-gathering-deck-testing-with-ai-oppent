from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401
import argparse
import hashlib
import json
import tempfile
import time
from collections import Counter
from itertools import combinations
from pathlib import Path

from ai.agent import AIAgent
from ai.deck_analysis import guess_archetype
from analytics.replay_tools import classify_first_divergence, classify_log_line, classify_timeout_state, first_log_divergence, normalize_log_line
from card_data.hydration import hydrate_deck_cards
from decks.bootstrap import ensure_builtin_decks, ensure_expansion_top_decks
from decks.selection import select_representative_decks
from game_state.state import MatchFactory, pregame_actor
from game_state.series_policy import game_seed, next_play_draw_chooser
from persistence.db import engine, init_db
from persistence.repository import Repository
from rules_engine.engine import RulesEngine
from sqlmodel import Session


def _report_progress(output, summary, total, started, *, status='running', last_sample=None, error=None):
    elapsed = max(0.0, time.monotonic() - started)
    completed = summary['matches']
    record = {
        'event': 'matrix_progress', 'status': status,
        'completed_samples': completed, 'total_samples': total,
        'repeatability_runs_per_sample': 2,
        'elapsed_seconds': round(elapsed, 3),
        'estimated_remaining_seconds': (round(elapsed * max(0, total-completed) / completed, 1)
                                        if completed else 0.0 if total == 0 else None),
        'determinism_failures': summary['determinism_failures'],
        'anomaly_counts': summary.get('anomaly_counts', {}),
        'last_sample': last_sample, 'error': error,
        'resume_supported': False,
    }
    path = Path(str(output) + '.progress.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps(record), flush=True)
    return record


def _stable_seed(left_name: str, right_name: str, index: int) -> int:
    digest = hashlib.sha256(f"{left_name}::{right_name}::{index}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _append_replay_trace(path: Path | None, record: dict) -> None:
    if path is not None:
        # Close each record so a later failed repeat retains completed evidence.
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(record) + '\n')


def _pair_schedule(left: dict, right: dict, count: int, seat_balanced: bool = True):
    """Pair each seed with both seat orders; repeats are not new samples."""
    for index in range(count):
        seed = _stable_seed(left["name"], right["name"], index)
        yield seed, left, right, 1
        if seat_balanced:
            yield seed, right, left, 2


def _pair_outcomes(rows: list[dict]) -> dict:
    wins = {"deck_a": 0, "deck_b": 0}
    unresolved = Counter()
    seats = Counter()
    for row in rows:
        seats[str(row["deck_a_seat"])] += 1
        if row["termination_status"] != "resolved" or row["winner"] not in (1, 2):
            unresolved[row["termination_status"] if row["termination_status"] != "resolved" else "no_series_winner"] += 1
        else:
            wins["deck_a" if row["winner"] == row["deck_a_seat"] else "deck_b"] += 1
    completed = sum(wins.values())
    return {"scheduled_matches": len(rows), "completed_matches": completed,
            "wins": wins, "unresolved": dict(unresolved), "deck_a_seat_counts": dict(seats),
            "deck_a_win_rate_completed": wins["deck_a"] / completed if completed else None,
            "inference": "paired-seed regression sample; not independent balance or AI-strength evidence"}


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _corpus_hash(decks: list[dict]) -> str:
    return hashlib.sha256(json.dumps(decks, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def _load_deck_manifest(path: str, max_decks: int) -> tuple[list[dict], dict]:
    """Use already resolved inputs verbatim; never rehydrate from a mutable cache."""
    raw = Path(path).read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('Deck manifest requires schema_version 1')
    decks = manifest.get('decks')
    if not isinstance(decks, list) or len(decks) < 2:
        raise ValueError('Deck manifest requires at least two resolved decks')
    names = set()
    for deck in decks:
        if not isinstance(deck, dict) or not isinstance(deck.get('name'), str) or not deck['name'].strip():
            raise ValueError('Each manifest deck requires a nonempty name')
        if deck['name'] in names:
            raise ValueError('Manifest deck names must be unique')
        names.add(deck['name'])
        board = deck.get('mainboard')
        if not isinstance(board, list) or not board or len(board) > 250:
            raise ValueError('Each manifest deck requires a nonempty resolved mainboard of at most 250 entries')
        for card in board:
            if (not isinstance(card, dict) or type(card.get('quantity')) is not int
                    or not 1 <= card['quantity'] <= 250
                    or not isinstance(card.get('card_name'), str) or not card['card_name'].strip()
                    or not isinstance(card.get('oracle_text'), str)
                    or not isinstance(card.get('mana_cost'), str)
                    or not isinstance(card.get('type_line'), str) or not card['type_line'].strip()):
                raise ValueError('Manifest cards require bounded quantities, names, Oracle text, mana cost and resolved type lines')
        if sum(card['quantity'] for card in board) > 250:
            raise ValueError('Manifest deck exceeds the 250-card application resource limit')
    expected = manifest.get('corpus_sha256')
    if not isinstance(expected, str) or expected != _corpus_hash(decks):
        raise ValueError('Manifest corpus_sha256 does not match its resolved decks')
    selected = decks[:max_decks]
    return selected, {'input_source': 'resolved_manifest',
                      'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                      'source_corpus_sha256': expected, 'corpus_sha256': _corpus_hash(selected),
                      'source_provenance': manifest.get('provenance')}


def _write_deck_manifest(path: str, decks: list[dict], provenance: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'schema_version': 1, 'decks': decks,
                              'corpus_sha256': _corpus_hash(decks), 'provenance': provenance},
                             indent=2, allow_nan=False), encoding='utf-8')


_normalize_log_line = normalize_log_line
_select_regression_matrix_decks = select_representative_decks


def _drift_excerpt(drift: dict, drift_label: dict | None) -> dict:
    return {
        "index": drift.get("index", -1),
        "category": (drift_label or {}).get("category", "unknown"),
        "line_a": drift.get("a", ""),
        "line_b": drift.get("b", ""),
        "context_before": drift.get("context_before", []),
    }


def _match_termination_status(match: dict) -> str:
    if match.get("draw_cap_reached"):
        return "draw_cap"
    timed_out = [game for game in match.get("games", []) if game.get("timeout")]
    if timed_out:
        return classify_timeout_state([line for game in timed_out for line in game.get("log", [])], True)
    return classify_timeout_state(match.get("log", []), bool(match.get("timeout")))


def run_game(deck_a: list[dict], deck_b: list[dict], seed: int, difficulty: str, max_ticks: int, *, starting_player: int = 1) -> dict:
    if starting_player not in (1, 2):
        raise ValueError("Starting player must be 1 or 2")
    state = MatchFactory.from_decks(deck_a, deck_b, seed=seed)
    state.active_player = starting_player
    state.priority_player = starting_player
    state.mechanic_choice_players = {1, 2}
    engine_rules = RulesEngine()
    ai_a = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_a), opponent_archetype=guess_archetype(deck_b))
    ai_b = AIAgent(difficulty=difficulty, archetype=guess_archetype(deck_b), opponent_archetype=guess_archetype(deck_a))
    ticks = 0
    while state.winner is None and ticks < max_ticks:
        pid = pregame_actor(state) if state.pregame_pending else state.priority_player
        legal = engine_rules.legal_moves(state, pid)
        if not legal:
            action = {"type": "pass_priority"}
        else:
            agent = ai_a if pid == 1 else ai_b
            action = agent.choose_action(state, legal, pid).action
            legal_types = {m["type"] for m in legal}
            if action.get("type") not in legal_types:
                action = {"type": "pass_priority"}
        state.log.append(
            "AI TRACE "
            + json.dumps(
                {
                    "trace": True,
                    "pid": pid,
                    "turn": state.turn,
                    "step": str(state.step),
                    "active_player": state.active_player,
                    "priority_player": state.priority_player,
                    "hand": [state.cards[cid].name for cid in state.players[pid].hand if cid in state.cards],
                    "battlefield": [state.cards[cid].name for cid in state.players[pid].battlefield if cid in state.cards],
                    "legal_non_pass": any(move.get("type") != "pass_priority" for move in legal),
                    "legal_meaningful": any(
                        move.get("type") in {
                            "play_land", "cast_spell", "activate_ability", "activate_loyalty",
                            "cycle_card", "equip", "attack",
                        }
                        for move in legal
                    ),
                    "legal_action_types": sorted({str(move.get("type")) for move in legal}),
                    "action": action,
                },
                separators=(",", ":"),
            )
        )
        engine_rules.take_action(state, pid, action)
        ticks += 1

    normalized_log = [normalize_log_line(line) for line in state.log]
    log_hash = hashlib.sha256("\n".join(normalized_log).encode("utf-8")).hexdigest()
    return {
        "winner": state.winner,
        "turn": state.turn,
        "ticks": ticks,
        "log_hash": log_hash,
        "log": normalized_log,
        "timeout": state.winner is None,
        "starting_player": starting_player,
    }


def run_match(deck_a: list[dict], deck_b: list[dict], seed: int, difficulty: str, max_ticks: int, best_of: int) -> dict:
    """Run a seeded match while preserving each game's independent replay seed."""
    wins = {1: 0, 2: 0}
    games: list[dict] = []
    needed = best_of // 2 + 1
    # Only resolved draws add slots; a timeout is not a finished game to transition from.
    counted_games = 0
    chooser = 1
    for game_index in range(best_of * 2):
        current_seed = game_seed(seed, game_index + 1)
        game = run_game(deck_a, deck_b, current_seed, difficulty, max_ticks, starting_player=chooser)
        game["seed"] = current_seed
        game["play_draw_chooser"] = chooser
        game["starting_player"] = chooser
        games.append(game)
        if game["timeout"]:
            break
        if game["winner"] != 0:
            counted_games += 1
        if game["winner"] in wins:
            wins[game["winner"]] += 1
        if max(wins.values()) >= needed or counted_games >= best_of:
            break
        if game["winner"] in (0, 1, 2):
            chooser = next_play_draw_chooser(game["winner"], chooser)
    winner = 1 if wins[1] >= needed else (2 if wins[2] >= needed else None)
    draw_cap_reached = winner is None and len(games) == best_of * 2 and not any(game["timeout"] for game in games)
    match_hash = hashlib.sha256(
        "\n".join(game["log_hash"] for game in games).encode("utf-8")
    ).hexdigest()
    return {
        "winner": winner,
        "wins": {"deck_a": wins[1], "deck_b": wins[2]},
        "games_played": len(games),
        "timeout": any(game["timeout"] for game in games),
        "draw_cap_reached": draw_cap_reached,
        "turns": sum(int(game["turn"] or 0) for game in games),
        "log_hash": match_hash,
        "log": [line for game in games for line in game["log"]],
        "games": games,
    }
def main() -> None:
    p = argparse.ArgumentParser(description="Deterministic replay regression matrix")
    p.add_argument("--matches-per-pair", type=_positive_int, default=3, help="Seeds per pairing; each runs in both seat orders by default")
    p.add_argument("--single-seat", action="store_true", help="Legacy one-order smoke mode; not seat balanced")
    p.add_argument("--difficulty", choices=("casual", "strong", "master"), default="master")
    p.add_argument("--max-ticks", type=_positive_int, default=6000)
    p.add_argument("--output", default="training_runs/regression_matrix_replay.json")
    p.add_argument("--max-decks", type=_positive_int, default=12)
    p.add_argument("--best-of", type=int, choices=(1, 3, 5, 7, 9), default=1)
    p.add_argument('--progress', action='store_true', help='Emit JSON progress and atomically update <output>.progress.json; not a resumable snapshot')
    p.add_argument('--deck-manifest', help='Use hash-verified resolved decks without database bootstrap or hydration')
    p.add_argument('--write-deck-manifest', help='Export selected resolved inputs and provenance before running games')
    p.add_argument('--trace-output', help='New JSONL file retaining full decisions and results for both runs, including successful matches')
    args = p.parse_args()

    trace_path = Path(args.trace_output) if args.trace_output else None
    if trace_path is not None:
        protected_paths = [args.output, str(args.output) + '.progress.json',
                           args.deck_manifest, args.write_deck_manifest]
        if any(trace_path.resolve() == Path(value).resolve() for value in protected_paths if value):
            p.error('Trace output must differ from summary, progress and deck manifest paths')
        try:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open('x', encoding='utf-8'):
                pass
        except OSError as exc:
            p.error(f'Cannot create new trace output: {exc}')

    if args.deck_manifest:
        try:
            decks, input_provenance = _load_deck_manifest(args.deck_manifest, args.max_decks)
        except (ValueError, OSError) as exc:
            p.error(str(exc))
    else:
        init_db()
        with Session(engine) as session:
            repo = Repository(session)
            ensure_builtin_decks(repo)
            ensure_expansion_top_decks(repo)
            rows = repo.list_decks()
        selected_decks = select_representative_decks(rows, args.max_decks, guess_archetype_fn=guess_archetype)
        with Session(engine) as session:
            hydration_repo = Repository(session)
            decks = [{**deck, "mainboard": hydrate_deck_cards(hydration_repo, deck["mainboard"])}
                     for deck in selected_decks]
        input_provenance = {'input_source': 'repository_bootstrap', 'corpus_sha256': _corpus_hash(decks),
                            'cache_policy': 'resolved from this isolated repository database; export to pin subsequent runs'}
    if args.write_deck_manifest:
        _write_deck_manifest(args.write_deck_manifest, decks, input_provenance)

    _append_replay_trace(trace_path, {
        'event': 'replay_trace_manifest', 'schema_version': 1,
        'input_provenance': input_provenance, 'difficulty': args.difficulty,
        'max_ticks_per_game': args.max_ticks, 'best_of': args.best_of,
        'repeatability_runs_per_sample': 2,
        'scope': 'Offline diagnostic: actor hand/board and chosen actions; contains hidden game information',
    })

    summary = {
        "decks": len(decks),
        "pairs": 0,
        "games": 0,
        "matches": 0,
        "best_of": args.best_of,
        "input_provenance": input_provenance,
        "protocol": {"seeds_per_pair": args.matches_per_pair, "seat_balanced": not args.single_seat,
                     "difficulty": args.difficulty, "max_ticks_per_game": args.max_ticks,
                     "seed_policy": "sha256(deck_a::deck_b::index), game seed = series seed + game index",
                     "start_policy": "seat 1 chooses game one; prior loser chooses thereafter; draw retains chooser; AI chooses play; no sideboarding",
                     "timeout_policy": "unresolved at tick cap; excluded from completed-series win rate",
                     "repeatability_runs_per_sample": 2},
        "determinism_failures": 0,
        "drift_labels": {},
        "pair_results": [],
    }
    drift_labels = Counter()
    anomaly_counts = Counter()
    started = time.monotonic()
    total = len(decks) * (len(decks)-1) // 2 * args.matches_per_pair * (1 if args.single_seat else 2)
    if args.progress:
        _report_progress(args.output, summary, total, started)

    for left, right in combinations(decks, 2):
        summary["pairs"] += 1
        pair = {"deck_a": left["name"], "deck_b": right["name"], "games": []}
        for seed, seat_one, seat_two, deck_a_seat in _pair_schedule(left, right, args.matches_per_pair, not args.single_seat):
            try:
                trace_context = {'event': 'replay_trace_run', 'seed': seed,
                                 'deck_a_seat': deck_a_seat, 'seat_one_deck': seat_one['name'],
                                 'seat_two_deck': seat_two['name']}
                a = run_match(seat_one["mainboard"], seat_two["mainboard"], seed, args.difficulty, args.max_ticks, args.best_of)
                _append_replay_trace(trace_path, {**trace_context, 'repeatability_run': 1, 'result': a})
                b = run_match(seat_one["mainboard"], seat_two["mainboard"], seed, args.difficulty, args.max_ticks, args.best_of)
                _append_replay_trace(trace_path, {**trace_context, 'repeatability_run': 2, 'result': b})
            except Exception as exc:
                if args.progress:
                    summary['anomaly_counts'] = dict(anomaly_counts)
                    _report_progress(args.output, summary, total, started, status='failed',
                                     last_sample={'seed': seed, 'deck_a_seat': deck_a_seat,
                                                  'seat_one_deck': seat_one['name'], 'seat_two_deck': seat_two['name']},
                                     error=str(exc))
                raise
            deterministic_ok = a == b
            if not deterministic_ok:
                summary["determinism_failures"] += 1
                drift = first_log_divergence(a.get("log", []), b.get("log", []))
                drift_label = classify_first_divergence(drift)
                drift_labels[drift_label["category"]] += 1
                anomaly_counts[drift_label["action_a"]] += 1
            else:
                drift = None
                drift_label = None
            termination_status = _match_termination_status(a)
            if termination_status != "resolved":
                anomaly_counts[termination_status] += 1
            pair["games"].append({
                "seed": seed,
                "deck_a_seat": deck_a_seat,
                "seat_one_deck": seat_one["name"],
                "seat_two_deck": seat_two["name"],
                "winner": a["winner"],
                "winner_deck": (left["name"] if a["winner"] == deck_a_seat else right["name"]) if a["winner"] in (1, 2) else None,
                "turns": a["turns"],
                "games_played": a["games_played"],
                "wins": a["wins"] if deck_a_seat == 1 else {"deck_a": a["wins"]["deck_b"], "deck_b": a["wins"]["deck_a"]},
                "timeout": a["timeout"],
                "termination_status": termination_status,
                "deterministic": deterministic_ok,
                "drift": drift,
                "drift_label": drift_label,
                "diverging_result_fields": sorted(key for key in a.keys() | b.keys() if a.get(key) != b.get(key)),
                "drift_excerpt": _drift_excerpt(drift, drift_label) if drift else None,
                "game_seeds": [game["seed"] for game in a["games"]],
                "game_starting_players": [game["starting_player"] for game in a["games"]],
                "game_play_draw_choosers": [game["play_draw_chooser"] for game in a["games"]],
                "anomaly_trace": a["log"] if termination_status != "resolved" or not deterministic_ok else None,
                "repeat_trace": b["log"] if not deterministic_ok else None,
            })
            summary["matches"] += 1
            summary["games"] += a["games_played"]
            if args.progress:
                summary['anomaly_counts'] = dict(anomaly_counts)
                row = pair['games'][-1]
                _report_progress(args.output, summary, total, started,
                                 last_sample={key: row[key] for key in ('seed', 'deck_a_seat', 'seat_one_deck',
                                     'seat_two_deck', 'winner', 'termination_status', 'deterministic', 'drift_excerpt')})
        pair["outcomes"] = _pair_outcomes(pair["games"])
        summary["pair_results"].append(pair)

    summary["drift_labels"] = dict(drift_labels)
    summary["anomaly_counts"] = dict(anomaly_counts)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.progress:
        _report_progress(args.output, summary, total, started, status='completed')
    print(json.dumps({
        "output": str(out),
        "matches": summary["matches"],
        "games": summary["games"],
        "best_of": summary["best_of"],
        "determinism_failures": summary["determinism_failures"],
        "drift_labels": summary["drift_labels"],
    }))


if __name__ == "__main__":
    main()
