"""Whole-module CI planning and strict, bounded public-artifact admission.

The pytest hooks observe collection only. They never select, reorder, skip or
change tests. Raw node identities stay in private runner scratch.
"""
from collections import Counter
from copy import deepcopy
import hashlib
from importlib.metadata import distributions
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import subprocess
import sys
import time


PLAN_BYTES = 16 * 1024 * 1024
WORKER_BYTES = 64 * 1024 * 1024
MAX_MODULES, MAX_NODES = 4096, 100000
MAX_PHASES, MAX_SUBTESTS = 300000, 100000
PLUGINS = ['ci_backend_evidence', 'ci_backend_snapshot_cleanup',
           'ci_backend_storage', 'ci_backend_shards']
BINDING_KEYS = {'run_id', 'attempt', 'commit', 'archive_sha256', 'lock_sha256'}
META_KEYS = {'schema_version', 'source_commit', 'pytest_exit_code', 'coverage',
             'collected_node_sha256', 'discovered_node_sha256',
             'deselected_node_sha256', 'deselection_row_count', 'phases', 'subtests',
             'failures', 'collection_errors', 'sessions', 'unresolved_failure_count',
             'rows_exported', 'skips_and_xfails_are_not_passes', 'metadata_error_codes'}
# These are existing sanitizer observations, not arbitrary pass-through fields.
# Successful shard transport retains the complete core audit, phases and subtests.
LOCAL_METADATA_KEYS = {'runtime_versions', 'timing', 'failure_diagnostics_status',
                       'interruption', 'interruption_diagnostics_status', 'partial_diagnostics',
                       'runner_closeout'}


class ContractError(ValueError):
    """A fixed code, never a private value, may cross the public boundary."""


def require(condition, code='SHARD_CONTRACT_REJECTED'):
    if not condition:
        raise ContractError(code)


def shape(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def integer(value, minimum=0, maximum=1000000):
    require(type(value) is int and minimum <= value <= maximum)
    return value


def runner_closeout_check(value, pytest_exit_code):
    """Admit a finite local observation without adding it to the shard core."""
    shape(value, {'schema_version', 'status', 'runner', 'diagnostics'})
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['status']) is str
            and value['status'] in ('complete', 'partial', 'degraded'))
    require(type(value['diagnostics']) is list and len(value['diagnostics']) <= 32)
    for row in value['diagnostics']:
        shape(row, {'role', 'finished', 'forced', 'wait_exit_code'})
        require(type(row['role']) is str and row['role'] in
                ('pytest', 'watcher', 'progress', 'sampler', 'pressure', 'sink', 'logger')
                and type(row['finished']) is bool and type(row['forced']) is bool)
        if row['finished']:
            integer(row['wait_exit_code'], 0, 255)
        else:
            require(row['wait_exit_code'] is None)
    runner = value['runner']
    if value['status'] == 'degraded':
        require(runner is None and value['diagnostics'] == [])
        return
    if runner is not None:
        codes = {'entry_exit_code', 'final_exit_code', 'pytest_exit_code',
                 'evidence_exit_code', 'audit_exit_code', 'pressure_exit_code',
                 'sink_exit_code', 'watcher_exit_code'}
        flags = {'diagnostic_failed', 'trap_changed_exit', 'closeout_complete'}
        groups = {'group_after_wait_quiet', 'group_final_quiet'}
        shape(runner, codes | flags | groups | {'schema_version', 'work_exit_stage'})
        require(type(runner['schema_version']) is int and runner['schema_version'] == 1
                and type(runner['work_exit_stage']) is str and runner['work_exit_stage'] in
                ('EARLY_OR_UNKNOWN', 'PYTEST', 'SINK', 'CONTROL', 'EVIDENCE', 'AUDIT'))
        for key in codes:
            if runner[key] is None and key not in ('entry_exit_code', 'final_exit_code'):
                continue
            integer(runner[key], 0, 255)
        for key in flags:
            require(type(runner[key]) is bool)
        for key in groups:
            require(type(runner[key]) is bool or runner[key] is None)
        require(runner['pytest_exit_code'] == pytest_exit_code
                and (pytest_exit_code is None or type(pytest_exit_code) is int)
                and runner['trap_changed_exit'] ==
                (runner['entry_exit_code'] != runner['final_exit_code']))
        if runner['closeout_complete']:
            require(all(runner[key] is not None for key in codes | groups))
    complete = (runner is not None and runner['closeout_complete']
                and all(row['finished'] for row in value['diagnostics']))
    require((value['status'] == 'complete') == bool(complete))


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def hashed(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def canonical_public_path(value, suffix=None):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_.\-/]+', value) is not None)
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value
            and all(part not in ('', '.', '..') for part in value.split('/')))
    if suffix is not None:
        require(path.suffix == suffix)
    return value


