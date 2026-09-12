from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from analytics.decision_quality import DECISION_QUALITY_METRICS, summarize_trace_rows
from analytics.service import AnalyticsService


ANOMALY_KEYS = (
    "timeouts",
    "long_game_timeouts",
    "stall_streaks",
    "invalid_targets",
    "cost_failures",
    "additional_cost_failures",
)



def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc.msg}") from exc


def _deck_archetypes(gate: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    id_candidates: dict[str, set[str]] = defaultdict(set)
    name_candidates: dict[str, set[str]] = defaultdict(set)

    def add(*, deck_id: Any = None, name: Any = None, archetype: Any = None) -> None:
        if not archetype:
            return
        if deck_id is not None:
            id_candidates[str(deck_id)].add(str(archetype))
        if name:
            name_candidates[str(name)].add(str(archetype))

    for deck, archetype in (gate.get("deck_archetypes") or {}).items():
        add(name=deck, archetype=archetype)
    for pair in gate.get("pair_summaries") or []:
        for side in ("a", "b"):
            add(
                deck_id=pair.get(f"deck_{side}_id"),
                name=pair.get(f"deck_{side}"),
                archetype=pair.get(f"deck_{side}_archetype"),
            )
    for deck in gate.get("decks") or []:
        add(deck_id=deck.get("id"), name=deck.get("name"), archetype=deck.get("archetype"))

    unique_ids = {key: next(iter(values)) for key, values in id_candidates.items() if len(values) == 1}
    unique_names = {key: next(iter(values)) for key, values in name_candidates.items() if len(values) == 1}
    return unique_ids, unique_names


def _archetypes_for_row(
    row: dict[str, Any],
    mapping: tuple[dict[str, str], dict[str, str]],
) -> tuple[tuple[str, str] | None, bool]:
    id_mapping, name_mapping = mapping
    resolved: list[str] = []
    for side in ("a", "b"):
        explicit = row.get(f"deck_{side}_archetype")
        deck_id = row.get(f"deck_{side}_id")
        id_archetype = id_mapping.get(str(deck_id)) if deck_id is not None else None
        if explicit and id_archetype and str(explicit) != id_archetype:
            return None, True
        archetype = explicit or id_archetype or name_mapping.get(str(row.get(f"deck_{side}", "")))
        if not archetype:
            return None, False
        resolved.append(str(archetype))
    return (resolved[0], resolved[1]), False


def _summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return summarize_trace_rows(rows)


def _aggregate_game_rows(
    rows: Iterable[dict[str, Any]],
    deck_archetypes: tuple[dict[str, str], dict[str, str]],
) -> dict[str, Any]:
    matchups: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    decision_quality: dict[str, Counter[str]] = defaultdict(Counter)
    decision_quality_available: dict[str, dict[str, bool]] = {}
    rows_without_archetypes = 0
    rows_with_conflicting_archetypes = 0

    for row in rows:
        archetypes, conflicting = _archetypes_for_row(row, deck_archetypes)
        if archetypes is None:
            if conflicting:
                rows_with_conflicting_archetypes += 1
            else:
                rows_without_archetypes += 1
            continue

        canonical = (min(archetypes), max(archetypes))
        swapped = archetypes != canonical
        matchup = matchups[canonical]
        matchup["games"] += 1
        if "winner" not in row:
            matchup["missing_winner"] += 1
        elif row["winner"] is None:
            matchup["timeouts"] += 1
        elif row["winner"] == (2 if swapped else 1):
            matchup["wins_a"] += 1
        elif row["winner"] == (1 if swapped else 2):
            matchup["wins_b"] += 1

        analytics = _summarize_rows((row,))
        for pid, archetype in (("1", archetypes[0]), ("2", archetypes[1])):
            availability = decision_quality_available.setdefault(
                archetype,
                {metric: True for metric in DECISION_QUALITY_METRICS},
            )
            pid_availability = analytics["availability"][pid]
            for metric in DECISION_QUALITY_METRICS:
                availability[metric] = availability[metric] and pid_availability.get(metric) is True
            decision_quality[archetype].update(analytics["counts"][pid])

    known_archetypes = set(deck_archetypes[0].values()) | set(deck_archetypes[1].values())
    for archetype in known_archetypes:
        decision_quality_available.setdefault(
            archetype,
            {metric: False for metric in DECISION_QUALITY_METRICS},
        )

    return {
        "matchups": matchups,
        "decision_quality": decision_quality,
        "decision_quality_available": decision_quality_available,
        "rows_without_archetypes": rows_without_archetypes,
        "rows_with_conflicting_archetypes": rows_with_conflicting_archetypes,
    }


def build_report(
    *,
    oracle_path: Path,
    gate_path: Path,
    log_priors_path: Path,
    games_jsonl_path: Path,
) -> dict[str, Any]:
    oracle = _load_json(oracle_path)
    gate = _load_json(gate_path)
    log_priors = _load_json(log_priors_path)
    deck_archetypes = _deck_archetypes(gate)
    unavailable = {}
    aggregated = _aggregate_game_rows(_iter_jsonl(games_jsonl_path), deck_archetypes)
    rows_without_archetypes = aggregated["rows_without_archetypes"]
    rows_with_conflicting_archetypes = aggregated["rows_with_conflicting_archetypes"]
    if rows_without_archetypes:
        unavailable["unmapped_game_archetypes"] = (
            f"{rows_without_archetypes} game row(s) lack unambiguous deck-to-archetype metadata"
        )
    if rows_with_conflicting_archetypes:
        unavailable["conflicting_game_archetypes"] = (
            f"{rows_with_conflicting_archetypes} game row(s) contain archetype metadata "
            "conflicting with stable deck IDs"
        )

    matchups: dict[str, dict[str, Any]] = {}
    for (archetype_a, archetype_b), counts in sorted(aggregated["matchups"].items()):
        wins_a = int(counts["wins_a"])
        wins_b = int(counts["wins_b"])
        resolved = wins_a + wins_b
        key = f"{archetype_a} vs {archetype_b}"
        outcomes_available = not counts["missing_winner"]
        if not outcomes_available:
            for metric in (
                "resolved_games",
                "timeouts",
                "wins_a",
                "wins_b",
                "win_rate_a",
                "win_rate_b",
                "wilson_ci_a",
                "wilson_ci_b",
            ):
                unavailable[f"win_rates_by_archetype_pair.{key}.{metric}"] = "winner absent from game row"
        elif resolved == 0:
            for metric in ("win_rate_a", "win_rate_b", "wilson_ci_a", "wilson_ci_b"):
                unavailable[f"win_rates_by_archetype_pair.{key}.{metric}"] = "no resolved games"
        matchups[key] = {
            "archetype_a": archetype_a,
            "archetype_b": archetype_b,
            "games": int(counts["games"]),
            "resolved_games": resolved if outcomes_available else None,
            "timeouts": int(counts["timeouts"]) if outcomes_available else None,
            "wins_a": wins_a if outcomes_available else None,
            "wins_b": wins_b if outcomes_available else None,
            "win_rate_a": round((wins_a / resolved) * 100, 2) if outcomes_available and resolved else None,
            "win_rate_b": round((wins_b / resolved) * 100, 2) if outcomes_available and resolved else None,
            "wilson_ci_a": AnalyticsService._wilson_interval(wins_a, resolved) if outcomes_available and resolved else None,
            "wilson_ci_b": AnalyticsService._wilson_interval(wins_b, resolved) if outcomes_available and resolved else None,
        }

    decision_quality = aggregated["decision_quality"]
    decision_quality_available = aggregated["decision_quality_available"]

    cards_available = "cards" in oracle and isinstance(oracle["cards"], list)
    cards = oracle["cards"] if cards_available else []
    cache_status_available = cards_available and all(isinstance(card.get("cached"), bool) for card in cards)
    cached_cards = sum(1 for card in cards if card.get("cached") is True) if cache_status_available else None
    total_cards = len(cards) if cards_available else None
    totals = gate.get("totals") or {}
    anomalies: dict[str, int | None] = {}
    for key in ANOMALY_KEYS:
        if key in totals and totals[key] is not None:
            anomalies[key] = int(totals[key])
        else:
            anomalies[key] = None
            unavailable[f"anomalies.{key}"] = "field absent from gate totals"

    decision_quality_report: dict[str, dict[str, int | None]] = {}
    for archetype in sorted(decision_quality_available):
        counts = decision_quality[archetype]
        decision_quality_report[archetype] = {}
        for metric in DECISION_QUALITY_METRICS:
            available = decision_quality_available[archetype][metric]
            decision_quality_report[archetype][metric] = int(counts[metric]) if available else None
            if not available:
                unavailable[f"decision_quality_by_archetype.{archetype}.{metric}"] = (
                    "complete relevant decision trace evidence absent"
                )

    oracle_status_counts: dict[str, dict[str, Any] | None] = {}
    for output_key, source_key in (("unique", "status_unique"), ("weighted", "status_weighted")):
        if source_key in oracle and oracle[source_key] is not None:
            oracle_status_counts[output_key] = oracle[source_key]
        else:
            oracle_status_counts[output_key] = None
            unavailable[f"oracle_status_counts.{output_key}"] = f"{source_key} absent or null in oracle artifact"

    if not cards_available:
        for metric in ("cached_cards", "total_cards", "missing_cards", "completeness_percent"):
            unavailable[f"card_cache_completeness.{metric}"] = "cards absent from oracle artifact"
    elif not cache_status_available:
        for metric in ("cached_cards", "missing_cards", "completeness_percent"):
            unavailable[f"card_cache_completeness.{metric}"] = "cached status absent or null for one or more cards"
    elif total_cards == 0:
        unavailable["card_cache_completeness.completeness_percent"] = "no cards in measured corpus"

    log_prior_cards = len(log_priors["cards"]) if isinstance(log_priors.get("cards"), dict) else None
    log_prior_samples = log_priors["samples"] if "samples" in log_priors else None
    if log_prior_cards is None:
        unavailable["log_priors.cards"] = "cards absent from log priors artifact"
    if log_prior_samples is None:
        unavailable["log_priors.samples"] = "samples absent from log priors artifact"
    if cache_status_available:
        assert cached_cards is not None and total_cards is not None
        missing_cards = total_cards - cached_cards
        completeness_percent = round((cached_cards / total_cards) * 100, 2) if total_cards else None
    else:
        missing_cards = None
        completeness_percent = None
    return {
        "win_rates_by_archetype_pair": matchups,
        "anomalies": anomalies,
        "decision_quality_by_archetype": decision_quality_report,
        "oracle_status_counts": oracle_status_counts,
        "card_cache_completeness": {
            "cached_cards": cached_cards,
            "total_cards": total_cards,
            "missing_cards": missing_cards,
            "completeness_percent": completeness_percent,
        },
        "log_priors": {
            "cards": log_prior_cards,
            "samples": log_prior_samples,
        },
        "unavailable_metrics": unavailable,
    }


def render_report(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine baseline gate artifacts into one deterministic report")
    parser.add_argument("--oracle", required=True, help="Path to oracle_corpus_report JSON")
    parser.add_argument("--gate", required=True, help="Path to CI gate/overnight summary JSON")
    parser.add_argument("--games-jsonl", required=True, help="Path to the gate run's full card-play game traces")
    parser.add_argument("--log-priors", default="ai/data/log_priors.json", help="Path to AI log priors JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        oracle_path=Path(args.oracle),
        gate_path=Path(args.gate),
        log_priors_path=Path(args.log_priors),
        games_jsonl_path=Path(args.games_jsonl),
    )
    print(render_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
