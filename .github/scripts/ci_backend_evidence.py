"""Observer-only pytest ledger and post-exit completeness audit."""
from collections import Counter
import builtins
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

try:
    from _pytest.subtests import SubtestReport
except ImportError as error:
    if error.name not in ('_pytest', '_pytest.subtests'):
        raise
    SubtestReport = None


_degraded = False
_progress_degraded = False
_evidence_root = None


def pytest_configure(config):
    global _evidence_root
    value = os.environ.get('MTG_CI_EVIDENCE')
    _evidence_root = Path(value).absolute() if value is not None else None


def evidence_directory():
    # Tests can intentionally change environment variables until fixture teardown.
    return _evidence_root if _evidence_root is not None else Path(os.environ['MTG_CI_EVIDENCE'])
EXCEPTION_CATEGORIES = frozenset({
    'AssertionError', 'AttributeError', 'FileNotFoundError', 'ImportError',
    'IndexError', 'KeyError', 'ModuleNotFoundError', 'NotImplementedError',
    'OSError', 'PermissionError', 'RuntimeError', 'TimeoutError', 'TypeError',
    'ValueError', 'ZeroDivisionError',
})
SQLITE_EXCEPTION_TYPES = {
    'SQLite' + name: getattr(sqlite3, name) for name in (
        'Error', 'DatabaseError', 'OperationalError', 'IntegrityError',
        'ProgrammingError', 'InterfaceError', 'DataError', 'InternalError',
        'NotSupportedError')
}
EXCEPTION_CATEGORIES |= frozenset(SQLITE_EXCEPTION_TYPES)
SQLITE_ERROR_CODES = {
    1: 'SQLITE_ERROR', 2: 'SQLITE_INTERNAL', 3: 'SQLITE_PERM', 4: 'SQLITE_ABORT',
    5: 'SQLITE_BUSY', 6: 'SQLITE_LOCKED', 7: 'SQLITE_NOMEM', 8: 'SQLITE_READONLY',
    9: 'SQLITE_INTERRUPT', 10: 'SQLITE_IOERR', 11: 'SQLITE_CORRUPT',
    12: 'SQLITE_NOTFOUND', 13: 'SQLITE_FULL', 14: 'SQLITE_CANTOPEN',
    15: 'SQLITE_PROTOCOL', 16: 'SQLITE_EMPTY', 17: 'SQLITE_SCHEMA',
    18: 'SQLITE_TOOBIG', 19: 'SQLITE_CONSTRAINT', 20: 'SQLITE_MISMATCH',
    21: 'SQLITE_MISUSE', 22: 'SQLITE_NOLFS', 23: 'SQLITE_AUTH',
    24: 'SQLITE_FORMAT', 25: 'SQLITE_RANGE', 26: 'SQLITE_NOTADB',
    27: 'SQLITE_NOTICE', 28: 'SQLITE_WARNING',
    517: 'SQLITE_BUSY_SNAPSHOT', 778: 'SQLITE_IOERR_WRITE',
    1032: 'SQLITE_READONLY_DBMOVED', 2067: 'SQLITE_CONSTRAINT_UNIQUE',
}


def sqlite_error_fields(code):
    valid = type(code) is int and 0 <= code <= 2147483647
    primary = code & 255 if valid else None
    known = valid and code in SQLITE_ERROR_CODES
    primary_known = primary in SQLITE_ERROR_CODES and primary <= 255
    return {
        'sqlite_errorcode': code if known else None,
        'sqlite_errorname': SQLITE_ERROR_CODES[code] if known else None,
        'sqlite_primary_errorcode': primary if primary_known else None,
        'sqlite_primary_errorname': SQLITE_ERROR_CODES[primary] if primary_known else None,
        'sqlite_code_status': ('known' if known else 'unlisted_extended'
                               if primary_known else 'unavailable'),
    }