def binding_check(binding):
    shape(binding, BINDING_KEYS)
    for key in ('run_id', 'attempt'):
        require(type(binding[key]) is str and re.fullmatch('[1-9][0-9]{0,19}', binding[key]) is not None)
    require(type(binding['commit']) is str
            and re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', binding['commit']) is not None)
    digest(binding['archive_sha256']); digest(binding['lock_sha256'])


def context_check(context):
    shape(context, {'rootdir', 'config', 'importmode', 'plugins'})
    canonical_public_path(context['rootdir'])
    require(context['rootdir'] == 'backend')
    if context['config'] is not None:
        canonical_public_path(context['config'])
    require(context['importmode'] in ('prepend', 'append', 'importlib'))
    require(type(context['plugins']) is list and context['plugins'] == PLUGINS)


def lock_versions():
    text = (Path(__file__).resolve().parents[2] / 'backend/requirements-py312-linux.lock').read_text()
    result = {}
    for line in text.splitlines():
        if not line or line.startswith('#') or line in ('--require-hashes', '--only-binary=:all:'):
            continue
        match = re.fullmatch(r'([a-z0-9-]+)==([0-9]+(?:\.[0-9]+)+) --hash=sha256:[0-9a-f]{64}', line)
        require(match is not None, 'LOCK_FORMAT_REJECTED')
        name, version = match.groups()
        require(name not in result, 'LOCK_DUPLICATE')
        result[name] = version
    require(len(result) == 28, 'LOCK_CLOSURE_REJECTED')
    return result


def validate_runtime(identity, versions):
    shape(identity, {'implementation', 'python', 'system', 'machine', 'libc', 'packages'})
    require(identity['implementation'] == 'CPython' and identity['python'] == '3.12.3'
            and identity['system'] == 'Linux' and identity['machine'] == 'x86_64'
            and type(identity['libc']) is list and identity['libc'] == ['glibc', '2.39'])
    require(type(versions) is dict and len(versions) == 28
            and type(identity['packages']) is dict and set(identity['packages']) == set(versions))
    for name, version in identity['packages'].items():
        require(type(name) is str and re.fullmatch('[a-z0-9-]+', name) is not None
                and type(version) is str and version == versions[name])
    return deepcopy(identity)


def observed_runtime():
    packages = {}
    for dist in distributions():
        name = re.sub(r'[-_.]+', '-', dist.metadata['Name']).lower()
        require(name not in packages, 'RUNTIME_DUPLICATE')
        packages[name] = dist.version
    # Installer tooling is deliberately outside the application identity.
    packages.pop('pip', None)
    identity = dict(implementation=platform.python_implementation(), python=platform.python_version(),
                    system=platform.system(), machine=platform.machine(), libc=list(platform.libc_ver()),
                    packages=packages)
    return validate_runtime(identity, lock_versions())


def node_hashes(values):
    require(type(values) is list and len(values) <= MAX_NODES)
    for value in values:
        digest(value)
    return values


def make_plan(observation, binding, runtime, public_modules):
    shape(observation, {'mode', 'context', 'items', 'discovered', 'deselections',
                        'collection_errors', 'session_finished', 'pytest_exit'})
    binding_check(binding); context_check(observation['context'])
    validate_runtime(runtime, lock_versions())
    require(observation['mode'] == 'reference' and observation['session_finished'] is True
            and type(observation['pytest_exit']) is int and observation['pytest_exit'] == 0
            and observation['deselections'] == [] and observation['collection_errors'] == [])
    require(type(public_modules) is list and len(public_modules) == len(set(public_modules)))
    for path in public_modules:
        canonical_public_path(path, '.py')
    require(type(observation['items']) is list and 0 < len(observation['items']) <= MAX_NODES)
    require(type(observation['discovered']) is list)
    grouped, nodes = {}, []
    for item in observation['items']:
        shape(item, {'path', 'nodeid'})
        path = canonical_public_path(item['path'], '.py')
        require(path.startswith('backend/') and path in public_modules)
        node = item['nodeid']
        require(type(node) is str and 0 < len(node.encode('utf-8')) <= 1024 * 1024)
        # Bind each actual item.path to the node's path, not its Python __module__.
        relative = PurePosixPath(path).relative_to(observation['context']['rootdir']).as_posix()
        require(node.split('::', 1)[0] == relative)
        nodes.append(node)
        grouped.setdefault(path, []).append(hashlib.sha256(node.encode('utf-8')).hexdigest())
    require(len(grouped) <= MAX_MODULES and len(nodes) == len(set(nodes)))
    require(all(type(node) is str for node in observation['discovered'])
            and Counter(nodes) == Counter(observation['discovered']))
    plan = dict(schema_version=1, kind='collect-only-reference', binding=deepcopy(binding),
                context=deepcopy(observation['context']), runtime=deepcopy(runtime),
                modules=[dict(path=path, shard=index % 4, node_sha256=grouped[path])
                         for index, path in enumerate(sorted(grouped))],
                node_sha256=[hashlib.sha256(node.encode('utf-8')).hexdigest() for node in nodes])
    plan['plan_sha256'] = hashed(plan)
    validate_plan(plan, binding)
    return plan


def validate_plan(plan, binding):
    shape(plan, {'schema_version', 'kind', 'binding', 'context', 'runtime', 'modules',
                 'node_sha256', 'plan_sha256'})
    require(type(plan['schema_version']) is int and plan['schema_version'] == 1
            and plan['kind'] == 'collect-only-reference')
    binding_check(binding); binding_check(plan['binding'])
    require(encoded(plan['binding']) == encoded(binding))
    context_check(plan['context']); validate_runtime(plan['runtime'], lock_versions())
    digest(plan['plan_sha256'])
    require(plan['plan_sha256'] == hashed({k: v for k, v in plan.items() if k != 'plan_sha256'}))
    require(type(plan['modules']) is list and 0 < len(plan['modules']) <= MAX_MODULES)
    paths, nodes = [], []
    for index, module in enumerate(plan['modules']):
        shape(module, {'path', 'shard', 'node_sha256'})
        path = canonical_public_path(module['path'], '.py')
        require(path.startswith('backend/'))
        integer(module['shard'], 0, 3); require(module['shard'] == index % 4)
        require(bool(node_hashes(module['node_sha256'])))
        paths.append(path); nodes.extend(module['node_sha256'])
    reference = node_hashes(plan['node_sha256'])
    require(len(nodes) <= MAX_NODES and paths == sorted(set(paths)) and len(nodes) == len(set(nodes))
            and Counter(nodes) == Counter(reference) and len(reference) == len(set(reference)))
    require(len(encoded(plan)) <= PLAN_BYTES)
    return plan


def assigned_nodes(plan, shard):
    integer(shard, 0, 3)
    return [node for module in plan['modules'] if module['shard'] == shard
            for node in module['node_sha256']]


def metadata_check(meta, expected, commit):
    require(type(meta) is dict and META_KEYS <= set(meta)
            and not set(meta) - META_KEYS - LOCAL_METADATA_KEYS)
    if 'runner_closeout' in meta:
        runner_closeout_check(meta['runner_closeout'], meta['pytest_exit_code'])
    # Optional sanitizer observations never become an unrestricted transport.
    value = {key: deepcopy(meta[key]) for key in META_KEYS}
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and value['source_commit'] == commit)
    integer(value['pytest_exit_code'], 0, 255); require(value['pytest_exit_code'] == 0)
    for key in ('rows_exported', 'skips_and_xfails_are_not_passes'):
        require(value[key] is True)
    for key in ('failures', 'collection_errors', 'metadata_error_codes', 'deselected_node_sha256'):
        require(type(value[key]) is list and value[key] == [])
    for key in ('deselection_row_count', 'unresolved_failure_count'):
        integer(value[key]); require(value[key] == 0)
    nodes = node_hashes(value['collected_node_sha256'])
    require(nodes == expected and len(nodes) == len(set(nodes)) and bool(nodes))
    require(Counter(node_hashes(value['discovered_node_sha256'])) == Counter(nodes))
    require(value['sessions'] == [{'event': 'start'}, {'event': 'finish', 'exitstatus': 0}])
    require(type(value['sessions']) is list)
    shape(value['sessions'][0], {'event'}); shape(value['sessions'][1], {'event', 'exitstatus'})
    integer(value['sessions'][1]['exitstatus'], 0, 255)
    coverage = value['coverage']
    base = {'all_collected_completed', 'ci_success_consistent', 'collected_count', 'unique_count',
            'phase_counts', 'missing_phases', 'duplicate_phases', 'unexpected_node_sha256'}
    require(type(coverage) is dict and base <= set(coverage)
            and not set(coverage) - base - {'subtest_report_count', 'subtest_counts'})
    require(coverage['all_collected_completed'] is True and coverage['ci_success_consistent'] is True)
    for key in ('collected_count', 'unique_count'):
        integer(coverage[key], 1, MAX_NODES); require(coverage[key] == len(nodes))
    for key in ('missing_phases', 'duplicate_phases', 'unexpected_node_sha256'):
        require(type(coverage[key]) is list and coverage[key] == [])
    phases, counts = {}, Counter()
    require(type(value['phases']) is list and len(value['phases']) <= MAX_PHASES)
    node_set = set(nodes)
    for row in value['phases']:
        shape(row, {'nodeid_sha256', 'phase', 'outcome', 'xfail_marker'})
        require(row['nodeid_sha256'] in node_set and row['phase'] in ('setup', 'call', 'teardown')
                and row['outcome'] in ('passed', 'skipped') and type(row['xfail_marker']) is bool)
        key = (row['nodeid_sha256'], row['phase'])
        require(key not in phases)
        phases[key] = row['outcome']; counts[row['phase'] + '/' + row['outcome']] += 1
    for node in nodes:
        require((node, 'setup') in phases and (node, 'teardown') in phases)
        require((node, 'call') in phases if phases[node, 'setup'] == 'passed'
                else (node, 'call') not in phases)
    require(type(coverage['phase_counts']) is dict)
    for count in coverage['phase_counts'].values():
        integer(count, 0, MAX_PHASES)
    require(coverage['phase_counts'] == dict(counts))
    require(type(value['subtests']) is list and len(value['subtests']) <= MAX_SUBTESTS)
    subcounts = Counter()
    for index, row in enumerate(value['subtests']):
        shape(row, {'nodeid_sha256', 'subtest_index', 'phase', 'outcome', 'xfail_marker', 'duration_seconds'})
        integer(row['subtest_index'], 0, MAX_SUBTESTS)
        require(row['subtest_index'] == index and row['nodeid_sha256'] in node_set
                and row['phase'] == 'call' and row['outcome'] in ('passed', 'skipped')
                and type(row['xfail_marker']) is bool)
        seconds = row['duration_seconds']
        require(seconds is None or type(seconds) in (int, float)
                and math.isfinite(seconds) and 0 <= seconds <= 86400)
        subcounts[row['outcome']] += 1
    if 'subtest_report_count' in coverage or 'subtest_counts' in coverage:
        require({'subtest_report_count', 'subtest_counts'} <= set(coverage))
        integer(coverage['subtest_report_count'], 0, MAX_SUBTESTS)
        require(coverage['subtest_report_count'] == len(value['subtests']))
        require(type(coverage['subtest_counts']) is dict)
        for count in coverage['subtest_counts'].values():
            integer(count, 0, MAX_SUBTESTS)
        require(coverage['subtest_counts'] == dict(subcounts))
    return value


