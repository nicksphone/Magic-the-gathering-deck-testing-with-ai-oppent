"""Explicit, non-resumable 36-game pilot driver; never launches the full matrix."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from scripts.archetype_matrix_execution import build_pilot, validate_pilot
from scripts.archetype_matrix_plan import build_plan, digest

BACKEND = Path(__file__).resolve().parents[1]


def publish(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def worker_environment(backend):
    # Do not inherit app settings, credentials, witnesses, policy overrides or
    # Python path configuration. Fixed hash/thread settings apply to both phases.
    return {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
            'PYTHONPATH': str(backend), 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1',
            'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}


def boot_time():
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _stop_and_wait(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return process.wait()


def run_process(command, *, directory, name, environment, seconds, stop):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Positive remaining wall budget required')
    if stop.is_set():
        return {'started': False, 'waited': False, 'returncode': None, 'termination': 'cancelled'}
    started, offset = boot_time(), boot_time() - time.monotonic()
    process, termination = None, None
    with os.fdopen(os.open(directory / f'{name}.stdout', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as out:
        with os.fdopen(os.open(directory / f'{name}.stderr', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as err:
            try:
                process = subprocess.Popen(command, cwd=BACKEND, env=environment,
                    stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
                while process.poll() is None:
                    if abs((boot_time() - time.monotonic()) - offset) > 0.25:
                        stop.set()
                        termination = 'host_sleep'
                        break
                    if stop.is_set():
                        termination = 'cancelled'
                        break
                    remaining = seconds - (boot_time() - started)
                    if remaining <= 0:
                        termination = 'wall_limit'
                        break
                    try:
                        process.wait(timeout=min(0.05, remaining))
                    except subprocess.TimeoutExpired:
                        pass
                rc = _stop_and_wait(process) if termination else process.wait()
            except BaseException:
                if process is not None:
                    _stop_and_wait(process)
                raise
    return {'started': True, 'waited': True, 'returncode': rc, 'termination': termination}


def pilot_report(rows, *, scheduled):
    seconds = sorted(row['seconds'] for row in rows)
    complete = (len(rows) == scheduled and not any(row.get('run_invalid') for row in rows))
    statuses = {}
    for row in rows:
        statuses[row['status']] = statuses.get(row['status'], 0) + 1
    mean = sum(seconds)/len(seconds) if seconds else None
    p95 = seconds[max(0, math.ceil(.95*len(seconds))-1)] if seconds else None
    return {'scheduled': scheduled, 'accounted': len(rows), 'complete': complete,
            'statuses': statuses, 'accepts_matrix_or_strength': False,
            'decision_quality_scores_available': False,
            'mean_cell_seconds': mean, 'p50_cell_seconds': ((seconds[(len(seconds)-1)//2]+seconds[len(seconds)//2])/2 if seconds else None),
            'p95_cell_seconds': p95,
            'forecast_1440_games_seconds': 1440*mean/2 if complete else None,
            'p95_scenario_1440_games_seconds': 1440*p95/2 if complete else None,
            'trace_bytes': sum(row['trace_bytes'] for row in rows),
            'forecast_trace_bytes': sum(row['trace_bytes'] for row in rows)*40 if complete else None,
            'cpu_usage_available_cells': sum(row['cpu_seconds'] is not None for row in rows),
            'rss_available_cells': sum(row['peak_rss_bytes'] is not None for row in rows),
            'replay_time_available_cells': sum(row['replay_seconds'] is not None for row in rows)}


def runtime_identity():
    """Exact interpreter/version inventory, not wheel-byte provenance."""
    import platform
    import re
    if platform.system() != 'Linux' or sys.version_info[:3] != (3, 12, 3):
        raise ValueError('Use the declared Linux CPython 3.12.3 runtime')
    rows = re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)',
                      (BACKEND/'requirements-py312-linux.lock').read_text(), re.M)
    if len(rows) != 28:
        raise ValueError('Locked application dependency count changed')
    for name, version in rows:
        if importlib.metadata.version(name) != version:
            raise ValueError('Installed application versions differ from the lock')
    versions = sorted((distribution.metadata['Name'], distribution.version)
                      for distribution in importlib.metadata.distributions())
    return {'python': sys.version, 'executable_sha256': file_sha(sys.executable),
            'distributions': versions, 'application_packages': len(rows)}


def source_identity(revision):
    root = BACKEND.parent
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    if git('rev-parse', 'HEAD') != revision or git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Measure the exact clean committed revision, with outputs outside the checkout')
    if os.path.lexists(BACKEND/'mtg_lab.db'):
        raise ValueError('Use a disposable checkout without a source-local application database')
    files = git('ls-files', '-z', 'backend').split('\0')
    selected = [name for name in files if Path(name).suffix in ('.py', '.json', '.lock', '.svg')]
    hashes = {}
    for name in selected:
        path = root/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Tracked executable/data source must be regular')
        hashes[name] = file_sha(path)
    return {'root': str(root), 'revision': revision, 'files': hashes}


def verify_sources(source):
    root = Path(source['root'])
    for name, expected in source['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Source identity path escapes checkout')
        path = root/relative
        if path.is_symlink() or not path.is_file() or file_sha(path) != expected:
            raise ValueError('Measured source changed')


def _cell_result(cell, directory, started, stages, *, outcome=None, error=None, invalid=False):
    trace = directory/'trace.jsonl'
    values = [stage.get('result') or {} for stage in stages]
    cpu = [value.get('cpu_seconds') for value in values]
    rss = [value.get('peak_rss_bytes') for value in values]
    row = {'cell_id': cell['cell_id'], 'status': 'error' if error else (outcome or {}).get('status', 'error'),
           'winner': None if error else (outcome or {}).get('winner'),
           'termination': error or (outcome or {}).get('termination', 'worker_error'),
           'accepted_actions': (outcome or {}).get('accepted_actions'),
           'seconds': boot_time()-started,
           'cpu_seconds': sum(cpu) if cpu and all(type(x) in (int, float) for x in cpu) else None,
           'peak_rss_bytes': max(rss) if rss and all(type(x) is int for x in rss) else None,
           'replay_seconds': (values[-1].get('replay_seconds') if len(values) == 2 else None),
           'trace_sha256': file_sha(trace) if trace.exists() else None,
           'trace_bytes': trace.stat().st_size if trace.exists() else 0,
           'stages': stages, 'run_invalid': invalid, 'parity_checked': False}
    if error in ('wall_limit', 'cpu_limit', 'memory_limit'):
        row['status'] = 'timeout'
        row['winner'] = None
    if error == 'replay_divergence':
        row['status'] = 'replay_divergence'
        row['winner'] = None
    if not error and len(values) == 2:
        row['parity_checked'] = bool(values[-1].get('replay', {}).get('matched'))
        row['handler_boundaries'] = values[-1].get('handler_boundaries')
    return row


def run_cell(plan, cell, directory, *, cpu, source, runtime, stop):
    directory.mkdir(mode=0o700)
    started, stages, outcome, error = boot_time(), [], None, None
    host_offset = boot_time()-time.monotonic()
    environment = worker_environment(BACKEND)
    try:
        verify_sources(source)
        if digest(runtime_identity()) != digest(runtime):
            raise ValueError('Runtime versions changed')
        for mode in ('game', 'verify'):
            seconds = plan['policy']['max_seconds'] - (boot_time()-started)
            used = sum((stage.get('result') or {}).get('cpu_seconds', 0) for stage in stages)
            cpu_remaining = plan['policy']['max_cpu_seconds_per_game'] - used
            if seconds <= 0 or cpu_remaining < 1:
                error = 'wall_limit' if seconds <= 0 else 'cpu_limit'
                break
            request = {'plan': plan, 'cell': cell, 'mode': mode, 'cpu': cpu,
                'cpu_seconds': min(90, math.floor(cpu_remaining)), 'wall_seconds': seconds,
                'memory_bytes': plan['policy']['max_memory_bytes_per_worker'],
                'source': source, 'runtime_sha256': digest(runtime),
                'trace_sha256': file_sha(directory/'trace.jsonl') if mode == 'verify' else None,
                'accepted_actions': outcome['accepted_actions'] if outcome else None}
            request_path = directory/f'{mode}-request.json'
            publish(request_path, request)
            process = run_process([sys.executable, '-B', '-m', 'scripts.archetype_matrix_worker',
                    str(request_path)], directory=directory, name=mode,
                    environment=environment, seconds=seconds, stop=stop)
            stage = {'mode': mode, **process}
            stages.append(stage)
            result_path = directory/f'{mode}-result.json'
            if result_path.exists():
                try:
                    stage['result'] = json.loads(result_path.read_text())
                except (OSError, ValueError):
                    # A killed worker may leave a partial receipt. Its actual
                    # wait/signal result remains authoritative, not JSON parse.
                    stage['result_unreadable'] = True
            if process['termination']:
                error = process['termination']
                break
            rc = process['returncode']
            if rc != 0:
                if rc == -signal.SIGXCPU:
                    error = 'cpu_limit'
                elif rc == -signal.SIGALRM:
                    error = 'wall_limit'
                elif rc is not None and rc < 0:
                    error = 'worker_crash'
                    stop.set()
                else:
                    failure = (stage.get('result') or {}).get('error')
                    error = failure if failure in ('memory_limit', 'replay_divergence', 'worker_error') else 'worker_protocol'
                    if error == 'worker_protocol':
                        stop.set()
                break
            result = stage.get('result')
            if (process.get('waited') is not True or process.get('started') is not True
                    or type(result) is not dict or result.get('cell_id') != cell['cell_id']
                    or result.get('mode') != mode or result.get('source_sha256') != digest(source)
                    or result.get('runtime_sha256') != digest(runtime)
                    or type(result.get('cpu_seconds')) not in (int, float)
                    or not math.isfinite(result['cpu_seconds']) or result['cpu_seconds'] < 0
                    or type(result.get('peak_rss_bytes')) is not int or result['peak_rss_bytes'] < 0
                    or digest(result.get('controls')) != digest(
                        {'affinity': [cpu], 'memory_bytes': request['memory_bytes'],
                         'cpu_soft_seconds': request['cpu_seconds']})):
                error = 'worker_protocol'
                stop.set()
                break
            if mode == 'game':
                if result.get('trace_sha256') != file_sha(directory/'trace.jsonl'):
                    error = 'worker_protocol'
                    break
                outcome = result['outcome']
            elif (result.get('replay', {}).get('matched') is not True
                  or result['replay'].get('status') != outcome['status']):
                error = 'replay_divergence'
                break
        verify_sources(source)
        if digest(runtime_identity()) != digest(runtime):
            raise ValueError('Runtime versions changed')
    except Exception:
        stop.set()
        error = 'source_runtime_or_controller_error'
    if abs((boot_time()-time.monotonic())-host_offset) > 0.25:
        stop.set()
        error = 'host_sleep'
    if not error and boot_time()-started > plan['policy']['max_seconds']:
        error = 'wall_limit'
    if not error and sum((stage.get('result') or {}).get('cpu_seconds', 0) for stage in stages) > plan['policy']['max_cpu_seconds_per_game']:
        error = 'cpu_limit'
    invalid = stop.is_set() or error == 'host_sleep'
    row = _cell_result(cell, directory, started, stages, outcome=outcome, error=error, invalid=invalid)
    publish(directory/'cell-result.json', row)
    return row


def available_memory():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1])*1024
    raise ValueError('Host memory headroom cannot be observed')


def run_pilot(plan, directory):
    """Only a complete predeclared pilot is executable here; no resume path."""
    validate_pilot(plan)
    source, runtime = source_identity(plan['revision']), runtime_identity()
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) < 3:
        raise ValueError('Two available CPU affinity slots plus controller headroom are required')
    if available_memory() < 5*1024**3:
        raise ValueError('At least 5 GiB observed memory headroom is required for two workers/controller')
    # Per-process address-space/CPU limits are not physical/cgroup reservations.
    from scripts.archetype_matrix_game import admit_decks
    admit_decks(plan['matrix'])
    directory = Path(directory)
    if not directory.is_absolute() or directory.resolve() != directory or directory.is_relative_to(BACKEND.parent):
        raise ValueError('An absent canonical private output outside the source checkout is required')
    from persistence.job_retention import local_path
    directory = local_path(directory, existing=False)
    directory.mkdir(mode=0o700)
    publish(directory/'plan.json', plan)
    publish(directory/'source.json', source)
    publish(directory/'runtime.json', runtime)
    stop, rows, pending = threading.Event(), {}, {}
    old_handlers = {}
    def cancel(_signum, _frame):
        stop.set()
    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, cancel)
    started = boot_time()
    host_offset = boot_time()-time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            iterator = iter(enumerate(plan['cells']))
            available = cpus[:2]
            while True:
                if abs((boot_time()-time.monotonic())-host_offset) > .25:
                    stop.set()
                while available and not stop.is_set():
                    item = next(iterator, None)
                    if item is None:
                        break
                    index, cell = item
                    cpu = available.pop()
                    future = pool.submit(run_cell, plan, cell, directory/f'{index:03d}',
                                         cpu=cpu, source=source, runtime=runtime, stop=stop)
                    pending[future] = (index, cpu)
                if not pending:
                    break
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    index, cpu = pending.pop(future)
                    available.append(cpu)
                    try:
                        rows[index] = future.result()
                    except Exception:
                        stop.set()
            # A cancelled/crashed controller never resumes a partial prefix.
        ordered = [rows[index] for index in sorted(rows)]
        verify_sources(source)
        if digest(runtime_identity()) != digest(runtime):
            stop.set()
        report = pilot_report(ordered, scheduled=36)
        report.update(run_id=plan['run_id'], plan_sha256=digest(plan),
                      elapsed_seconds=boot_time()-started,
                      source_sha256=digest(source), runtime_sha256=digest(runtime))
        report['complete'] = (report['complete'] and not stop.is_set()
            and abs((boot_time()-time.monotonic())-host_offset) <= .25)
        if not report['complete']:
            report['forecast_1440_games_seconds'] = None
            report['p95_scenario_1440_games_seconds'] = None
            report['forecast_trace_bytes'] = None
        publish(directory/('PILOT-COMPLETE.json' if report['complete'] else 'PILOT-INCOMPLETE.json'), report)
        return report
    finally:
        stop.set()
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('run_id'); p.add_argument('output', type=Path)
    r = sub.add_parser('run')
    r.add_argument('plan', type=Path); r.add_argument('output', type=Path)
    r.add_argument('--execute-pilot', action='store_true', required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        revision = subprocess.check_output(['git', '-C', str(BACKEND.parent), 'rev-parse', 'HEAD'], text=True).strip()
        source_identity(revision)
        matrix = build_plan(revision, (BACKEND/'decks/builtin_decks.py').read_text())
        publish(args.output, build_pilot(matrix, args.run_id))
        return 0
    result = run_pilot(json.loads(args.plan.read_text()), args.output)
    # A complete pilot is diagnostic; errors/resource limits never accept RC.
    print(json.dumps({'complete': result['complete'], 'accounted': result['accounted'],
                      'statuses': result['statuses'], 'accepts_matrix_or_strength': False}))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    if sys.flags.optimize:
        raise SystemExit('Optimized execution is unsupported')
    raise SystemExit(main())
