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
    from card_data.seed_cards import SEED_CARD_DATA
    from card_data.hydration import ready_for_match
    canonical_names = {alias: payload['name'] for printed, payload in SEED_CARD_DATA.items()
                       for alias in (printed, payload['name'])}

    def canonical_inventory(inventory):
        counts = Counter()
        for name, quantity in inventory.items():
            if name not in canonical_names:
                raise ValueError('Unsupported exact seed card name')
            counts[canonical_names[name]] += quantity
        return dict(counts)

    templates = builtin_templates()
    for row in rows:
        inventories = {key: canonical_inventory(_board_inventory(row[key], main=key == 'mainboard'))
                       for key in ('mainboard', 'sideboard')}
        expected = {key: canonical_inventory(board)
                    for key, board in _template_inventory(templates[row['name']]).items()}
        if inventories != expected:
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


def comparison_gate_totals(legacy_totals):
    """NEW fixed-game aggregate; the legacy non-long timeout total is unchanged."""
    keys = {'timeouts', 'long_game_timeouts', 'stall_streaks', 'invalid_targets',
            'cost_failures', 'additional_cost_failures'}
    if (type(legacy_totals) is not dict or set(legacy_totals) != keys
            or any(type(value) is not int or value < 0 for value in legacy_totals.values())):
        raise ValueError('Complete typed legacy anomaly counters required')
    result = dict(legacy_totals)
    result['timeouts'] += result['long_game_timeouts']
    return result


def fixed_game_counters(raw_log, tick_timeout):
    """Legacy gate semantics over ONLY a complete accepted raw game log."""
    from analytics.decision_quality import parse_trace_row
    from analytics.replay_tools import classify_timeout_state
    from analytics.service import AnalyticsService
    if type(tick_timeout) is not bool or type(raw_log) is not list or any(type(line) is not str for line in raw_log):
        raise ValueError('Complete raw game log and actual tick-timeout flag required')
    counts = Counter(dict.fromkeys(('timeouts', 'long_game_timeouts', 'stall_streaks',
        'invalid_targets', 'cost_failures', 'additional_cost_failures',
        'passed_with_options', 'missed_land_windows', 'repeated_error_bursts'), 0))
    classification = classify_timeout_state(raw_log, tick_timeout)
    if tick_timeout:
        counts['long_game_timeouts' if classification == 'timeout_long_game' else 'timeouts'] += 1
    payloads, malformed = parse_trace_row({'log': raw_log})
    if malformed:
        raise ValueError('Malformed accepted trace cannot certify gate counters')
    streak = 0
    for payload in payloads:
        action = payload.get('action')
        if (type(action) is not dict or type(payload.get('stall_actionable_options')) is not bool
                or type(payload.get('legal_has_land')) is not bool):
            raise ValueError('Incomplete legacy gate trace observation')
        passed = action.get('type') == 'pass_priority'
        if passed and payload['stall_actionable_options']:
            counts['passed_with_options'] += 1
            streak += 1
        else:
            streak = 0
        if payload['legal_has_land'] and action.get('type') != 'play_land':
            counts['missed_land_windows'] += 1
    counts['stall_streaks'] = int(streak >= 3)
    AnalyticsService._scan_log_for_anomalies(None, raw_log, counts, Counter())
    return dict(counts)


def preflight_game_record(result, raw_log, budget):
    """Bound the exact writer envelope before the existing unbounded encoders."""
    from analytics.resource_budget import checked_json
    budget.checked_result(result)
    limit = min(budget.limits['result_json_bytes'], budget.limits['snapshot_json_bytes'])
    raw = checked_json(raw_log, limit, 'result_json', separators=(',', ':'))
    envelope = dict(schema_version=1, result=result, raw_log=raw_log,
                    raw_sha256=hashlib.sha256(raw.encode('ascii')).hexdigest())
    budget.checked_result(envelope)
    return checked_json(envelope, limit, 'result_json', separators=(',', ':'))


