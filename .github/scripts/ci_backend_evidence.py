"""Observer-only pytest ledger and post-exit completeness audit."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys


_degraded = False


def emit(filename, value):
    global _degraded
    if _degraded:
        return
    try:
        with (Path(os.environ['MTG_CI_EVIDENCE']) / filename).open('a') as stream:
            stream.write(json.dumps(value, sort_keys=True) + '\n')
    except OSError as error:
        _degraded = True
        print(f'CI_EVIDENCE_WRITE_ERROR {filename}: {error}', file=sys.stderr, flush=True)


def pytest_sessionstart(session):
    emit('session.jsonl', {'event': 'start'})


def pytest_itemcollected(item):
    emit('discovered.jsonl', {'nodeid': item.nodeid})


def pytest_collection_finish(session):
    emit('collected.json', {'nodeids': [item.nodeid for item in session.items]})


def pytest_deselected(items):
    emit('deselected.jsonl', {'nodeids': [item.nodeid for item in items]})


def failure(report, phase):
    text = str(report.longrepr)
    emit('failures.jsonl', {
        'nodeid': report.nodeid, 'phase': phase, 'outcome': report.outcome,
        'excerpt': text[:4096], 'truncated': len(text) > 4096,
        'longrepr_sha256': hashlib.sha256(text.encode()).hexdigest(),
    })


def pytest_collectreport(report):
    if report.failed:
        emit('collection-errors.jsonl', {'nodeid': report.nodeid})
        failure(report, 'collection')


def pytest_runtest_logreport(report):
    row = {'nodeid': report.nodeid, 'phase': report.when,
           'outcome': report.outcome, 'duration_seconds': report.duration}
    if hasattr(report, 'wasxfail'):
        row['wasxfail'] = str(report.wasxfail)
    emit('phases.jsonl', row)
    if report.failed:
        failure(report, report.when)


def pytest_sessionfinish(session, exitstatus):
    emit('session.jsonl', {'event': 'finish', 'exitstatus': int(exitstatus)})
    if _degraded:
        print('CI_EVIDENCE_DEGRADED=1', file=sys.stderr, flush=True)


def audit(root, exitcode):
    def rows(filename):
        path = root / filename
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f'Evidence is not a regular file: {filename}')
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    try:
        collection = root / 'collected.json'
        if collection.is_symlink() or not collection.is_file():
            raise ValueError('Evidence is not a regular file: collected.json')
        collected = json.loads(collection.read_text())['nodeids']
        discovered = [row['nodeid'] for row in rows('discovered.jsonl')]
        reports = rows('phases.jsonl')
        phases = {}
        duplicates = []
        for row in reports:
            key = (row['nodeid'], row['phase'])
            if key in phases:
                duplicates.append(list(key))
            phases[key] = row['outcome']
        missing = []
        for nodeid in collected:
            required = ['setup', 'teardown']
            if phases.get((nodeid, 'setup')) == 'passed':
                required.append('call')
            missing.extend([nodeid, phase] for phase in required if (nodeid, phase) not in phases)
        unexpected = sorted({nodeid for nodeid, phase in phases} - set(collected))
        sessions = rows('session.jsonl')
        collection_errors = rows('collection-errors.jsonl')
        complete = bool(collected) and not (
            len(collected) != len(set(collected)) or Counter(discovered) != Counter(collected)
            or duplicates or missing or unexpected or collection_errors or rows('deselected.jsonl')
            or not sessions or sessions[-1].get('event') != 'finish'
            or sessions[-1].get('exitstatus') != exitcode
        )
        counts = Counter(f"{row['phase']}/{row['outcome']}" for row in reports)
        eligible = complete and exitcode == 0 and not any(row['outcome'] == 'failed' for row in reports)
        result = {'pytest_exit_code': exitcode, 'all_collected_completed': complete,
                  'ci_success_consistent': eligible, 'collected_count': len(collected),
                  'unique_count': len(set(collected)), 'phase_counts': dict(counts),
                  'missing_phases': missing, 'duplicate_phases': duplicates,
                  'unexpected_nodes': unexpected, 'collection_errors': collection_errors,
                  'skips_and_xfails_are_not_passes': True}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'all_collected_completed': False, 'ci_success_consistent': False,
                  'pytest_exit_code': exitcode, 'evidence_error': str(error)}
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['all_collected_completed'] and (exitcode != 0 or result['ci_success_consistent']) else 2


if __name__ == '__main__':
    raise SystemExit(audit(Path(sys.argv[1]), int(sys.argv[2])))
