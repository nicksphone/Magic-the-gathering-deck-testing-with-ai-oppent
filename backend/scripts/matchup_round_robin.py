"""Offline fixed-board BO3 measurement. Planning never imports the game engine."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path

EXPORT_BASE_COMMIT = '46158ddb40a2e67e27a37c0854eba8d2bc05a281'
BUILTIN_SHA256 = '236bc11807d9aeea3134c2b1ec9d1fa73a29d9dc366bf0e11a79ed605a14c0b3'
BACKEND = Path(__file__).resolve().parents[1]


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def collect_source_manifest(backend):
    """Ordinary backend files, not dependency/runtime/evidence storage."""
    root = Path(backend)
    if not root.is_absolute() or root.resolve() != root or any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('Canonical owned backend directory required')
    files = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        parts = relative.parts
        if (any(part in ('__pycache__', '.pytest_cache', '.venv', 'venv', 'node_modules') for part in parts)
                or parts[0] in ('runtime', 'generated', 'evidence', 'training_runs')
                or parts[:2] == ('card_data', 'image_cache') or path.suffix in ('.pyc', '.pyo')):
            continue
        if path.is_symlink():
            raise ValueError('Source symlink is not ordinary owned source')
        if path.is_file():
            files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise ValueError('Nonordinary source member')
    return files


def verify_source_binding(binding, backend):
    if (type(binding) is not dict or set(binding) != {'schema_version', 'source_base_commit', 'backend_files', 'backend_sha256'}
            or type(binding['schema_version']) is not int or binding['schema_version'] != 1
            or type(binding['source_base_commit']) is not str or len(binding['source_base_commit']) != 40
            or any(char not in '0123456789abcdef' for char in binding['source_base_commit'])
            or type(binding['backend_files']) is not dict or not binding['backend_files']
            or type(binding['backend_sha256']) is not str):
        raise ValueError('Explicit measured-source binding required; no ambient Git/default epoch')
    actual = collect_source_manifest(backend)
    if canonical_bytes(actual) != canonical_bytes(binding['backend_files']) or digest(actual) != binding['backend_sha256']:
        raise ValueError('Measured backend source mismatch')
    return binding['backend_sha256']


def source_closure(binding, backend, before_sha256):
    try:
        after = digest(collect_source_manifest(backend))
    except (OSError, ValueError):
        after = None
    return dict(source_base_commit=binding['source_base_commit'], binding_sha256=digest(binding),
                before_sha256=before_sha256, after_sha256=after,
                equal=before_sha256 == after == binding['backend_sha256'],
                ordinary_files=len(binding['backend_files']))


def builtin_templates():
    raw = (BACKEND / 'decks/builtin_decks.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != BUILTIN_SHA256:
        raise ValueError('Builtin source changed; explicit roster review required')
    tree = ast.parse(raw)
    return ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.AnnAssign)
                                 and isinstance(node.target, ast.Name) and node.target.id == 'BUILTIN_DECKS'))


def _board_inventory(board, *, main):
    if type(board) is not list or len(board) > 250:
        raise ValueError('Explicit bounded board list required')
    counts = Counter()
    for card in board:
        if (type(card) is not dict or type(card.get('quantity')) is not int
                or not 1 <= card['quantity'] <= 250
                or type(card.get('card_name')) is not str or not card['card_name'].strip()
                or any(type(card.get(key)) is not str for key in ('oracle_text', 'mana_cost', 'type_line'))
                or not card['type_line'].strip()):
            raise ValueError('Typed complete printed card fields required')
        counts[card['card_name']] += card['quantity']
    if sum(counts.values()) > 250 or (main and sum(counts.values()) < 60):
        raise ValueError('Invalid board size')
    return dict(counts)


def _roster(rows):
    expected = builtin_templates()
    if type(rows) is not list or len(rows) != len(expected):
        raise ValueError('Complete builtin roster required; no subset qualification')
    names = set()
    for row in rows:
        if (type(row) is not dict or row.get('source') != 'builtin' or row.get('id') is not None
                or type(row.get('name')) is not str or row['name'] not in expected or row['name'] in names
                or row.get('classification_status') not in ('resolved', 'unknown')
                or type(row.get('archetype')) is not str or not row['archetype']):
            raise ValueError('Unique shipped source-name identity required')
        names.add(row['name'])
        _board_inventory(row.get('mainboard'), main=True)
        _board_inventory(row.get('sideboard'), main=False)
    return sorted(deepcopy(rows), key=lambda row: row['name'])


def make_export(rows, *, corpus_sha256):
    decks = _roster(rows)
    if type(corpus_sha256) is not str or len(corpus_sha256) != 64 or any(c not in '0123456789abcdef' for c in corpus_sha256):
        raise ValueError('Explicit canonical corpus SHA256 required')
    return dict(schema_version=1, source_commit=EXPORT_BASE_COMMIT, builtin_sha256=BUILTIN_SHA256,
                corpus_sha256=corpus_sha256, decks_sha256=digest(decks), decks=decks,
                sideboard_mode='fixed_no_swaps')


def validate_export(export):
    if (type(export) is not dict or type(export.get('schema_version')) is not int
            or export['schema_version'] != 1 or export.get('source_commit') != EXPORT_BASE_COMMIT
            or export.get('builtin_sha256') != BUILTIN_SHA256 or export.get('sideboard_mode') != 'fixed_no_swaps'):
        raise ValueError('Unsupported offline roster contract')
    rebuilt = make_export(export.get('decks'), corpus_sha256=export.get('corpus_sha256'))
    if rebuilt['decks_sha256'] != export.get('decks_sha256'):
        raise ValueError('Deck content digest mismatch')
    return rebuilt['decks']


def build_schedule(rows, seed_tokens):
    from decks.selection import cohort_identity, cohort_pair_seed
    decks = _roster(rows)
    if (type(seed_tokens) is not list or not seed_tokens or
            any(type(token) is not int or token < 0 for token in seed_tokens) or len(set(seed_tokens)) != len(seed_tokens)):
        raise ValueError('Explicit unique nonnegative integer seed tokens required')
    schedule = []
    for left, right in combinations(decks, 2):
        pair = (dict(left, identity_key=cohort_identity(left)), dict(right, identity_key=cohort_identity(right)))
        for token in seed_tokens:
            root = cohort_pair_seed(*pair, token)
            for seat in (1, 2):
                schedule.append(dict(deck_a=left['name'], deck_b=right['name'], seed_token=token,
                    root_seed=root, deck_a_seat=seat, seat_one=left['name'] if seat == 1 else right['name'],
                    seat_two=right['name'] if seat == 1 else left['name'], sideboard_mode='fixed_no_swaps'))
    return schedule


def check_fixed_boards(original, current):
    # Canonical comparison also rejects bool/int and changes to retained card bodies.
    if canonical_bytes(original) != canonical_bytes(current):
        raise ValueError('Fixed-board input changed')


def summarize_pair(rows, *, wilson):
    wins = {1: 0, 2: 0}
    unresolved = Counter()
    for row in rows:
        if row['status'] == 'resolved' and type(row['winner']) is int and row['winner'] in (1, 2):
            wins[1 if row['winner'] == row['deck_a_seat'] else 2] += 1
        else:
            unresolved[row['status']] += 1
    total = sum(wins.values())
    intervals = ({key: {**wilson(wins[seat], total), 'unit': 'percent', 'sample_unit': 'resolved_bo3_series'}
                  for key, seat in (('deck_a', 1), ('deck_b', 2))} if total else None)
    return dict(wins_a=wins[1], wins_b=wins[2], resolved_series=total, attempted_series=len(rows),
        timeouts=unresolved.get('timeout', 0), unresolved=dict(unresolved), win_rate_ci=intervals,
        unavailable_reason=None if total else 'no resolved BO3 series',
        inference='descriptive resolved-conditional Wilson; mirrored seeds are dependent')


def quality_for_pair(rows, *, metrics):
    out = {}
    for name in ('deck_a', 'deck_b'):
        values, available, seen = Counter(), dict.fromkeys(metrics, True), False
        for row in rows:
            pid = str(row['deck_a_seat'] if name == 'deck_a' else 3 - row['deck_a_seat'])
            for game in row['games']:
                seen = True
                quality = game.get('quality') or {}
                for metric in metrics:
                    value = (quality.get('counts', {}).get(pid) or {}).get(metric)
                    valid = (game.get('evidence_complete') is True
                             and (quality.get('availability', {}).get(pid) or {}).get(metric) is True
                             and type(value) is int and value >= 0)
                    available[metric] = available[metric] and valid
                    if valid:
                        values[metric] += value
        out[name] = {metric: values[metric] if seen and available[metric] else None for metric in metrics}
    return out


def _template_inventory(text):
    # Builtin syntax is pinned and intentionally finite; this is not a card parser.
    boards = {'mainboard': Counter(), 'sideboard': Counter()}
    section = 'mainboard'
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';', '//')):
            continue
        if line.casefold().rstrip(':') in ('sideboard', 'sb'):
            section = 'sideboard'
            continue
        if line.casefold().rstrip(':') in ('mainboard', 'maindeck', 'deck'):
            section = 'mainboard'
            continue
        quantity, name = line.split(maxsplit=1)
        boards[section][name] += int(quantity)
    return {key: dict(value) for key, value in boards.items()}


def admit_execution_rows(rows):
    """Structural/export hashes are not canonical card admission."""
    from card_data.hydration import ready_for_match
    templates = builtin_templates()
    for row in rows:
        inventories = {key: _board_inventory(row[key], main=key == 'mainboard') for key in ('mainboard', 'sideboard')}
        if inventories != _template_inventory(templates[row['name']]):
            raise ValueError('Prepared boards differ from the shipped builtin inventory')
        if not all(ready_for_match(card) for key in ('mainboard', 'sideboard') for card in row[key]):
            raise ValueError('Missing complete local canonical card admission')


def write_private_game(directory, ordinal, result, raw_log):
    raw_bytes = json.dumps(raw_log, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    payload = canonical_bytes(dict(schema_version=1, result=result, raw_log=raw_log,
                                   raw_sha256=hashlib.sha256(raw_bytes).hexdigest()))
    path = directory / f'game-{ordinal:02d}.json'
    with path.open('xb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != payload:
        raise OSError('Private game readback differs')
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(reference=path.name, complete=True, bytes=len(raw_bytes),
                raw_sha256=hashlib.sha256(raw_bytes).hexdigest(), record_sha256=hashlib.sha256(payload).hexdigest())


def run_round_robin(export, seed_tokens, *, difficulty, max_ticks, limits, private_directory, source_binding=None):
    """Actual execution requires an external IO/resource approval; no implicit DB."""
    source_before = verify_source_binding(source_binding, BACKEND)
    source_binding = deepcopy(source_binding)
    rows = validate_export(export)
    schedule = build_schedule(rows, seed_tokens)
    if difficulty not in ('casual', 'strong', 'master') or type(max_ticks) is not int or max_ticks <= 0:
        raise ValueError('Explicit difficulty and positive tick cap required')
    from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS
    if type(limits) is not dict or set(limits) != set(RESOURCE_LIMITS):
        raise ValueError('Complete explicit shared resource limits required')
    if any(type(value) is not int or value < 0 or value > RESOURCE_LIMITS[key] for key, value in limits.items()):
        raise ValueError('Limits may not widen the shared policy')
    admit_execution_rows(rows)
    from scripts.regression_matrix_replay import run_game, run_match
    from analytics.decision_quality import build_trace_payload, summarize_trace_rows, DECISION_QUALITY_METRICS
    from analytics.service import AnalyticsService
    directory = Path(private_directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    manifest = dict(export_sha256=digest(export), input_export_base_commit=export['source_commit'],
                    source_base_commit=source_binding['source_base_commit'], source_binding_sha256=digest(source_binding),
                    difficulty=difficulty, max_ticks=max_ticks, limits=dict(limits), seeds=list(seed_tokens),
                    sideboard_mode='fixed_no_swaps', planned_series=len(schedule), planned_pairs=len(rows)*(len(rows)-1)//2,
                    roster=[dict(name=row['name'], classification_status=row['classification_status'],
                        archetype=row['archetype'], content_sha256=digest(row),
                        mainboard_cards=sum(card['quantity'] for card in row['mainboard']),
                        sideboard_cards=sum(card['quantity'] for card in row['sideboard'])) for row in rows],
                    source_scope='explicit current ordinary backend binding; file provenance, not live CodeRef authority',
                    backend_before_sha256=source_before)
    by_name = {row['name']: row for row in rows}
    original_rows = deepcopy(rows)
    original_export = canonical_bytes(export)
    receipt_keys = ('complete', 'bytes', 'raw_sha256', 'reference')
    source_equal = True
    series = []
    try:
        for index, scheduled in enumerate(schedule):
            one, two = by_name[scheduled['seat_one']], by_name[scheduled['seat_two']]
            series_directory = directory / f'series-{index:05d}'
            series_directory.mkdir(mode=0o700)
            budget = ResourceBudget(limits)  # One deadline and cumulative log budget per BO3, never per game.
            raw_quality = []
            written_receipts = []
            delivered = []
            ordinal = 0
            def trace(state, pid, legal, action, decision):
                return build_trace_payload(state, pid, legal, action, getattr(decision, 'reasoning', ''),
                                           knowledge_usage=getattr(decision, 'knowledge_usage', None))
            def record(result, raw):
                nonlocal ordinal
                ordinal += 1
                receipt = write_private_game(series_directory, ordinal, result, raw)
                written_receipts.append({key: receipt[key] for key in receipt_keys})
                raw_quality.append(summarize_trace_rows(({'log': raw},)))
                return receipt
            def play(a, b, seed, level, ticks, **options):
                if canonical_bytes(export) != original_export:
                    raise ValueError('Original export changed')
                check_fixed_boards(original_rows, rows)
                # Independent copies protect immutable admitted boards from a game callback.
                game_boards = deepcopy([a, b])
                before = deepcopy(game_boards)
                result = run_game(*game_boards, seed, level, ticks,
                                  trace_builder=trace, budget=budget, record_game=record, **options)
                delivered.append(result)
                check_fixed_boards(before, game_boards)
                check_fixed_boards(original_rows, rows)
                return result
            series_stop = None
            try:
                match = run_match(one['mainboard'], two['mainboard'], scheduled['root_seed'], difficulty, max_ticks, 3,
                                  game_runner=play)
            except Exception:
                # Earlier actual deliveries/receipts survive a later setup interruption.
                series_stop = 'execution_error'
                match = dict(winner=None, games=delivered, timeout=False, draw_cap_reached=False,
                             wins={'deck_a': sum(g['winner'] == 1 for g in delivered),
                                   'deck_b': sum(g['winner'] == 2 for g in delivered)})
            games = []
            for n, game in enumerate(match['games']):
                games.append({key: value for key, value in game.items() if key != 'log'})
                games[-1].update(quality=raw_quality[n] if n < len(raw_quality) else None,
                                 evidence_complete=game.get('evidence') is not None)
                if game.get('stop_reason') == 'resource_limit':
                    games[-1].update(quality=None, quality_available=False,
                                     quality_unavailable_reason='partial_game_resource_limit')
            stop = next((g['stop_reason'] for g in games if g.get('stop_reason')), None)
            status = series_stop or stop or ('timeout' if match['timeout'] else 'draw_cap' if match['draw_cap_reached'] else 'resolved')
            series.append({**scheduled, 'winner': match['winner'] if status == 'resolved' else None,
                           'wins': match['wins'], 'status': status, 'games': games})
            if stop or series_stop:
                if (stop == 'resource_limit' and series_stop is None and games
                        and len(written_receipts) == len(games)
                        and all(game['evidence_complete'] is True and type(game['evidence']) is dict
                                and set(game['evidence']) == set(receipt_keys)
                                and game['evidence']['complete'] is True
                                and canonical_bytes(game['evidence']) == canonical_bytes(receipt)
                                for game, receipt in zip(games, written_receipts))):
                    source_equal = source_closure(source_binding, BACKEND, source_before)['equal']
                    if source_equal:
                        continue
                break
    finally:
        closure = source_closure(source_binding, BACKEND, source_before)
        closure['equal'] = closure['equal'] and source_equal
    pairs = []
    for left, right in combinations(rows, 2):
        for token in seed_tokens:
            records = [row for row in series if row['deck_a'] == left['name'] and row['deck_b'] == right['name']
                       and row['seed_token'] == token]
            qualities = quality_for_pair(records, metrics=DECISION_QUALITY_METRICS)
            pairs.append(dict(deck_a=left['name'], deck_b=right['name'], seed=token,
                **summarize_pair(records, wilson=AnalyticsService._wilson_interval),
                decision_quality_a=qualities['deck_a'], decision_quality_b=qualities['deck_b']))
    complete = (closure['equal'] and len(series) == len(schedule)
                and all(row['status'] in ('resolved', 'timeout', 'draw_cap') for row in series))
    if not closure['equal']:
        for record in series:
            for game in record['games']:
                game.update(quality=None, quality_available=False,
                            quality_unavailable_reason='source_unavailable')
        for pair in pairs:
            pair['decision_quality_a'] = dict.fromkeys(DECISION_QUALITY_METRICS)
            pair['decision_quality_b'] = dict.fromkeys(DECISION_QUALITY_METRICS)
        manifest['source_unavailable_reason'] = 'ordinary backend changed during execution'
    return dict(schema_version=1, manifest=manifest, attempted_series=len(series),
                measured_source=closure,
                not_run_series=len(schedule)-len(series), complete=complete,
                status='completed_schedule' if complete else 'stopped',
                pairs=pairs, series=series)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deck-export', required=True, help='Complete prepared local canonical roster JSON; no DB fallback')
    parser.add_argument('--seed-token', type=int, action='append', required=True)
    parser.add_argument('--output', required=True, help='New sanitized summary/plan file')
    parser.add_argument('--execute', action='store_true', help='Requires separately approved actual game IO contract')
    parser.add_argument('--private-directory')
    parser.add_argument('--limits-json')
    parser.add_argument('--source-binding', help='Explicit current whole ordinary backend binding JSON; no Git HEAD lookup')
    parser.add_argument('--difficulty', choices=('casual', 'strong', 'master'))
    parser.add_argument('--max-ticks', type=int)
    args = parser.parse_args()
    # Reserve the exact new summary before any execution callback. Never remove it.
    with Path(args.output).open('x', encoding='utf-8') as handle:
        # Direct CLI imports only the stdlib until explicit execution is requested.
        import sys
        sys.path.insert(0, str(BACKEND))
        export = json.loads(Path(args.deck_export).read_text())
        rows = validate_export(export)
        schedule = build_schedule(rows, args.seed_token)
        if args.execute:
            if not args.private_directory or not args.limits_json or not args.difficulty or args.max_ticks is None or not args.source_binding:
                parser.error('Execution requires private-directory, limits, difficulty, max-ticks and current source-binding')
            if not os.environ.get('MTG_DATABASE_PATH'):
                parser.error('Replay import requires explicit isolated MTG_DATABASE_PATH; never use the default DB')
            result = run_round_robin(export, args.seed_token, difficulty=args.difficulty, max_ticks=args.max_ticks,
                limits=json.loads(Path(args.limits_json).read_text()), private_directory=args.private_directory,
                source_binding=json.loads(Path(args.source_binding).read_text()))
        else:
            result = dict(schema_version=1, status='planned_not_executed', export_sha256=digest(export),
                          planned_pairs=len(rows)*(len(rows)-1)//2, planned_series=len(schedule), schedule=schedule)
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    return 0 if not args.execute or result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