def worker_envelope(plan, shard, metadata, exits, runtime):
    validate_plan(plan, plan['binding']); integer(shard, 0, 3)
    shape(exits, {'runner', 'metadata'})
    for exitcode in exits.values():
        integer(exitcode, 0, 255); require(exitcode == 0)
    validate_runtime(runtime, lock_versions())
    require(encoded(runtime) == encoded(plan['runtime']))
    result = dict(schema_version=1, kind='serial-worker', binding=deepcopy(plan['binding']),
                  plan_sha256=plan['plan_sha256'], shard=shard, exits=deepcopy(exits),
                  runtime=deepcopy(runtime), metadata=metadata_check(
                      metadata, assigned_nodes(plan, shard), plan['binding']['commit']))
    require(len(encoded(result)) <= WORKER_BYTES)
    return result


def join(plan, workers, job_results):
    validate_plan(plan, plan['binding'])
    shape(job_results, {'reference', 'workers'})
    require(job_results == {'reference': 'success', 'workers': 'success'})
    require(type(workers) is list and len(workers) == 4)
    validated, seen, union = [], set(), Counter()
    for worker in workers:
        shape(worker, {'schema_version', 'kind', 'binding', 'plan_sha256', 'shard',
                       'exits', 'runtime', 'metadata'})
        require(type(worker['schema_version']) is int and worker['schema_version'] == 1
                and worker['kind'] == 'serial-worker')
        integer(worker['shard'], 0, 3)
        require(worker['shard'] not in seen and encoded(worker['binding']) == encoded(plan['binding'])
                and worker['plan_sha256'] == plan['plan_sha256'])
        seen.add(worker['shard'])
        admitted = worker_envelope(plan, worker['shard'], worker['metadata'], worker['exits'], worker['runtime'])
        require(encoded(admitted) == encoded(worker))
        validated.append(admitted)
        union.update(admitted['metadata']['collected_node_sha256'])
    require(seen == set(range(4)) and union == Counter(plan['node_sha256'])
            and all(count == 1 for count in union.values()))
    return dict(schema_version=1, kind='four-serial-shards', binding=deepcopy(plan['binding']),
                plan_sha256=plan['plan_sha256'], reference_node_sha256=plan['node_sha256'],
                workers=sorted(validated, key=lambda worker: worker['shard']))