def measurement_runtime_identity():
    """Actual interpreter/prefix content, not an operator-supplied version label."""
    import sys
    root = Path(sys.prefix)
    files, links, directories = {}, {}, ['.']
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            links[name] = os.readlink(path)
        elif path.is_file():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            directories.append(name)
        else:
            raise ValueError('Nonordinary measured runtime input')
    binary = hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
    return dict(sha256=digest(dict(files=files, links=links, directories=directories,
        python=binary, version=sys.version)), files=len(files), symlinks=len(links),
        directories_including_root=len(directories), python_executable_sha256=binary)


def verify_measurement_callable(function, relative, binding, backend):
    """Strict loaded code/globals identity against compile-only ordinary source."""
    import sys
    import types
    module = sys.modules.get(getattr(function, '__module__', None))
    path = Path(backend) / relative
    if (relative not in binding['backend_files'] or not hasattr(function, '__code__')
            or module is None or function.__globals__ is not vars(module)
            or Path(function.__code__.co_filename).resolve() != path
            or hashlib.sha256(path.read_bytes()).hexdigest() != binding['backend_files'][relative]):
        raise ValueError('Actual loaded callable differs from measured source')
    pending = [compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)]
    matches = []
    while pending:
        code = pending.pop()
        if code.co_qualname == function.__qualname__:
            matches.append(code)
        pending.extend(item for item in code.co_consts if isinstance(item, types.CodeType))
    if len(matches) != 1 or matches[0] != function.__code__:
        raise ValueError('Loaded executable code is not the pinned source definition')


