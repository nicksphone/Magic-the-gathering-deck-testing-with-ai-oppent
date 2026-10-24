"""Explicit, closed MatrixQuota110 -> private raw exports; never save/adopt priors.

Expected seals/lineage are caller-approved trust anchors, not proof of origin
supplied by the measured producer. This is not the legacy Schema2 intake.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile


_PRODUCERS = {
    'scripts/matchup_round_robin.py': 'ad2c1c1df3e9204152f16ac579ab2b870a33f04d5a5ccce43010b8f22a518f4f',
    'scripts/regression_matrix_replay.py': 'd29588861eb7a471ae3616fd79a4591c4b56050cc4ef9d1fe9db0e7ee3228b10',
    'scripts/build_ai_log_priors.py': '5142857efe9051889a91b5b4e7db40a199d37afd1afb066b1a779d1d073d2e4c',
}
_CHECKS = (
    'role_inputs_equal', 'prepared_inputs_equal', 'setup_approval_equal',
    'source_equal', 'full_source_metadata_equal', 'F_equal', 'full_F_metadata_equal',
    'runtime_equal', 'system_equal', 'parent_resources_equal', 'physical_closed',
    'own_cgroup_quiet', 'C_only_owned', 'data_fuser_empty', 'no_SQL_files',
    'true_actor_OS_exit0', 'not_stopped', 'actor_original_error_absent',
    'actor_cli_exit0', 'actor_native_denials_empty', 'actor_guard_not_sticky',
    'actor_resources_equal', 'actor_quota_bounded',
)
_BE = ('SOURCE', 'FULL_SOURCE', 'F', 'FULL_F', 'RUNTIME', 'SYSTEM',
       'PREPARED', 'ROLE', 'APPROVAL')
_MAX_MEMBER_BYTES = 32 * 1024 * 1024  # Original private native per-file ceiling.


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(value, length=64):
    return type(value) is str and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _integer(value, low=0, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def _decode(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            _require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError('nonfinite_json')

    def finite_float(value):
        result = float(value)
        _require(math.isfinite(result), 'nonfinite_json')
        return result

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant,
                      parse_float=finite_float)


def _ordinary(path):
    path = Path(path)
    _require(path.is_absolute() and path.resolve() == path
             and not any(p.is_symlink() for p in (path, *path.parents)), 'nonordinary_path')
    return path


def _read(path, digest=None, size=None, mode=None):
    path = _ordinary(path)
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 <= before.st_size <= _MAX_MEMBER_BYTES, 'invalid_input_file')
    raw = path.read_bytes()
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
              'st_size', 'st_mtime_ns', 'st_ctime_ns')
    _require(all(getattr(before, k) == getattr(after, k) for k in fields), 'input_changed_during_read')
    _require(digest is None or hashlib.sha256(raw).hexdigest() == digest, 'file_seal_mismatch')
    _require(size is None or len(raw) == size, 'file_size_mismatch')
    _require(mode is None or stat.S_IMODE(before.st_mode) == mode, 'file_mode_mismatch')
    return raw


def _reference(value):
    _require(type(value) is dict and set(value) == {'path', 'sha256'}
             and type(value['path']) is str and _sha(value['sha256']), 'invalid_external_reference')
    return _read(Path(value['path']), value['sha256'])


def _lineage(value):
    return (type(value) is dict
            and set(value) == {'source_base_commit', 'backend_sha256', 'source_binding_sha256'}
            and _sha(value['source_base_commit'], 40) and _sha(value['backend_sha256'])
            and _sha(value['source_binding_sha256']))


def _cast_counts(raw, game, series, contexts, counts, unavailable):
    from ai.log_priors import _cast_context, _opponent_archetype

    pending, seen, total = None, set(), 0
    for line in raw:
        if line.startswith('AI TRACE '):
            pending = None
            trace = _decode(line.removeprefix('AI TRACE '))
            _require(type(trace) is dict, 'invalid_native_trace')
            if 'action_index' in trace:
                index = trace['action_index']
                _require(_integer(index, 0, game['ticks'] - 1) and index not in seen,
                         'invalid_or_duplicate_native_action')
                seen.add(index)
            context = _opponent_archetype(trace)
            known = any(_opponent_archetype({key: trace.get(key)}) is not None
                        for key in ('opponent_archetype', 'opp_archetype'))
            _require(context is not None or not known, 'conflicting_context_aliases')
            if context is None:
                unavailable['unknown_or_missing_context'] += 1
                continue
            pid, index, turn = trace.get('pid'), trace.get('action_index'), trace.get('turn')
            _require(_integer(pid, 1, 2) and _integer(index, 0, game['ticks'] - 1)
                     and _integer(turn, 1, game['turn'])
                     and type(trace.get('player_name')) is str and bool(trace['player_name'])
                     and type(trace.get('action')) is dict, 'missing_native_action_identity')
            opponent = series['seat_two'] if pid == 1 else series['seat_one']
            expected = _opponent_archetype({'opponent_archetype': contexts.get(opponent)})
            _require(expected is not None and context == expected, 'physical_context_mismatch')
            action = trace['action']
            if action.get('type') == 'cast_spell':
                if type(action.get('card_name')) is str and action['card_name'].strip():
                    pending = trace
                else:
                    unavailable['unconfirmed_cast_name'] += 1
        elif ' casts/activates ' in line:
            if pending is not None:
                actor, name = line.split(' casts/activates ', 1)
                name = name.strip().removesuffix('.')
                context = _cast_context(pending, actor.strip(), name)
                _require(context is not None and name == pending['action']['card_name'],
                         'conflicting_cast_announcement')
                counts[name.strip().lower()][context] += 1
                total += 1
            pending = None
    return total


def export_closed_matrixquota_training(*, role_root, contract, inventory, destination,
        measured_backend, expected_lineage, expected_contract_sha256,
        expected_inventory_sha256):
    """All-or-nothing intake. Caller anchors are mandatory; no SQL or game route."""
    _require(_lineage(expected_lineage) and _sha(expected_contract_sha256)
             and _sha(expected_inventory_sha256), 'missing_caller_approval')
    root, backend = _ordinary(role_root), _ordinary(measured_backend)
    contract, inventory, destination = map(_ordinary, (contract, inventory, destination))
    _require(root.is_dir() and backend.is_dir() and destination.parent.is_dir()
             and not destination.exists(), 'invalid_destination_or_roots')
    for protected in (root, backend.parent):
        _require(not destination.is_relative_to(protected) and not protected.is_relative_to(destination),
                 'destination_overlaps_inputs')
    contract_raw = _read(contract, expected_contract_sha256)
    inventory_raw = _read(inventory, expected_inventory_sha256)
    header, seal = _decode(contract_raw), _decode(inventory_raw)
    _require(type(header) is dict and set(header) == {'schema_version', 'layout', 'role_root',
        'measured_backend', 'lineage', 'prepared_export', 'parent_receipt'}
        and type(header['schema_version']) is int and header['schema_version'] == 1
        and header['layout'] == 'matrixquota-closed110-v1'
        and header['role_root'] == str(root) and header['measured_backend'] == str(backend)
        and _canonical(header['lineage']) == _canonical(expected_lineage), 'invalid_contract')
    _require(type(seal) is dict and set(seal) == {'schema_version', 'files'}
             and type(seal['schema_version']) is int and seal['schema_version'] == 1
             and type(seal['files']) is dict and bool(seal['files']), 'invalid_inventory')
    files = seal['files']
    for rel, row in files.items():
        path = PurePosixPath(rel)
        _require(type(rel) is str and bool(rel) and not path.is_absolute() and '..' not in path.parts
                 and path.as_posix() == rel and type(row) is dict
                 and set(row) == {'sha256', 'bytes', 'mode'} and _sha(row['sha256'])
                 and _integer(row['bytes'], 0, _MAX_MEMBER_BYTES)
                 and _integer(row['mode'], 0, 0o777), 'invalid_inventory_member')

    def member(rel):
        _require(rel in files, 'unsealed_member')
        row = files[rel]
        return _read(root / rel, row['sha256'], row['bytes'], row['mode'])

    def metadata(rel):
        value = _decode(member(rel))
        _require(type(value) is dict, 'invalid_metadata_object')
        return value

    acceptance = _decode(_reference(header['parent_receipt']))
    _require(type(acceptance) is dict and set(acceptance) == {'schema_version', 'kind', 'qualified',
        'physical_closed', 'cancelled', 'lineage', 'strict_qualifier_exit', 'strict_reader',
        'strict_report', 'summary_sha256'} and type(acceptance['schema_version']) is int
        and acceptance['schema_version'] == 1 and acceptance['kind'] == 'matrixquota-parent-acceptance-v1'
        and acceptance['qualified'] is True and acceptance['physical_closed'] is True
        and acceptance['cancelled'] is False and type(acceptance['strict_qualifier_exit']) is int
        and acceptance['strict_qualifier_exit'] == 0
        and _canonical(acceptance['lineage']) == _canonical(expected_lineage), 'parent_not_qualified_closed')
    _require(bool(_reference(acceptance['strict_reader'])), 'empty_strict_reader')
    strict = _decode(_reference(acceptance['strict_report']))
    _require(type(strict) is dict and set(strict) == {'schema_version', 'qualified', 'summary_sha256',
        'lineage', 'counts', 'errors'} and type(strict['schema_version']) is int
        and strict['schema_version'] == 1 and strict['qualified'] is True and strict['errors'] == []
        and _canonical(strict['lineage']) == _canonical(expected_lineage), 'strict_report_not_qualified')
    actor = metadata('actual/workspace/actor_receipt.json')
    terminal, release, unit = (metadata(p) for p in ('actual/TERMINAL.json', 'actual/RELEASE.json', 'UNIT_EXIT.json'))
    _require({'source_cli_exit', 'original_error', 'native_denials', 'guard_refusals', 'guard_sticky',
        'resources_equal', 'source_database_absent', 'configured_database_absent'} <= set(actor)
        and type(actor.get('source_cli_exit')) is int and actor['source_cli_exit'] == 0
        and actor.get('original_error') is None and actor.get('native_denials') == []
        and actor.get('guard_refusals') == [] and actor.get('guard_sticky') is False
        and actor.get('resources_equal') is True and actor.get('source_database_absent') is True
        and actor.get('configured_database_absent') is True, 'actor_not_qualified')
    _require(type(terminal.get('exit')) is int and terminal['exit'] == 0
        and terminal.get('runtime_envelope_qualified') is True
        and type(terminal.get('checks')) is dict
        and all(terminal['checks'].get(k) is True for k in _CHECKS)
        and all(v is True for v in terminal['checks'].values())
        and _canonical(terminal.get('actor_receipt')) == _canonical(actor), 'keeper_not_qualified')
    _require('failure' in release and release.get('physical_closed') is True and release.get('C_fd_closed') is True
        and release.get('runtime_envelope_qualified') is True and release.get('failure') is None
        and unit.get('SERVICE_RESULT') == 'success' and unit.get('EXIT_CODE') == 'exited'
        and unit.get('EXIT_STATUS') == '0'
        and unit.get('workload_members_absent_at_ExecStopPost') is True, 'closure_or_manager_not_qualified')
    for name in _BE:
        before, after = metadata(f'actual/{name}_BEFORE.json'), metadata(f'actual/{name}_AFTER.json')
        _require(bool(before) and _canonical(before) == _canonical(after), 'runtime_or_input_drift')
    for reference in (header['prepared_export'], header['parent_receipt'],
                      acceptance['strict_reader'], acceptance['strict_report']):
        protected = _ordinary(reference['path']).parent
        _require(not destination.is_relative_to(protected) and not protected.is_relative_to(destination),
                 'destination_overlaps_evidence')
    summary_raw = member('actual/workspace/summary.json')
    summary_hash = hashlib.sha256(summary_raw).hexdigest()
    _require(acceptance['summary_sha256'] == strict['summary_sha256'] == summary_hash, 'qualified_summary_mismatch')
    summary = _decode(summary_raw)
    binding = metadata('inputs/CURRENT_SOURCE_BINDING.json')
    role = metadata('inputs/ROLE.json')
    export = _decode(_reference(header['prepared_export']))

    from analytics.resource_budget import RESOURCE_LIMITS
    from analytics.replay_tools import normalize_log_line
    from scripts.derive_matchup_profiles import _admit
    from scripts import matchup_round_robin as rr

    _require(type(binding.get('backend_files')) is dict
        and all(binding['backend_files'].get(k) == v for k, v in _PRODUCERS.items()), 'unsupported_producer_layout')
    rows, series = _admit(summary, export, binding, backend, expected_lineage)
    manifest = summary['manifest']
    _require(len(rows) == 11 and len(series) == 110 and len(summary['pairs']) == 55
        and manifest['seeds'] == [1] and type(manifest['seeds'][0]) is int
        and manifest['difficulty'] == role.get('difficulty') == 'strong'
        and type(manifest['max_ticks']) is int and manifest['max_ticks'] == role.get('max_ticks') == 6000
        and manifest['sideboard_mode'] == role.get('sideboard_mode') == 'fixed_no_swaps'
        and _canonical(manifest['limits']) == _canonical(role.get('productive_limits')) == _canonical(dict(RESOURCE_LIMITS))
        and role.get('seed_tokens') == [1] and role.get('source') == str(backend.parent)
        and role.get('active_source') == str(backend)
        and role.get('source_commit') == expected_lineage['source_base_commit'], 'native_configuration_mismatch')
    schedule = rr.build_schedule(rows, [1])
    _require(all(_canonical({k: row.get(k) for k in expected}) == _canonical(expected)
        for row, expected in zip(series, schedule)), 'misindexed_schedule')
    contexts = manifest.get('effective_archetypes')
    _require(type(contexts) is dict and set(contexts) == {row['name'] for row in rows}, 'missing_physical_context_map')
    game_count = sum(len(row['games']) for row in series)
    _require(type(strict['counts']) is dict and set(strict['counts']) == {'series', 'pairs', 'games'}
        and all(type(strict['counts'][k]) is int for k in strict['counts'])
        and strict['counts'] == dict(series=110, pairs=55, games=game_count), 'strict_counts_mismatch')
    planned = [f'actual/workspace/private/series-{index:05d}/' + game['evidence']['reference']
               for index, row in enumerate(series) for game in row['games']]
    _require(len(planned) == len(set(planned)) and {p for p in files if p.startswith('actual/workspace/private/')} == set(planned),
             'unreferenced_or_missing_games')

    def capsule(rel, game):
        value = _decode(member(rel))
        _require(type(value) is dict and set(value) == {'schema_version', 'result', 'raw_log', 'raw_sha256'}
            and type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['raw_log']) is list and all(type(x) is str for x in value['raw_log'])
            and type(value['result']) is dict, 'invalid_capsule')
        raw = value['raw_log']
        encoded = json.dumps(raw, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        receipt, result = game['evidence'], value['result']
        _require(hashlib.sha256(encoded).hexdigest() == receipt['raw_sha256'] == value['raw_sha256']
            and len(encoded) == receipt['bytes'], 'raw_receipt_mismatch')
        _require(all(k in result for k in ('winner', 'turn', 'ticks', 'log', 'log_hash', 'timeout', 'starting_player'))
            and result['log'] == [normalize_log_line(line) for line in raw]
            and hashlib.sha256('\n'.join(result['log']).encode()).hexdigest() == result['log_hash'] == game['log_hash']
            and all(k in game and _canonical(game[k]) == _canonical(v) for k, v in result.items() if k != 'log'),
            'normalized_result_summary_mismatch')
        return raw

    # All metadata gates above precede any private capsule read or output creation.
    def inventory_members():
        result = set()
        for path in root.rglob('*'):
            _ordinary(path)
            _require(path.is_file() or path.is_dir(), 'nonordinary_inventory_member')
            if path.is_file():
                result.add(path.relative_to(root).as_posix())
        return result

    _require(inventory_members() == set(files), 'inexact_inventory')
    counts, unavailable, qualified_casts = defaultdict(Counter), Counter(), 0
    for index, row in enumerate(series):
        for game in row['games']:
            rel = f'actual/workspace/private/series-{index:05d}/' + game['evidence']['reference']
            qualified_casts += _cast_counts(capsule(rel, game), game, row, contexts, counts, unavailable)
    eligible = {}
    for card, values in sorted(counts.items()):
        retained = {context: n for context, n in sorted(values.items()) if n >= 3}
        if len(retained) >= 2:
            eligible[card] = retained
    _require(bool(eligible), 'insufficient_cast_context')
    for rel in files:
        member(rel)

    stage = Path(tempfile.mkdtemp(prefix='.matrixquota-export-', dir=destination.parent))
    reserved = published = False
    try:
        for index, row in enumerate(series):
            folder = stage / f'series-{index:05d}'
            folder.mkdir(mode=0o700)
            fd = os.open(folder / 'games.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                for game in row['games']:
                    rel = f'actual/workspace/private/series-{index:05d}/' + game['evidence']['reference']
                    handle.write(_canonical(dict(game=game['evidence']['reference'], seed=game['seed'],
                                                 log=capsule(rel, game))) + b'\n')
                handle.flush()
                os.fsync(handle.fileno())
        _require(_read(contract, expected_contract_sha256) == contract_raw
            and _read(inventory, expected_inventory_sha256) == inventory_raw, 'approval_changed')
        _reference(header['parent_receipt'])
        _reference(header['prepared_export'])
        _reference(acceptance['strict_reader'])
        _reference(acceptance['strict_report'])
        for rel in files:
            member(rel)
        _require(inventory_members() == set(files), 'inventory_changed')
        rr.verify_source_binding(binding, backend)
        # Reserve the absent final name first: never replace a pre-existing output.
        destination.mkdir(mode=0o700)
        reserved = True
        os.replace(stage, destination)
        published = True
        return dict(status='exported_private_training', games=game_count,
                    qualified_casts=qualified_casts, cast_context_eligible=True,
                    eligible_card_context_counts=eligible, context_unavailable=dict(sorted(unavailable.items())),
                    priors_saved=False, task33_complete=False)
    except BaseException:
        if published:
            shutil.rmtree(destination)
        elif reserved:
            destination.rmdir()
        if stage.exists():
            shutil.rmtree(stage)
        raise