def remaining_seconds(deadline, now):
    require(type(deadline) in (int, float) and type(now) in (int, float)
            and math.isfinite(deadline) and math.isfinite(now) and deadline > now,
            'WORK_DEADLINE_EXPIRED')
    return deadline - now


def identity_check(identity):
    shape(identity, {'pid', 'parent', 'start', 'pgrp', 'session'})
    for value in identity.values():
        integer(value, 1, 2**63 - 1)
    require(identity['pid'] == identity['pgrp'] == identity['session'])


def group_status(pgrp):
    """Presence only. No discovery/signals; EPERM is not absence."""
    integer(pgrp, 1, 2**63 - 1)
    try:
        os.killpg(pgrp, 0)
    except ProcessLookupError:
        return 'ABSENT'
    except OSError:
        return 'UNKNOWN'
    return 'PRESENT'


def observe_group_quiet(probe, now, pause):
    """Bounded natural drain, never permission to signal an unbound group."""
    started = now()
    require(type(started) in (int, float) and math.isfinite(started))
    until, empty = started + 2, 0
    while True:
        status = probe()
        if status not in ('ABSENT', 'PRESENT'):
            return dict(status='UNKNOWN_GROUP', signals=[])
        empty = empty + 1 if status == 'ABSENT' else 0
        if empty == 2:
            return dict(status='GROUP_ABSENT', signals=[])
        current = now()
        require(type(current) in (int, float) and math.isfinite(current))
        if current >= until:
            return dict(status='UNKNOWN_GROUP_PRESENT', signals=[])
        pause(min(0.1, until - current))