def verify_measurement_partition(binding, backend, partition, approved_sha256, configuration, activation_check):
    """Recompute reviewed function/data inverses; invoke a source-bound arm control."""
    import textwrap
    allowed = {'task2.3', 'task3.2', 'task4.1', 'task4.2', 'task4.3', 'task4.5'}
    if (type(partition) is not dict or set(partition) != {'schema_version', 'arm',
            'configuration', 'controlled_files', 'features', 'activation_control'}
            or type(partition['schema_version']) is not int or partition['schema_version'] != 1
            or type(partition['arm']) is not str or not 0 < len(partition['arm']) <= 64
            or digest(partition) != approved_sha256
            or canonical_bytes(configuration) != canonical_bytes(partition['configuration'])):
        raise ValueError('Reviewed exact source/configuration partition required')
    verify_source_binding(binding, backend)
    features = partition['features']
    if type(features) is not dict or not features or not set(features) <= allowed:
        raise ValueError('Explicit supported experimental feature hunks required')
    controlled, edits, used = dict(binding['backend_files']), {}, set()
    controlled_configuration = deepcopy(configuration)
    for feature, hunks in features.items():
        if type(hunks) is not list or not hunks:
            raise ValueError('No whole-file experimental exemption')
        for hunk in hunks:
            if (type(hunk) is not dict or set(hunk) != {'path', 'kind', 'qualified_name', 'reference', 'active'}
                    or hunk['path'] not in controlled and hunk['path'] != '@configuration'
                    or hunk['path'] != '@configuration' and not hunk['path'].startswith(('ai/', 'knowledge/'))
                    or hunk['kind'] not in ('python', 'json')
                    or type(hunk['qualified_name']) is not str or not hunk['qualified_name']):
                raise ValueError('Finite policy hunks only; rules/metrics stay controlled')
            if hunk['path'] == '@configuration' and (hunk['kind'] != 'json'
                    or hunk['qualified_name'] != 'input_sha256.priors'
                    or not any(item['path'] == 'ai/data/log_priors.json' for item in hunks)):
                raise ValueError('Only the consumed experimental priors digest may normalize in configuration')
            identity = hunk['path'], hunk['qualified_name']
            if any(identity[0] == p and (identity[1] == q or identity[1].startswith(q + '.')
                                        or q.startswith(identity[1] + '.')) for p, q in used):
                raise ValueError('Overlapping experimental hunks')
            used.add(identity)
            edits.setdefault(hunk['path'], []).append(hunk)
    for path, hunks in edits.items():
        kinds = {h['kind'] for h in hunks}
        if len(kinds) != 1:
            raise ValueError('Mixed file partition types')
        if path == '@configuration':
            tree = controlled_configuration
        else:
            text = (Path(backend) / path).read_text(encoding='utf-8')
            tree = ast.parse(text) if hunks[0]['kind'] == 'python' else json.loads(text)
        for hunk in hunks:
            names = hunk['qualified_name'].split('.')
            parent = tree
            if hunk['kind'] == 'python':
                for name in names:
                    matches = [(i, node) for i, node in enumerate(parent.body)
                        if getattr(node, 'name', None) == name
                        or isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name
                        or isinstance(node, ast.Assign) and len(node.targets) == 1
                           and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name]
                    if len(matches) != 1:
                        raise ValueError('Unique qualified AST hunk required')
                    owner, index, node = parent, matches[0][0], matches[0][1]
                    parent = node
                active = ast.parse(textwrap.dedent(hunk['active'])).body
                reference = ast.parse(textwrap.dedent(hunk['reference'])).body
                if (len(active) != 1 or len(reference) != 1
                        or type(node) not in (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign, ast.AnnAssign)
                        or ast.dump(node) != ast.dump(active[0]) or type(reference[0]) is not type(node)):
                    raise ValueError('Actual complete experimental AST differs')
                owner.body[index] = reference[0]
            else:
                for name in names[:-1]:
                    if type(parent) is not dict or name not in parent:
                        raise ValueError('Explicit existing JSON key required')
                    parent = parent[name]
                if (type(parent) is not dict or names[-1] not in parent
                        or canonical_bytes(parent[names[-1]]) != canonical_bytes(hunk['active'])):
                    raise ValueError('Actual experimental data differs')
                parent[names[-1]] = deepcopy(hunk['reference'])
        if path != '@configuration':
            controlled[path] = (hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
                                if hunks[0]['kind'] == 'python' else digest(tree))
    if canonical_bytes(controlled) != canonical_bytes(partition['controlled_files']):
        raise ValueError('Undeclared controlled source/input difference')
    identity = partition['activation_control']
    if (type(identity) is not dict or set(identity) != {'path', 'qualname'}
            or identity['path'] not in binding['backend_files'] or not callable(activation_check)
            or getattr(activation_check, '__qualname__', None) != identity['qualname']):
        raise ValueError('Genuine source-bound activation control required')
    verify_measurement_callable(activation_check, identity['path'], binding, backend)
    feature_hashes = {key: digest(value) for key, value in features.items()}
    activation = activation_check(deepcopy(configuration), dict(feature_hashes))
    expected = dict(configuration_sha256=digest(configuration), features=feature_hashes)
    if canonical_bytes(activation) != canonical_bytes(expected):
        raise ValueError('Actual activation control did not verify this arm')
    verify_source_binding(binding, backend)
    return dict(controlled_policy_sha256=digest(dict(files=controlled, configuration=controlled_configuration)),
                experimental_features=feature_hashes,
                engine_rules_sha256=digest({p: v for p, v in controlled.items()
                    if p.startswith(('rules_engine/', 'game_state/'))}),
                metric_definitions_sha256=digest({p: v for p, v in controlled.items()
                    if p in ('analytics/decision_quality.py', 'analytics/replay_tools.py', 'analytics/service.py',
                             'scripts/baseline_report.py', 'scripts/matchup_round_robin.py')}),
                activation=activation)


