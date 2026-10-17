from __future__ import annotations

try:  # pragma: no cover - import path bootstrap for CLI execution
    from . import _bootstrap  # type: ignore[attr-defined]  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution
    import _bootstrap  # noqa: F401

import argparse
import hashlib
import json
import os
import stat
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from itertools import combinations
from fractions import Fraction
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


def package_measurement(production, *, directory, oracle_path, log_priors_path, budget, artifact_guard):
    """Package current closed fixed-game files; never run, retry or repair a game."""
    from analytics.resource_budget import checked_json
    from scripts.matchup_round_robin import canonical_bytes, digest
    if (not callable(artifact_guard) or type(production) is not dict
            or production.get('budget_identity') != id(budget)
            or production.get('budget_deadline') != budget.deadline):
        raise ValueError('Actual same-budget producer and external artifact guard required')
    budget.check_deadline()
    directory = Path(directory)
    limits = budget.limits
    def read(path, maximum):
        with Path(path).open('rb') as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            from analytics.resource_budget import SimulationResourceLimit
            raise SimulationResourceLimit('result_json')
        return raw
    producer = read(directory / 'producer.json', limits['result_json_bytes'])
    if canonical_bytes(json.loads(producer)) != canonical_bytes(production):
        raise ValueError('Producer file differs from the actual delivery')
    input_hashes = {}
    for key, path in (('oracle', oracle_path), ('priors', log_priors_path)):
        raw = read(path, limits['request_json_bytes'])
        actual = hashlib.sha256(raw).hexdigest()
        if actual != production['inputs'][key]['sha256']:
            raise ValueError('Actual measured input changed before packaging')
        input_hashes[str(path)] = actual
    observed = {}
    for name, receipt in production['output_files'].items():
        raw = read(directory / name, limits['result_json_bytes'] + 1)
        if len(raw) != receipt['bytes'] or hashlib.sha256(raw).hexdigest() != receipt['sha256']:
            raise ValueError('Actual closed writer output differs')
        observed[name] = raw
    sample_fields = ('deck_a', 'deck_b', 'seed_token', 'deck_a_seat', 'evidence_complete', 'status', 'winner')

    def result_outcome(result):
        if (type(result) is not dict or 'winner' not in result
                or result['winner'] is not None and (type(result['winner']) is not int or result['winner'] not in (0, 1, 2))
                or result.get('stop_reason') is not None and type(result['stop_reason']) is not str):
            raise ValueError('Typed genuine result outcome required')
        winner = result['winner']
        return dict(winner=winner, status=result.get('stop_reason') or (
            'timeout' if winner is None else 'draw' if winner == 0 else 'resolved'))

    def validate_game_records():
        budget.check_deadline()
        if (directory.resolve(strict=True) != directory.absolute()
                or any(path.is_symlink() for path in (directory, *directory.parents))):
            raise ValueError('Ordinary private record directory required')
        records = production.get('game_records')
        if (type(records) is not list or len(records) > len(production['games'])
                or production['complete'] and len(records) != len(production['selected'])):
            raise ValueError('Actual full writer receipts required')
        if type(production['games']) is not list or len(production['games']) > len(production['selected']):
            raise ValueError('Only actually attempted scheduled samples may be published')
        for index, sample in enumerate(production['games']):
            coordinate = production['selected'][index]
            if (type(sample) is not dict or not set(sample_fields) <= set(sample)
                    or type(sample['evidence_complete']) is not bool):
                raise ValueError('Typed complete published sample fields required')
            expected = {key: coordinate[key] for key in sample_fields[:4]}
            if 'result' in sample:
                actual = sample['result']
                expected.update(result_outcome(actual), evidence_complete=actual.get('evidence') is not None)
                if not expected['evidence_complete'] and expected['status'] in ('resolved', 'timeout', 'draw'):
                    raise ValueError('Unavailable evidence cannot certify a completed outcome')
            else:
                if (sample['status'] not in ('resource_limit', 'execution_error')
                        or type(sample.get('error_type')) is not str or not sample['error_type']):
                    raise ValueError('Receiptless exception remains explicitly unavailable')
                expected.update(winner=None, status=sample['status'], evidence_complete=False)
            if (canonical_bytes({key: sample[key] for key in sample_fields}) != canonical_bytes(expected)
                    or sample['evidence_complete'] and index >= len(records)):
                raise ValueError('Published sample differs from its actual coordinate/outcome/evidence')
        names, identities, row_index = set(), set(), 0
        maximum = min(limits['result_json_bytes'], limits['snapshot_json_bytes'])
        for index, binding in enumerate(records):
            budget.check_deadline()
            if (type(binding) is not dict or set(binding) != {'ordinal', 'coordinate', 'receipt', 'result'}
                    or type(binding['ordinal']) is not int or binding['ordinal'] != index + 1
                    or index >= len(production['selected'])
                    or canonical_bytes(binding['coordinate']) != canonical_bytes(production['selected'][index])):
                raise ValueError('Writer ordinal/coordinate differs from the actual sample')
            sample, receipt = production['games'][index], binding['receipt']
            coordinate = production['selected'][index]
            if (type(sample) is not dict or not set(coordinate) <= set(sample)
                    or canonical_bytes({key: sample[key] for key in coordinate}) != canonical_bytes(coordinate)
                    or type(receipt) is not dict or set(receipt) != {
                        'reference', 'complete', 'bytes', 'raw_sha256', 'record_sha256'}
                    or receipt['complete'] is not True or type(receipt['bytes']) is not int
                    or type(receipt['reference']) is not str
                    or receipt['reference'] != f'game-{index + 1:02d}.json'):
                raise ValueError('Genuine complete writer receipt/sample join required')
            path = directory / receipt['reference']
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != os.getuid():
                    raise ValueError('Distinct ordinary raw record required')
                if before.st_size > maximum:
                    from analytics.resource_budget import SimulationResourceLimit
                    raise SimulationResourceLimit('result_json')
                with os.fdopen(fd, 'rb', closefd=False) as handle:
                    raw = handle.read(maximum + 1)
                after = os.fstat(fd)
                current = path.lstat()
                identity = before.st_dev, before.st_ino
                if (len(raw) != before.st_size or len(raw) > maximum
                        or (after.st_dev, after.st_ino, after.st_size) != (*identity, len(raw))
                        or (current.st_dev, current.st_ino) != identity or stat.S_ISLNK(current.st_mode)
                        or identity in identities):
                    raise ValueError('Raw record identity/content changed during read')
                identities.add(identity)
            finally:
                os.close(fd)
            envelope = json.loads(raw)
            if (type(envelope) is not dict or set(envelope) != {'schema_version', 'result', 'raw_log', 'raw_sha256'}
                    or type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
                    or type(envelope['result']) is not dict or type(envelope['raw_log']) is not list
                    or any(type(line) is not str for line in envelope['raw_log'])):
                raise ValueError('Complete actual writer envelope required')
            raw_log = checked_json(envelope['raw_log'], maximum, 'result_json', separators=(',', ':')).encode('ascii')
            raw_sha = hashlib.sha256(raw_log).hexdigest()
            if (canonical_bytes(envelope) != raw or hashlib.sha256(raw).hexdigest() != receipt['record_sha256']
                    or envelope['raw_sha256'] != raw_sha or receipt['raw_sha256'] != raw_sha
                    or receipt['bytes'] != len(raw_log)
                    or canonical_bytes(envelope['result']) != canonical_bytes(binding['result'])):
                raise ValueError('Actual raw/result bytes differ from the retained writer receipt')
            evidence = {key: receipt[key] for key in ('reference', 'complete', 'bytes', 'raw_sha256')}
            if sample['evidence_complete']:
                expected_result = {key: value for key, value in binding['result'].items() if key != 'log'}
                expected_result['evidence'] = evidence
                if (canonical_bytes(sample.get('result')) != canonical_bytes(expected_result)
                        or canonical_bytes({key: sample[key] for key in ('winner', 'status')})
                           != canonical_bytes(result_outcome(envelope['result']))):
                    raise ValueError('Actual result differs from its completed sample')
                if sample['status'] in ('resolved', 'timeout'):
                    if row_index >= len(production['rows']):
                        raise ValueError('Raw record lacks its report row')
                    row = production['rows'][row_index]
                    if (canonical_bytes(json.loads(observed[f'row-{row_index:02d}.jsonl'])) != canonical_bytes(row)
                            or canonical_bytes(row.get('log')) != canonical_bytes(envelope['raw_log'])
                            or row.get('evidence') != evidence or row.get('winner') != binding['result']['winner']
                            or row.get('turns') != binding['result']['turn'] or row.get('ticks') != binding['result']['ticks']
                            or any(row.get(key) != value for key, value in {
                                'deck_a': coordinate['seat_one'], 'deck_b': coordinate['seat_two'],
                                'pair_a': coordinate['deck_a'], 'pair_b': coordinate['deck_b'],
                                'seed_token': coordinate['seed_token'], 'root_seed': coordinate['root_seed'],
                                'deck_a_seat': coordinate['deck_a_seat'], 'starting_player': 1}.items())):
                        raise ValueError('Raw record/report row join differs')
                    row_index += 1
            names.add(receipt['reference'])
        if (row_index != len(production['rows'])
                or names != {path.name for path in directory.iterdir() if path.name.startswith('game-')}):
            raise ValueError('Unjoined or missing actual raw record/report row')

    rows = [observed[f'row-{index:02d}.jsonl'] for index in range(len(production['rows']))]
    games_path = directory / 'all-games.jsonl'
    artifact_guard(games_path, sum(map(len, rows)))
    with games_path.open('xb') as handle:
        for row in rows:
            handle.write(row)
        handle.flush(); os.fsync(handle.fileno())
    with games_path.open('rb') as handle:
        if any(handle.read(len(row)) != row for row in rows) or handle.read(1):
            raise OSError('JSONL copy readback differs')
    report = build_report(oracle_path=Path(oracle_path), gate_path=directory/'comparison-gate.json',
                          log_priors_path=Path(log_priors_path), games_jsonl_path=games_path)
    config, source, partition = (production[k] for k in ('configuration', 'source', 'partition'))
    measurement = dict(schema_version=1, source_base_commit=source['source_base_commit'],
        backend_before_sha256=source['before_sha256'], backend_after_sha256=source['after_sha256'],
        corpus_sha256=config['corpus_sha256'], export_sha256=config['export_sha256'],
        metric_definitions_sha256=partition['metric_definitions_sha256'],
        report_sha256=digest(report), engine_rules_sha256=partition['engine_rules_sha256'],
        controlled_policy_sha256=partition['controlled_policy_sha256'],
        experimental_features=partition['experimental_features'],
        policy_configuration_sha256=digest({k: partition[k] for k in
            ('controlled_policy_sha256', 'experimental_features')}),
        difficulty=config['difficulty'], max_ticks=config['max_ticks'], limits=config['limits'],
        sideboard_mode='fixed_no_swaps', schedule_kind='fixed_games', roster=config['roster'],
        seeds=[production['selected'][0]['seed_token']], seats=[1, 2], complete=production['complete'],
        status='completed_schedule' if production['complete'] else 'stopped', planned_games=2,
        attempted_games=production['attempted_games'], not_run_games=production['not_run_games'],
        samples=[{key: game[key] for key in sample_fields} for game in production['games']])
    package = dict(report=report, measurement=measurement)
    validate_game_records()  # After report construction, immediately before eligibility.
    try:
        _comparison_admit(package)
        eligible = True
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        eligible = False  # Missing observations remain diagnostic, never invented zeroes.
    budget.checked_result(package)
    raw = checked_json(package, limits['result_json_bytes'], 'result_json', separators=(',', ':')).encode('ascii')
    output = directory / 'package.json'
    artifact_guard(output, len(raw))
    validate_game_records()
    with output.open('xb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    if read(output, limits['result_json_bytes']) != raw:
        raise OSError('Comparison package readback differs')
    for path, expected in input_hashes.items():
        if hashlib.sha256(read(path, limits['request_json_bytes'])).hexdigest() != expected:
            raise ValueError('Measured input changed during packaging')
    budget.check_deadline()
    validate_game_records()  # The external package charge/write cannot hide a later mutation.
    return dict(eligible=eligible, package=package, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _comparison_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode('utf-8')).hexdigest()


def _comparison_require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _comparison_count(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 2**63 - 1


def _comparison_hex(value: Any, length: int = 64) -> bool:
    return type(value) is str and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _comparison_admit(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate an explicit fixed-game receipt, not the authenticity of gameplay."""
    from analytics.resource_budget import RESOURCE_LIMITS

    require = _comparison_require
    count = _comparison_count
    require(type(package) is dict and set(package) == {'report', 'measurement'}, 'package_shape')
    report, measurement = package['report'], package['measurement']
    keys = {'schema_version', 'source_base_commit', 'backend_before_sha256', 'backend_after_sha256',
            'corpus_sha256', 'export_sha256', 'metric_definitions_sha256', 'report_sha256',
            'engine_rules_sha256', 'controlled_policy_sha256', 'experimental_features',
            'policy_configuration_sha256',
            'difficulty', 'max_ticks', 'limits', 'sideboard_mode', 'schedule_kind', 'roster',
            'seeds', 'seats', 'complete', 'status', 'planned_games', 'attempted_games',
            'not_run_games', 'samples'}
    require(type(measurement) is dict and set(measurement) == keys, 'measurement_shape')
    require(type(measurement['schema_version']) is int and measurement['schema_version'] == 1,
            'measurement_version')
    require(_comparison_hex(measurement['source_base_commit'], 40)
            and all(_comparison_hex(measurement[key]) for key in keys if key.endswith('_sha256'))
            and measurement['backend_before_sha256'] == measurement['backend_after_sha256'],
            'source_or_digest_binding')
    features = measurement['experimental_features']
    require(type(features) is dict and features and set(features) <= {
            'task2.3', 'task3.2', 'task4.1', 'task4.2', 'task4.3', 'task4.5'}
            and all(_comparison_hex(value) for value in features.values())
            and measurement['policy_configuration_sha256'] == _comparison_digest({
                'controlled_policy_sha256': measurement['controlled_policy_sha256'],
                'experimental_features': features}), 'experimental_configuration')
    require(type(report) is dict and _comparison_digest(report) == measurement['report_sha256'],
            'report_digest')
    require(set(report) == {'win_rates_by_archetype_pair', 'anomalies',
            'decision_quality_by_archetype', 'oracle_status_counts', 'card_cache_completeness',
            'log_priors', 'unavailable_metrics'} and report['unavailable_metrics'] == {}
            and type(report['unavailable_metrics']) is dict, 'report_unavailable')
    oracle, cache, priors = (report[key] for key in ('oracle_status_counts', 'card_cache_completeness', 'log_priors'))
    require(type(oracle) is dict and set(oracle) == {'unique', 'weighted'}
            and all(type(row) is dict and all(type(key) is str and count(value)
                    for key, value in row.items()) for row in oracle.values()), 'oracle_summary')
    require(type(cache) is dict and set(cache) == {'cached_cards', 'total_cards', 'missing_cards',
            'completeness_percent'} and all(count(cache[key]) for key in ('cached_cards', 'total_cards', 'missing_cards'))
            and cache['total_cards'] > 0 and cache['cached_cards'] + cache['missing_cards'] == cache['total_cards']
            and type(cache['completeness_percent']) in (int, float)
            and cache['completeness_percent'] == round(cache['cached_cards'] / cache['total_cards'] * 100, 2),
            'cache_summary')
    unique, weighted = oracle['unique'], oracle['weighted']
    require(sum(unique.values()) == cache['total_cards'] and set(unique) == set(weighted)
            and all(unique[key] > 0 and weighted[key] >= unique[key] for key in unique),
            'oracle_coverage')
    require(type(priors) is dict and set(priors) == {'cards', 'samples'} and count(priors['cards'])
            and type(priors['samples']) is dict and set(priors['samples']) == {'games', 'logs'}
            and all(count(value) for value in priors['samples'].values()), 'priors_summary')
    require(measurement['schedule_kind'] == 'fixed_games'
            and measurement['sideboard_mode'] == 'fixed_no_swaps'
            and measurement['difficulty'] in ('casual', 'strong', 'master')
            and count(measurement['max_ticks']) and measurement['max_ticks'] > 0,
            'unsupported_measurement_contract')
    limits = measurement['limits']
    require(type(limits) is dict and set(limits) == set(RESOURCE_LIMITS)
            and all(count(value) and value <= RESOURCE_LIMITS[key] for key, value in limits.items()),
            'resource_contract')
    roster, seeds, seats = (measurement[key] for key in ('roster', 'seeds', 'seats'))
    require(type(roster) is list and 2 <= len(roster) <= 100
            and type(seeds) is list and 1 <= len(seeds) <= 1000
            and all(count(seed) for seed in seeds) and len(set(seeds)) == len(seeds)
            and type(seats) is list and len(seats) == 2
            and all(type(seat) is int for seat in seats) and seats == [1, 2], 'roster_seeds_seats')
    decks = {}
    for row in roster:
        require(type(row) is dict and set(row) == {'name', 'archetype', 'content_sha256'}
                and all(type(row[key]) is str and 0 < len(row[key]) <= 128
                        and row[key] == row[key].strip() for key in ('name', 'archetype'))
                and ' vs ' not in row['archetype']
                and _comparison_hex(row['content_sha256']) and row['name'] not in decks, 'roster_row')
        decks[row['name']] = row['archetype']
    planned = len(roster) * (len(roster)-1) * len(seeds)
    require(planned <= 100000 and measurement['complete'] is True
            and measurement['status'] == 'completed_schedule'
            and all(count(measurement[key]) for key in ('planned_games', 'attempted_games', 'not_run_games'))
            and measurement['planned_games'] == measurement['attempted_games'] == planned
            and measurement['not_run_games'] == 0, 'incomplete_schedule')
    expected = {(a, b, seed, seat) for a, b in combinations(sorted(decks), 2)
                for seed in seeds for seat in seats}
    samples = measurement['samples']
    require(type(samples) is list and len(samples) == planned, 'sample_coverage')
    seen, outcomes = set(), defaultdict(Counter)
    for row in samples:
        require(type(row) is dict and set(row) == {'deck_a', 'deck_b', 'seed_token', 'deck_a_seat',
                'evidence_complete', 'status', 'winner'} and type(row['deck_a']) is str
                and type(row['deck_b']) is str and count(row['seed_token'])
                and type(row['deck_a_seat']) is int and row['deck_a_seat'] in (1, 2)
                and row['evidence_complete'] is True, 'sample_shape')
        key = row['deck_a'], row['deck_b'], row['seed_token'], row['deck_a_seat']
        require(key in expected and key not in seen, 'sample_identity')
        seen.add(key)
        require((row['status'] == 'resolved' and type(row['winner']) is int and row['winner'] in (1, 2))
                or (row['status'] == 'timeout' and row['winner'] is None), 'sample_outcome')
        archetypes = decks[row['deck_a']], decks[row['deck_b']]
        pair = tuple(sorted(archetypes))
        totals = outcomes[pair]
        totals['games'] += 1
        if row['status'] == 'timeout':
            totals['timeouts'] += 1
        else:
            winner_is_a = row['winner'] == row['deck_a_seat']
            # Mirror archetypes retain the existing reporter's player-one orientation.
            if archetypes[0] == archetypes[1]:
                winner_is_a = row['winner'] == 1
            elif archetypes != pair:
                winner_is_a = not winner_is_a
            totals['wins_a' if winner_is_a else 'wins_b'] += 1
    anomalies, quality = report['anomalies'], report['decision_quality_by_archetype']
    require(type(anomalies) is dict and set(anomalies) == set(ANOMALY_KEYS)
            and all(count(value) for value in anomalies.values()), 'anomaly_counts')
    require(type(quality) is dict and set(quality) == set(decks.values())
            and all(type(row) is dict and set(row) == set(DECISION_QUALITY_METRICS)
                    and all(count(value) for value in row.values()) for row in quality.values()),
            'quality_counts')
    pairs = report['win_rates_by_archetype_pair']
    require(type(pairs) is dict and set(pairs) == {f'{a} vs {b}' for a, b in outcomes}, 'pair_coverage')
    for (a, b), totals in outcomes.items():
        pair = pairs[f'{a} vs {b}']
        require(type(pair) is dict and set(pair) == {'archetype_a', 'archetype_b', 'games',
                'resolved_games', 'timeouts', 'wins_a', 'wins_b', 'win_rate_a', 'win_rate_b',
                'wilson_ci_a', 'wilson_ci_b'} and pair['archetype_a'] == a and pair['archetype_b'] == b,
                'pair_shape')
        resolved = totals['wins_a'] + totals['wins_b']
        require(resolved > 0 and all(count(pair[key]) and pair[key] == totals[key]
                for key in ('games', 'timeouts', 'wins_a', 'wins_b'))
                and count(pair['resolved_games']) and pair['resolved_games'] == resolved, 'pair_counts')
        for side in ('a', 'b'):
            wins = pair[f'wins_{side}']
            require(type(pair[f'win_rate_{side}']) in (int, float)
                    and pair[f'win_rate_{side}'] == round(wins / resolved * 100, 2)
                    and _comparison_digest(pair[f'wilson_ci_{side}']) == _comparison_digest(
                        AnalyticsService._wilson_interval(wins, resolved)), 'pair_rates')
    require(anomalies['timeouts'] == sum(row['timeouts'] for row in outcomes.values()), 'timeout_total')
    return report, measurement


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare bound report artifacts only; never certify AI strength or play games."""
    try:
        old, old_binding = _comparison_admit(before)
        new, new_binding = _comparison_admit(after)
        differing_source = {'source_base_commit', 'backend_before_sha256', 'backend_after_sha256',
                            'report_sha256', 'samples', 'experimental_features', 'policy_configuration_sha256'}
        _comparison_require(all(_comparison_digest(old_binding[key]) == _comparison_digest(new_binding[key])
                                for key in old_binding if key not in differing_source), 'incomparable_inputs')
        _comparison_require(set(old_binding['experimental_features']) == set(new_binding['experimental_features']),
                            'different_experimental_features')
        _comparison_require(all(_comparison_digest(old[key]) == _comparison_digest(new[key])
                                for key in ('oracle_status_counts', 'card_cache_completeness', 'log_priors')),
                            'changed_data_summaries')
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {'schema_version': 1, 'status': 'unavailable', 'reason': 'invalid_or_incomparable_evidence'}
    deltas = []
    totals = [Counter(), Counter()]
    for ordinal, archetype in enumerate(sorted(old['decision_quality_by_archetype'])):
        for metric in DECISION_QUALITY_METRICS:
            left, right = (report['decision_quality_by_archetype'][archetype][metric] for report in (old, new))
            totals[0][metric] += left
            totals[1][metric] += right
            deltas.append(dict(group='quality', archetype_ordinal=ordinal, metric=metric,
                               before=left, after=right, delta=right-left))
    for metric in ANOMALY_KEYS:
        left, right = (report['anomalies'][metric] for report in (old, new))
        deltas.append(dict(group='anomalies', metric=metric, before=left, after=right, delta=right-left))
    pair_deltas = []
    for ordinal, key in enumerate(sorted(old['win_rates_by_archetype_pair'])):
        left, right = (report['win_rates_by_archetype_pair'][key] for report in (old, new))
        exact_delta = 100 * (Fraction(right['wins_a'], right['resolved_games'])
                             - Fraction(left['wins_a'], left['resolved_games']))
        delta = round(float(exact_delta), 2)
        pair_deltas.append(dict(pair_ordinal=ordinal, delta_percentage_points_a=delta,
                                delta_percentage_points_b=-delta, moved_over_fifteen=abs(exact_delta) > 15))
    flags = [row for row in pair_deltas if row['moved_over_fifteen']]
    regressions = [row for row in deltas if row['delta'] > 0]
    no_increase = lambda *metrics: all(totals[1][key] <= totals[0][key] for key in metrics)
    decrease = lambda key: totals[1][key] < totals[0][key]
    anomaly_no_increase = lambda *metrics: all(new['anomalies'][key] <= old['anomalies'][key] for key in metrics)

    def archetype_spread(report):
        wins, games = Counter(), Counter()
        for row in report['win_rates_by_archetype_pair'].values():
            for side in ('a', 'b'):
                archetype = row[f'archetype_{side}']
                wins[archetype] += row[f'wins_{side}']
                games[archetype] += row['resolved_games']
        rates = [Fraction(wins[key], games[key]) for key in games]
        return max(rates) - min(rates)

    spread_no_increase = archetype_spread(new) <= archetype_spread(old)
    def provenance(binding):
        return dict(source_base_commit=binding['source_base_commit'], backend_sha256=binding['backend_before_sha256'],
                    engine_rules_sha256=binding['engine_rules_sha256'],
                    controlled_policy_sha256=binding['controlled_policy_sha256'],
                    policy_configuration_sha256=binding['policy_configuration_sha256'],
                    experimental_features=dict(binding['experimental_features']))

    return dict(schema_version=1, status='comparable', scope='declared_fixed_game_schedule_only',
                provenance=dict(before=provenance(old_binding), after=provenance(new_binding)),
                counter_deltas=deltas, regressions=regressions, pair_deltas=pair_deltas, pair_flags=flags,
                criteria=dict(p2_nonregression=no_increase('bad_blocks', 'lethal_misses'),
                    p3_nonregression=anomaly_no_increase('timeouts', 'stall_streaks')
                                     and no_increase('stall_streaks'),
                    p4_lethal_decrease=decrease('lethal_misses'),
                    p4_unused_mana_decrease=decrease('unused_mana_passes'),
                    p4_unexplained_pass_decrease=None,
                    p4_order_nonregression=no_increase('missed_land_drops', 'unused_mana_passes')
                                           and spread_no_increase,
                    final_metrics=decrease('lethal_misses') and decrease('bad_blocks')
                                  and anomaly_no_increase('timeouts') and not flags and not regressions),
                unavailable_criteria=['unexplained_pass_priority_clusters'],
                interpretation='artifact validation, not authentic execution, full BO3 coverage or AI strength')


def _comparison_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Compare two explicitly bound baseline report packages')
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    args = parser.parse_args(argv)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _comparison_require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result

    def read(path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            _comparison_require(stat.S_ISREG(info.st_mode) and info.st_size <= 1048576,
                                'comparison_input_bound')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                payload = stream.read(1048577)
        finally:
            os.close(fd)
        _comparison_require(len(payload) <= 1048576, 'comparison_input_bound')
        return json.loads(payload, object_pairs_hook=unique_object,
                          parse_constant=lambda value: _comparison_require(False, 'nonfinite_json'))

    try:
        result = compare_reports(read(args.before), read(args.after))
    except (OSError, ValueError, TypeError, RecursionError):
        result = {'schema_version': 1, 'status': 'unavailable', 'reason': 'invalid_or_incomparable_evidence'}
    print(render_report(result), end='')
    return 0 if result['status'] == 'comparable' and result['criteria']['final_metrics'] else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine baseline gate artifacts into one deterministic report")
    parser.add_argument("--oracle", required=True, help="Path to oracle_corpus_report JSON")
    parser.add_argument("--gate", required=True, help="Path to CI gate/overnight summary JSON")
    parser.add_argument("--games-jsonl", required=True, help="Path to the gate run's full card-play game traces")
    parser.add_argument("--log-priors", default="ai/data/log_priors.json", help="Path to AI log priors JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] == 'compare':
        return _comparison_main(arguments[1:])
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
