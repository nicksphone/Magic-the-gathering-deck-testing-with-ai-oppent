"""One disposable pilot phase; resource limits precede rules/AI/app imports."""
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
from urllib.parse import unquote, urlsplit


def validate_limits(cpu, cpu_seconds, memory_bytes):
    if (type(cpu) is not int or cpu not in os.sched_getaffinity(0)
            or type(cpu_seconds) is not int or not 1 <= cpu_seconds <= 90
            or type(memory_bytes) is not int or memory_bytes != 2147483648):
        raise ValueError('Invalid worker resource limits')


def apply_limits(cpu, cpu_seconds, memory_bytes):
    validate_limits(cpu, cpu_seconds, memory_bytes)
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    # Linux accounts CPU in integral seconds; the hard second is a fail-safe
    # for an undelivered/default-ignored soft-limit signal, not extra budget.
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds+1))
    signal.signal(signal.SIGXCPU, signal.SIG_DFL)
    return {'affinity': sorted(os.sched_getaffinity(0)),
            'memory_bytes': resource.getrlimit(resource.RLIMIT_AS)[0],
            'cpu_soft_seconds': resource.getrlimit(resource.RLIMIT_CPU)[0]}


def install_guard(database=None):
    """Prevent accidental descendants/network and undeclared app DB fallback.

    Python audit hooks are cooperative diagnostics, not a hostile-code sandbox.
    Limits cover this process and its threads, not a delegated cgroup.
    """
    allowed = ({str(database), str(database.with_suffix('.before-capacity.db'))}
               if database is not None else set())
    def audit(event, args):
        if event in ('subprocess.Popen', 'os.fork', 'os.forkpty', 'os.posix_spawn',
                     'os.exec', 'os.system', 'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'):
            raise RuntimeError('Worker descendants/network are not admitted')
        if event == 'sqlite3.connect':
            value = str(args[0])
            path = unquote(urlsplit(value).path) if value.startswith('file:') else value
            if path not in allowed:
                raise RuntimeError('Worker database is not admitted')
    sys.addaudithook(audit)


def configure_cache(directory):
    """Keep optional token/media IO away from developer/source caches."""
    from card_data import placeholders, sync, token_images
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('Worker cache must not be an alias')
    directory.mkdir(mode=0o700, exist_ok=True)
    placeholders.CACHE_DIR = directory
    sync.CACHE_DIR = directory
    token_images.CACHE_DIR = directory
    token_images._INDEX_FILE = directory/'token-index.json'
    token_images._TOKEN_IMAGE_CACHE.clear()


def selected_steps(actions):
    return ({0, actions-1} | set(range(0, actions, 100))) if actions else set()


def main(argv=None):
    if sys.flags.optimize or not sys.flags.dont_write_bytecode:
        raise SystemExit('Run the worker without optimization and with -B')
    request_path = Path((sys.argv[1:] if argv is None else argv)[0]).resolve()
    request = json.loads(request_path.read_text())
    mode, directory = request['mode'], request_path.parent
    if mode not in ('game', 'verify'):
        raise ValueError('Unknown pilot worker phase')
    controls = apply_limits(request['cpu'], request['cpu_seconds'], request['memory_bytes'])
    seconds = request['wall_seconds']
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise ValueError('Invalid remaining cell wall budget')
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    os.umask(0o077)
    database = directory/'handler.db' if mode == 'verify' else None
    if database is not None:
        os.environ['MTG_DATABASE_PATH'] = str(database)
    install_guard(database)
    from scripts.archetype_matrix_execution import execution_matrix
    from scripts.archetype_matrix_game import TraceDivergence, admit_decks, cell_decks, play_game, replay_trace
    from scripts.archetype_matrix_pilot import file_sha, publish, runtime_identity, verify_sources
    from scripts.archetype_matrix_plan import digest
    result_path = directory/f'{mode}-result.json'
    rc, result = 0, {'mode': mode, 'cell_id': request['cell']['cell_id'], 'controls': controls}
    started = time.monotonic()
    try:
        matrix = execution_matrix(request['plan'])
        if (request['source']['revision'] != request['plan']['revision']
                or Path(request['source']['root']).resolve() != Path(__file__).resolve().parents[2]):
            raise ValueError('Worker source and plan revision/root differ')
        if request['cell'] not in request['plan']['cells']:
            raise ValueError('Cell is outside the predeclared pilot')
        verify_sources(request['source'])
        identity = digest(runtime_identity())
        if identity != request['runtime_sha256']:
            raise ValueError('Worker interpreter/package identity changed')
        result.update(source_sha256=digest(request['source']), runtime_sha256=identity)
        configure_cache(directory/'offline-cache')
        result['cache_policy'] = 'private_offline_per_cell'
        decks = cell_decks(admit_decks(matrix), request['cell'])
        trace = directory/'trace.jsonl'
        if mode == 'game':
            with trace.open('x', encoding='utf-8') as stream:
                def emit(row):
                    stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n')
                    stream.flush()
                result['outcome'] = play_game(*decks, seed=request['cell']['seed'],
                    game_id=request['cell']['cell_id'], policy=request['plan']['policy'], emit=emit)
                os.fsync(stream.fileno())
            result['trace_sha256'] = file_sha(trace)
        else:
            if file_sha(trace) != request['trace_sha256']:
                raise ValueError('Sealed trace changed before fresh-process replay')
            with trace.open() as stream:
                header = json.loads(next(stream))
            expected = {'deck_a': decks[0], 'deck_b': decks[1], 'seed': request['cell']['seed'],
                        'game_id': request['cell']['cell_id'], 'policy': request['plan']['policy']}
            if any(digest(header.get(key)) != digest(value) for key, value in expected.items()):
                raise ValueError('Trace root differs from predeclared cell')
            selected, checks = selected_steps(request['accepted_actions']), []
            from scripts.archetype_matrix_api_check import HandlerChecks
            with HandlerChecks(database) as handler:
                def boundary(first, row):
                    if row['step'] in selected:
                        checks.append(handler(first, row))
                with trace.open() as stream:
                    result['replay'] = replay_trace((json.loads(line) for line in stream), boundary=boundary)
            if {row['step'] for row in checks} != selected:
                raise ValueError('Selected handler boundaries were not all checked')
            if result['replay']['actions'] != request['accepted_actions']:
                raise ValueError('Accepted-action accounting changed')
            if file_sha(trace) != request['trace_sha256']:
                raise ValueError('Trace changed during replay')
            result['handler_boundaries'] = checks
            result['replay_seconds'] = time.monotonic()-started
        verify_sources(request['source'])
        if digest(runtime_identity()) != request['runtime_sha256']:
            raise ValueError('Runtime changed during phase')
    except TraceDivergence as exc:
        rc = 1
        result.update(error='replay_divergence', first_divergence={'step': exc.step, 'fields': exc.fields})
    except MemoryError:
        rc = 1
        result['error'] = 'memory_limit'
    except Exception as exc:
        rc = 1
        result.update(error='worker_error', exception_class=type(exc).__name__)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_seconds=usage.ru_utime+usage.ru_stime,
                  peak_rss_bytes=usage.ru_maxrss*1024, seconds=time.monotonic()-started)
    publish(result_path, result)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