def pytest_runtest_makereport(item, call):
    """Observe identities and locations only; never inspect exception messages."""
    if call.excinfo is None:
        return
    try:
        root = Path(os.environ['MTG_ISOLATED_TEST_ROOT']).resolve(strict=True)
        category = next((name for name, kind in SQLITE_EXCEPTION_TYPES.items()
                         if call.excinfo.type is kind and type(call.excinfo.value) is kind), None)
        if category is None:
            category = next((name for name in EXCEPTION_CATEGORIES
                             if call.excinfo.type is getattr(builtins, name, None)), 'Other')
        frames = []
        for entry in call.excinfo.traceback:
            path = Path(entry.path)
            if not path.is_absolute() or path.is_symlink():
                continue
            path = path.resolve(strict=True)
            if not path.is_relative_to(root) or path.suffix != '.py':
                continue
            relative = path.relative_to(root).as_posix()
            if not relative.startswith(('backend/', '.github/scripts/')):
                continue
            frames.append({'path': relative, 'line': entry.lineno + 1,
                           'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        value = {
            'nodeid': item.nodeid, 'phase': call.when,
            'signature': {'exception': category, 'frames': frames[-8:]},
        }
        if category in SQLITE_EXCEPTION_TYPES:
            value['signature'].update(sqlite_error_fields(
                vars(call.excinfo.value).get('sqlite_errorcode')))
        path = evidence_directory() / 'failure-signatures.jsonl'
        if any(component.is_symlink() for component in (*path.absolute().parents, path)):
            return
        with path.open('a') as stream:
            stream.write(json.dumps(value, sort_keys=True) + '\n')
    except Exception:
        # Missing diagnostic data must not change test execution or coverage.
        return


def pytest_runtest_logstart(nodeid, location):
    global _progress_degraded
    if os.environ.get('MTG_CI_PROGRESS') != '1' or _progress_degraded:
        return
    try:
        root = evidence_directory()
        path = root / 'started.jsonl'
        if any(component.is_symlink() for component in (*path.absolute().parents, path)) or not root.is_dir():
            raise OSError
        if path.exists() and not path.is_file():
            raise OSError
        with path.open('a') as stream:
            stream.write(json.dumps({'nodeid': nodeid}, sort_keys=True) + '\n')
    except (OSError, KeyError):
        # Diagnostic failure must never suppress the original completeness ledger.
        _progress_degraded = True
        print('CI_PROGRESS_START_DEGRADED', file=sys.stderr, flush=True)


def emit(filename, value):
    global _degraded
    if _degraded:
        return
    try:
        with (evidence_directory() / filename).open('a') as stream:
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
    subtest = SubtestReport is not None and type(report) is SubtestReport
    if hasattr(report, 'wasxfail'):
        row['wasxfail'] = True if subtest else str(report.wasxfail)
    if subtest:
        # Preserve every subreport without reading its private context or repr.
        emit('subtests.jsonl', row)
        return
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
        subtests = rows('subtests.jsonl')
        for row in subtests:
            if (type(row) is not dict or type(row.get('nodeid')) is not str
                    or row['nodeid'] not in collected or row.get('phase') != 'call'
                    or row.get('outcome') not in ('passed', 'failed', 'skipped')):
                raise ValueError('SUBTEST_ROW_INVALID')
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
        eligible = complete and exitcode == 0 and not any(
            row['outcome'] == 'failed' for row in reports + subtests)
        result = {'pytest_exit_code': exitcode, 'all_collected_completed': complete,
                  'ci_success_consistent': eligible, 'collected_count': len(collected),
                  'unique_count': len(set(collected)), 'phase_counts': dict(counts),
                  'missing_phases': missing, 'duplicate_phases': duplicates,
                  'unexpected_nodes': unexpected, 'collection_errors': collection_errors,
                  'skips_and_xfails_are_not_passes': True}
        if subtests:
            result['subtest_report_count'] = len(subtests)
            result['subtest_counts'] = dict(Counter(row['outcome'] for row in subtests))
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'all_collected_completed': False, 'ci_success_consistent': False,
                  'pytest_exit_code': exitcode, 'evidence_error': str(error)}
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['all_collected_completed'] and (exitcode != 0 or result['ci_success_consistent']) else 2


if __name__ == '__main__':
    raise SystemExit(audit(Path(sys.argv[1]), int(sys.argv[2])))