def run_fixed_game_measurement(export, seed_tokens, *, selected_pair, selected_token,
        difficulty, max_ticks, limits, private_directory, source_binding, partition,
        partition_sha256, activation_check, artifact_guard, oracle_path, log_priors_path):
    """Opt-in fixed probe, NOT BO3; requires a reviewed external artifact charger."""
    from analytics.resource_budget import ResourceBudget, RESOURCE_LIMITS, checked_json, checked_text
    if not callable(artifact_guard):
        raise ValueError('Approved external artifact guard required before execution')
    if (type(limits) is not dict or set(limits) != set(RESOURCE_LIMITS)
            or any(type(v) is not int or not 0 <= v <= RESOURCE_LIMITS[k] for k, v in limits.items())
            or difficulty not in ('casual', 'strong', 'master')
            or type(max_ticks) is not int or max_ticks <= 0):
        raise ValueError('Complete bounded fixed-game execution configuration required')
    budget = ResourceBudget(limits)  # Both mirrors AND their packaging share this one deadline.
    source_binding = deepcopy(source_binding)
    checked_json(dict(export=export, partition=partition, source_binding=source_binding),
                 limits['request_json_bytes'], 'request_json')
    source_before = verify_source_binding(source_binding, BACKEND)
    checked_json(export, limits['request_json_bytes'], 'request_json')
    rows = validate_export(export)
    admit_execution_rows(rows)  # Full builtin admission precedes ANY probe selection.
    schedule = build_schedule(rows, seed_tokens)
    if (type(selected_pair) is not list or len(selected_pair) != 2 or selected_pair != sorted(set(selected_pair))
            or type(selected_token) is not int or selected_token not in seed_tokens):
        raise ValueError('Explicit exact canonical pair and admitted token required')
    selected = [s for s in schedule if [s['deck_a'], s['deck_b']] == selected_pair and s['seed_token'] == selected_token]
    if len(selected) != 2 or [s['deck_a_seat'] for s in selected] != [1, 2]:
        raise ValueError('Probe must select exactly two actual mirrored games')
    from ai.deck_analysis import guess_archetype
    from scripts.regression_matrix_replay import run_game
    from analytics.decision_quality import build_trace_payload
    from scripts.baseline_report import package_measurement
    by_name = {r['name']: r for r in rows}
    runtime_before = measurement_runtime_identity()
    configuration = dict(difficulty=difficulty, max_ticks=max_ticks, limits=dict(limits), runtime=runtime_before,
        lifetime='arm_pair_token_two_fixed_games', starting_player=1, sideboard_mode='fixed_no_swaps',
        export_sha256=digest(export), corpus_sha256=export['corpus_sha256'],
        full_schedule_sha256=digest(schedule), selected=selected,
        effective_archetypes={r['name']: guess_archetype(r['mainboard']) for r in rows})
    configuration['roster'] = [dict(name=n, archetype=configuration['effective_archetypes'][n],
                                   content_sha256=digest(by_name[n])) for n in selected_pair]
    inputs = {}
    input_values = {}
    for key, value in (('oracle', oracle_path), ('priors', log_priors_path)):
        with Path(value).open('rb') as handle:
            raw = handle.read(limits['request_json_bytes'] + 1)
        if len(raw) > limits['request_json_bytes']:
            from analytics.resource_budget import SimulationResourceLimit
            raise SimulationResourceLimit('request_json')
        inputs[key] = dict(sha256=hashlib.sha256(raw).hexdigest(), path=str(Path(value).resolve()))
        input_values[key] = json.loads(raw)
    if Path(log_priors_path).resolve() != BACKEND / 'ai/data/log_priors.json':
        raise ValueError('Report priors must be the actual agent loader input')
    from scripts.oracle_corpus_report import collect_corpus
    corpus = collect_corpus()
    oracle = input_values['oracle']
    cards = oracle.get('cards') if type(oracle) is dict else None
    if (export['corpus_sha256'] != digest(corpus) or type(cards) is not list
            or any(type(c) is not dict or type(c.get('name')) is not str
                   or type(c.get('copies')) is not int or type(c.get('cached')) is not bool
                   or type(c.get('status')) is not str for c in cards)):
        raise ValueError('Complete source-derived Oracle corpus coverage required')
    actual = {c['name'].casefold(): {k: c.get(k) for k in ('name', 'copies', 'decks', 'sources')} for c in cards}
    unique, weighted = Counter(), Counter()
    for card in cards:
        unique[card['status']] += 1
        weighted[card['status']] += card['copies']
    if (len(actual) != len(cards) or canonical_bytes(actual) != canonical_bytes(corpus)
            or dict(unique) != oracle.get('status_unique') or dict(weighted) != oracle.get('status_weighted')):
        raise ValueError('Oracle corpus names/copies/status aggregates differ from actual complete source')
    configuration['input_sha256'] = {k: v['sha256'] for k, v in inputs.items()}
    checked_json(configuration, limits['request_json_bytes'], 'request_json')
    provenance = verify_measurement_partition(source_binding, BACKEND, partition,
        partition_sha256, configuration, activation_check)
    from ai.agent import AIAgent
    from ai.log_priors import load_log_priors
    for function, path in ((run_game, 'scripts/regression_matrix_replay.py'),
            (build_trace_payload, 'analytics/decision_quality.py'),
            (guess_archetype, 'ai/deck_analysis.py'), (AIAgent.__init__, 'ai/agent.py'),
            (load_log_priors, 'ai/log_priors.py'), (collect_corpus, 'scripts/oracle_corpus_report.py')):
        verify_measurement_callable(function, path, source_binding, BACKEND)
    if AIAgent._log_priors_cache is not None and canonical_bytes(AIAgent._log_priors_cache) != canonical_bytes(load_log_priors()):
        raise ValueError('Agent priors cache differs from the actual pinned loader input')
    directory = Path(private_directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    games, game_rows, game_records, legacy = [], [], [], Counter()
    original_rows = deepcopy(rows)
    def write(name, value, *, jsonl=False):
        budget.check_deadline()
        text = checked_json(value, limits['result_json_bytes'], 'result_json', separators=(',', ':'))
        data = (text + ('\n' if jsonl else '')).encode('ascii')
        path = directory / name
        artifact_guard(path, len(data))
        with path.open('xb') as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        if path.read_bytes() != data:
            raise OSError('Fixed measurement readback differs')
        budget.check_deadline()
        return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    try:
        for ordinal, scheduled in enumerate(selected, 1):
            budget.check_deadline()
            one, two = [by_name[scheduled[key]] for key in ('seat_one', 'seat_two')]
            boards = deepcopy([one['mainboard'], two['mainboard']])
            checked_json(dict(boards=boards, configuration=configuration), limits['request_json_bytes'], 'request_json')
            raw_delivery = []
            def before_encode(result, raw):
                preflight_game_record(result, raw, budget)
            def record(result, raw):
                encoded = preflight_game_record(result, raw, budget)
                artifact_guard(directory / f'game-{ordinal:02d}.json', len(encoded.encode('ascii')))
                written_result = deepcopy(result)
                receipt = write_private_game(directory, ordinal, result, raw)
                game_records.append(dict(ordinal=ordinal, coordinate=deepcopy(scheduled),
                    receipt=deepcopy(receipt), result=written_result))
                raw_delivery.append(list(raw))
                budget.check_deadline()
                return receipt
            record.before_encode = before_encode
            def trace(state, pid, legal, action, decision):
                return build_trace_payload(state, pid, legal, action, getattr(decision, 'reasoning', ''),
                    knowledge_usage=getattr(decision, 'knowledge_usage', None))
            try:
                result = run_game(*boards, scheduled['root_seed'], difficulty, max_ticks,
                    starting_player=1, trace_builder=trace, budget=budget, record_game=record)
                check_fixed_boards([one['mainboard'], two['mainboard']], boards)
                check_fixed_boards(original_rows, rows)
                status = (result.get('stop_reason') or ('timeout' if result['winner'] is None
                          else 'draw' if result['winner'] == 0 else 'resolved'))
                complete = result.get('evidence') is not None and len(raw_delivery) == 1
                games.append(dict(scheduled, status=status, winner=result['winner'],
                    evidence_complete=complete, result={k: v for k, v in result.items() if k != 'log'}))
                if status not in ('resolved', 'timeout') or not complete:
                    break
                raw = raw_delivery[0]
                counters = fixed_game_counters(raw, status == 'timeout')
                legacy.update(counters)
                game_rows.append(dict(deck_a=one['name'], deck_b=two['name'], deck_a_id=one.get('id'),
                    deck_b_id=two.get('id'), deck_a_archetype=configuration['effective_archetypes'][one['name']],
                    deck_b_archetype=configuration['effective_archetypes'][two['name']], log=raw,
                    pair_a=scheduled['deck_a'], pair_b=scheduled['deck_b'], seed_token=selected_token,
                    root_seed=scheduled['root_seed'], deck_a_seat=scheduled['deck_a_seat'], starting_player=1,
                    winner=result['winner'], turns=result['turn'], ticks=result['ticks'],
                    termination_status='resolved' if status == 'resolved' else __import__(
                        'analytics.replay_tools', fromlist=['classify_timeout_state']).classify_timeout_state(raw, True),
                    evidence=result['evidence'], counters=counters))
            except Exception as error:
                name = checked_text(type(error).__name__, limits['error_utf8_bytes'], 'error_utf8')
                from analytics.resource_budget import SimulationResourceLimit
                failure = dict(scheduled, status='resource_limit' if isinstance(error, SimulationResourceLimit)
                               else 'execution_error', winner=None,
                               evidence_complete=False, error_type=name)
                if len(games) == ordinal:
                    games[-1] = failure
                else:
                    games.append(failure)
                break
    finally:
        closure = source_closure(source_binding, BACKEND, source_before)
    all_complete = closure['equal'] and len(game_rows) == len(selected)
    legacy_totals = {k: int(legacy[k]) for k in ('timeouts', 'long_game_timeouts', 'stall_streaks',
        'invalid_targets', 'cost_failures', 'additional_cost_failures')}
    gate = dict(decks=[dict(name=n, archetype=configuration['effective_archetypes'][n]) for n in selected_pair],
                totals=comparison_gate_totals(legacy_totals))
    output_files = {}
    output_files['comparison-gate.json'] = write('comparison-gate.json', gate)
    output_files['legacy-gate.json'] = write('legacy-gate.json', dict(totals=dict(legacy),
        complete=all_complete, counter_definition='unchanged_legacy_timeouts_exclude_long'))
    # Each exact row is independently bounded; no unbounded joined JSONL string.
    for index, row in enumerate(game_rows):
        output_files[f'row-{index:02d}.jsonl'] = write(f'row-{index:02d}.jsonl', row, jsonl=True)
    production = dict(configuration=configuration, partition=provenance, arm=partition['arm'],
        partition_sha256=partition_sha256, inputs=inputs, source=closure, selected=selected,
        full_schedule_sha256=digest(schedule), excluded_coordinates=[s for s in schedule if s not in selected],
        rows=game_rows, games=games, game_records=game_records, legacy_totals=legacy_totals, complete=all_complete,
        attempted_games=len(games), not_run_games=len(selected)-len(games),
        budget_identity=id(budget), budget_deadline=budget.deadline,
        snapshot_boundary='not_exercised_no_snapshot_operation', output_files=dict(output_files))
    producer_file = write('producer.json', production)
    package = package_measurement(production, directory=directory, oracle_path=oracle_path,
        log_priors_path=log_priors_path, budget=budget, artifact_guard=artifact_guard)
    if not source_closure(source_binding, BACKEND, source_before)['equal']:
        raise ValueError('Source changed during packaging; no final delivery')
    if measurement_runtime_identity() != runtime_before:
        raise ValueError('Runtime changed during execution/packaging; no final delivery')
    return dict(production=production, producer_file=producer_file, package=package)


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