def watch_deadline(expected, deadline, probe, now, pause, send, group_probe=None):
    """Observe/signals only; actual wait/reap belongs to the spawning shell."""
    identity_check(expected)
    require(type(deadline) in (int, float) and math.isfinite(deadline))
    signals = []
    while True:
        actual = probe()
        if actual is None:
            if group_probe is None:
                # Historical fake-callback API: explicitly not group proof.
                return dict(status='LEADER_ABSENT', signals=signals)
            result = observe_group_quiet(group_probe, now, pause)
            result['signals'] = signals
            return result
        try:
            identity_check(actual)
        except ContractError:
            return dict(status='UNKNOWN_IDENTITY', signals=signals)
        if encoded(actual) != encoded(expected):
            return dict(status='UNKNOWN_IDENTITY', signals=signals)
        current = now()
        require(type(current) in (int, float) and math.isfinite(current))
        if current < deadline:
            pause(min(0.1, deadline - current)); continue
        if not signals:
            # This probe and the later KILL probe both revalidate the full identity.
            send(expected['pgrp'], 'INT'); signals.append('INT')
            kill_at = current + 15
        elif current >= kill_at and signals == ['INT']:
            send(expected['pgrp'], 'KILL'); signals.append('KILL')
            observe_until = current + 2
        elif signals == ['INT', 'KILL'] and current >= observe_until:
            return dict(status='UNKNOWN_UNREAPED', signals=signals)
        pause(0.1)


def regular_read(path, limit):
    path = Path(path).absolute()
    require(not any(part.is_symlink() for part in (*path.parents, path)), 'INPUT_PATH_REJECTED')
    info = path.stat()
    require(path.is_file() and info.st_nlink == 1 and info.st_size <= limit, 'INPUT_SIZE_REJECTED')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'INPUT_SIZE_REJECTED')
    def invalid(_):
        raise ContractError('JSON_NONFINITE')
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'JSON_DUPLICATE_KEY')
            result[key] = value
        return result
    return json.loads(raw, parse_constant=invalid, object_pairs_hook=pairs)


def bound_diagnostic_file(path):
    """Bound the unchanged sanitizer's exact JSON; never rewrite or certify it.

    Failure/partial documents are intentionally retained. The existing sanitizer
    remains the raw-to-public projection, not this availability/size check.
    """
    path = Path(path)
    require(path.name == 'backend-metadata.json', 'DIAGNOSTIC_FILENAME_REJECTED')
    value = regular_read(path, WORKER_BYTES)
    require(type(value) is dict and META_KEYS <= set(value)
            and not set(value) - META_KEYS - LOCAL_METADATA_KEYS,
            'DIAGNOSTIC_SCHEMA_REJECTED')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and type(value['coverage']) is dict
            and type(value['rows_exported']) is bool
            and value['skips_and_xfails_are_not_passes'] is True,
            'DIAGNOSTIC_SCHEMA_REJECTED')
    if 'runner_closeout' in value:
        runner_closeout_check(value['runner_closeout'], value['pytest_exit_code'])


def save(path, value, limit):
    raw = encoded(value) + b'\n'
    require(len(raw) <= limit, 'OUTPUT_SIZE_REJECTED')
    path = Path(path).absolute()
    require(not any(part.is_symlink() for part in path.parents), 'OUTPUT_PATH_REJECTED')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                                    '-C', str(root), *args], timeout=30,
                                   env=dict(PATH=os.defpath, LANG='C.UTF-8', GIT_CONFIG_NOSYSTEM='1',
                                            GIT_CONFIG_GLOBAL='/dev/null', GIT_OPTIONAL_LOCKS='0'))


def current_binding(root, archive_sha):
    binding = dict(run_id=os.environ['GITHUB_RUN_ID'], attempt=os.environ['GITHUB_RUN_ATTEMPT'],
                   commit=git(root, 'rev-parse', 'HEAD').decode().strip(), archive_sha256=archive_sha,
                   lock_sha256=hashlib.sha256((Path(root) / 'backend/requirements-py312-linux.lock').read_bytes()).hexdigest())
    require(binding['commit'] == os.environ['GITHUB_SHA'], 'COMMIT_MISMATCH')
    binding_check(binding)
    return binding


def proc_identity(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
    except FileNotFoundError:
        return None
    fields = text.rsplit(') ', 1)[1].split()
    if fields[0] in ('Z', 'X'):
        return None
    return dict(pid=pid, parent=int(fields[1]), pgrp=int(fields[2]),
                session=int(fields[3]), start=int(fields[19]))


# This observer is loaded only by explicit -p ci_backend_shards in hosted modes.
_observation = None
_source_root = None
_observation_path = None


def pytest_configure(config):
    global _observation, _source_root, _observation_path
    if os.environ.get('MTG_CI_SHARD_ROLE') not in ('reference', 'worker'):
        return
    _source_root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve(strict=True)
    _observation_path = Path(os.environ['MTG_CI_EVIDENCE']) / 'shard-observation.json'
    def relative(path):
        absolute = Path(path).absolute()
        require(absolute.resolve(strict=True) == absolute
                and not any(part.is_symlink() for part in (*absolute.parents, absolute)))
        return absolute.relative_to(_source_root).as_posix()
    for plugin in PLUGINS:
        require(config.pluginmanager.hasplugin(plugin), 'REQUIRED_PLUGIN_MISSING')
    _observation = dict(mode=os.environ['MTG_CI_SHARD_ROLE'],
                        context=dict(rootdir=relative(config.rootpath),
                                     config=relative(config.inipath) if config.inipath else None,
                                     importmode=config.getoption('importmode'), plugins=list(PLUGINS)),
                        items=[], discovered=[], deselections=[], collection_errors=[],
                        session_finished=False, pytest_exit=None)


def pytest_itemcollected(item):
    if _observation is not None:
        require(len(_observation['discovered']) < MAX_NODES, 'COLLECTION_BOUND_EXCEEDED')
        _observation['discovered'].append(item.nodeid)


def pytest_collection_finish(session):
    if _observation is None:
        return
    for item in session.items:
        path = Path(item.path).absolute()
        require(path.resolve(strict=True) == path and not any(part.is_symlink() for part in (*path.parents, path)))
        require(len(_observation['items']) < MAX_NODES, 'COLLECTION_BOUND_EXCEEDED')
        _observation['items'].append(dict(path=path.relative_to(_source_root).as_posix(), nodeid=item.nodeid))


def pytest_deselected(items):
    if _observation is not None:
        _observation['deselections'].append([item.nodeid for item in items])


def pytest_collectreport(report):
    if _observation is not None and report.failed:
        _observation['collection_errors'].append(True)


def pytest_sessionfinish(session, exitstatus):
    if _observation is not None:
        _observation.update(session_finished=True, pytest_exit=int(exitstatus))
        # Raw identities are private local evidence, never an artifact input.
        save(_observation_path, _observation, WORKER_BYTES)


def bundle(directory, name, limit):
    directory = Path(directory)
    require(directory.is_dir() and not any(part.is_symlink() for part in (*directory.absolute().parents, directory)))
    require(sorted(path.name for path in directory.iterdir()) == [name], 'ARTIFACT_MEMBER_SET_REJECTED')
    return regular_read(directory / name, limit)


def main(argv):
    mode, *args = argv
    if mode == 'platform':
        require((platform.python_implementation(), platform.python_version(), platform.system(),
                 platform.machine(), platform.libc_ver()) ==
                ('CPython', '3.12.3', 'Linux', 'x86_64', ('glibc', '2.39')), 'PLATFORM_REJECTED')
    elif mode == 'runtime':
        save(args[0], observed_runtime(), 65536)
    elif mode == 'remaining':
        deadline = float(os.environ['MTG_CI_WORK_DEADLINE'])
        print(remaining_seconds(deadline, time.monotonic()))
    elif mode == 'binding':
        save(args[2], current_binding(args[0], args[1]), 4096)
    elif mode == 'reference':
        source, evidence, binding_path, runtime_path, output = map(Path, args)
        tracked = git(source, 'ls-tree', '-rz', 'HEAD').split(b'\0')
        public = []
        for entry in tracked:
            if not entry:
                continue
            info, raw_path = entry.split(b'\t', 1)
            path = raw_path.decode('utf-8')
            if path.endswith('.py') and path.startswith('backend/'):
                require(info.split()[0] == b'100644' or info.split()[0] == b'100755')
                public.append(path)
        observation = regular_read(evidence / 'shard-observation.json', WORKER_BYTES)
        plan = make_plan(observation, regular_read(binding_path, 4096), regular_read(runtime_path, 65536), public)
        save(output, plan, PLAN_BYTES)
    elif mode == 'worker-argv':
        plan_path, binding_path, source, shard = args
        plan = regular_read(plan_path, PLAN_BYTES)
        validate_plan(plan, regular_read(binding_path, 4096))
        integer(int(shard), 0, 3)
        context = plan['context']
        flags = ['--rootdir', str(Path(source) / context['rootdir']), '--import-mode', context['importmode']]
        if context['config'] is not None:
            flags += ['-c', str(Path(source) / context['config'])]
        paths = [str(PurePosixPath(module['path']).relative_to('backend'))
                 for module in plan['modules'] if module['shard'] == int(shard)]
        require(bool(paths), 'EMPTY_SHARD')
        for value in flags + paths:
            sys.stdout.buffer.write(value.encode('utf-8') + b'\0')
    elif mode == 'worker-context':
        plan_path, observation_path, shard = args
        plan = regular_read(plan_path, PLAN_BYTES); validate_plan(plan, plan['binding'])
        obs = regular_read(observation_path, WORKER_BYTES)
        require(obs['mode'] == 'worker' and encoded(obs['context']) == encoded(plan['context']))
        require(obs['session_finished'] is True and type(obs['pytest_exit']) is int and obs['pytest_exit'] == 0
                and obs['deselections'] == [] and obs['collection_errors'] == [])
        require([hashlib.sha256(item['nodeid'].encode()).hexdigest() for item in obs['items']]
                == assigned_nodes(plan, int(shard)))
        expected_paths = [module['path'] for module in plan['modules'] if module['shard'] == int(shard)]
        require(list(dict.fromkeys(item['path'] for item in obs['items'])) == expected_paths)
    elif mode == 'validate-bundle':
        directory, binding_path = args
        plan = bundle(directory, 'plan.json', PLAN_BYTES)
        validate_plan(plan, regular_read(binding_path, 4096))
    elif mode == 'export-reference':
        evidence, output, runner_exit = args
        require(runner_exit == '0')
        plan = regular_read(Path(evidence) / 'plan.json', PLAN_BYTES)
        validate_plan(plan, plan['binding'])
        save(output, plan, PLAN_BYTES)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('plan_sha256=' + plan['plan_sha256'] + '\n')
    elif mode == 'export-worker':
        plan_path, evidence, metadata_path, shard, runner_exit, metadata_exit, output = args
        plan = regular_read(plan_path, PLAN_BYTES)
        value = worker_envelope(plan, int(shard), regular_read(metadata_path, WORKER_BYTES),
                                dict(runner=int(runner_exit), metadata=int(metadata_exit)),
                                regular_read(Path(evidence) / 'runtime-identity.json', 65536))
        save(output, value, WORKER_BYTES)
    elif mode == 'diagnostic-file':
        bound_diagnostic_file(Path(args[0]))
    elif mode == 'join':
        reference, worker_root, output = args
        plan = bundle(reference, 'plan.json', PLAN_BYTES)
        # Bind even a well-formed replay to this workflow invocation/checkout.
        require(plan['binding']['run_id'] == os.environ['GITHUB_RUN_ID']
                and plan['binding']['attempt'] == os.environ['GITHUB_RUN_ATTEMPT']
                and plan['binding']['commit'] == os.environ['GITHUB_SHA'])
        result = join(plan, [bundle(Path(worker_root) / str(index), 'worker.json', WORKER_BYTES)
                            for index in range(4)],
                      dict(reference=os.environ['REFERENCE_JOB_RESULT'], workers=os.environ['WORKERS_JOB_RESULT']))
        save(output, result, 4 * WORKER_BYTES + PLAN_BYTES)
    elif mode == 'watch':
        pid, parent, deadline, output = args
        pid, parent, deadline = int(pid), int(parent), float(deadline)
        setup_until = min(time.monotonic() + 2, deadline)
        expected = proc_identity(pid)
        while expected is not None and (expected['pgrp'] != pid or expected['session'] != pid) and time.monotonic() < setup_until:
            time.sleep(0.01); expected = proc_identity(pid)
        if expected is None:
            result = dict(status='UNKNOWN_UNREGISTERED', signals=[])
        else:
            identity_check(expected); require(expected['parent'] == parent, 'PYTEST_OWNER_MISMATCH')
            save(str(output) + '.identity.json', expected, 4096)
            def send(group, kind):
                os.killpg(group, getattr(signal, 'SIG' + kind))
            result = watch_deadline(expected, deadline, lambda: proc_identity(pid), time.monotonic, time.sleep, send,
                                    group_probe=lambda: group_status(expected['pgrp']))
        save(output, result, 4096)
        require(result['status'] == 'GROUP_ABSENT'
                and not result['signals'], 'DEADLINE_OR_IDENTITY_FAILURE')
    elif mode == 'group-quiet':
        identity_path, output = args
        expected = regular_read(identity_path, 4096); identity_check(expected)
        result = observe_group_quiet(lambda: group_status(expected['pgrp']), time.monotonic, time.sleep)
        save(output, result, 4096)
        require(result['status'] == 'GROUP_ABSENT', 'REGISTERED_GROUP_CLOSURE_UNKNOWN')
    elif mode == 'stop-pytest':
        identity_path = Path(args[0])
        expected = regular_read(identity_path, 4096); identity_check(expected)
        # Reuse the exact registered identity and finite 15+2 second watcher.
        result = watch_deadline(expected, time.monotonic(), lambda: proc_identity(expected['pid']),
                                time.monotonic, time.sleep,
                                lambda group, kind: os.killpg(group, getattr(signal, 'SIG' + kind)),
                                group_probe=lambda: group_status(expected['pgrp']))
        require(result['status'] == 'GROUP_ABSENT', 'PYTEST_CLOSURE_UNKNOWN')
    else:
        raise ContractError('UNKNOWN_MODE')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception:
        # No private arguments, paths, messages or tracebacks reach public logs.
        print('CI_SHARD_CONTRACT_FAILED', file=sys.stderr)
        raise SystemExit(2)
