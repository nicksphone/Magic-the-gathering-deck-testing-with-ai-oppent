"""Export allowlisted metadata, never raw logs, failure excerpts or parameters.

This is a separate artifact, not a sanitizer for existing raw diagnostics or
arbitrary future stdout. Unknown public identifiers remain null.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ERROR_CODES = frozenset({
    'EVIDENCE_NOT_REGULAR', 'EVIDENCE_MISSING', 'EVIDENCE_JSON_INVALID',
    'EVIDENCE_TYPE_INVALID', 'SOURCE_GIT_ERROR', 'SOURCE_COMMIT_INVALID',
    'SOURCE_COMMIT_MISMATCH', 'EXIT_CODE_INVALID', 'PHASE_INVALID',
    'OUTCOME_INVALID', 'SESSION_INVALID', 'AUDIT_ERROR', 'COVERAGE_MISMATCH',
    'COVERAGE_INCOMPLETE', 'SUCCESS_INCONSISTENT', 'EVIDENCE_IO_ERROR',
    'METADATA_INTERNAL_ERROR',
})
EXCEPTION_CATEGORIES = frozenset({
    'AssertionError', 'AttributeError', 'FileNotFoundError', 'ImportError',
    'IndexError', 'KeyError', 'ModuleNotFoundError', 'NotImplementedError',
    'OSError', 'PermissionError', 'RuntimeError', 'TimeoutError', 'TypeError',
    'ValueError', 'ZeroDivisionError',
})
SQLITE_EXCEPTION_CATEGORIES = frozenset({
    'SQLiteError', 'SQLiteDatabaseError', 'SQLiteOperationalError',
    'SQLiteIntegrityError', 'SQLiteProgrammingError', 'SQLiteInterfaceError',
    'SQLiteDataError', 'SQLiteInternalError', 'SQLiteNotSupportedError',
})
EXCEPTION_CATEGORIES |= SQLITE_EXCEPTION_CATEGORIES
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

RUNTIME_PACKAGES = (
    'annotated-doc', 'annotated-types', 'anyio', 'certifi', 'click', 'fastapi',
    'greenlet', 'h11', 'httpcore', 'httpx', 'idna', 'iniconfig',
    'opentelemetry-api', 'packaging', 'pluggy', 'pydantic-core', 'pydantic',
    'pygments', 'pytest', 'python-multipart', 'rapidfuzz', 'sniffio',
    'sqlalchemy', 'sqlmodel', 'starlette', 'typing-extensions',
    'typing-inspection', 'uvicorn',
)
RUNTIME_DIRECT_PACKAGES = (
    'fastapi', 'httpx', 'pydantic', 'pytest', 'python-multipart', 'rapidfuzz',
    'sqlmodel', 'starlette', 'uvicorn',
)


def sqlite_error_fields(value):
    code = value.get('sqlite_errorcode')
    known = type(code) is int and code in SQLITE_ERROR_CODES
    primary = code & 255 if known else None
    # Unlisted extended codes carry only an explicitly labelled allowlisted primary.
    if code is None and value.get('sqlite_code_status') == 'unlisted_extended':
        candidate = value.get('sqlite_primary_errorcode')
        if type(candidate) is int and candidate in SQLITE_ERROR_CODES and candidate <= 255:
            primary = candidate
    return {
        'sqlite_errorcode': code if known else None,
        'sqlite_errorname': SQLITE_ERROR_CODES[code] if known else None,
        'sqlite_primary_errorcode': primary,
        'sqlite_primary_errorname': SQLITE_ERROR_CODES.get(primary),
        'sqlite_code_status': ('known' if known else 'unlisted_extended'
                               if primary is not None else 'unavailable'),
    }


class MetadataError(Exception):
    """Only fixed codes may cross the artifact boundary."""


def has_symlink_component(path):
    # Resolving or normalizing ".." first would erase preceding symlinks.
    path = path.absolute()
    return any(component.is_symlink() for component in (*reversed(path.parents), path))


def read_text(root, name, required=True, *, max_bytes=None):
    path = root / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise MetadataError('EVIDENCE_NOT_REGULAR')
    if not path.exists():
        if required:
            raise MetadataError('EVIDENCE_MISSING')
        return ''
    if max_bytes is None:
        return path.read_text(encoding='utf-8')
    with path.open('rb') as stream:
        value = stream.read(max_bytes + 1)
    if len(value) > max_bytes:
        raise MetadataError('EVIDENCE_TYPE_INVALID')
    return value.decode('utf-8')


def json_value(text):
    def invalid_constant(value):
        raise MetadataError('EVIDENCE_JSON_INVALID')
    try:
        return json.loads(text, parse_constant=invalid_constant)
    except ValueError:
        raise MetadataError('EVIDENCE_JSON_INVALID') from None


def runtime_version_fields(root):
    """Observe existing pre-pytest snapshots, never import or certify packages."""
    packages = dict.fromkeys(RUNTIME_PACKAGES)
    python_version = None
    try:
        text = read_text(root, 'python-version.txt', required=False, max_bytes=128)
        match = re.fullmatch(r'Python ([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\n?', text)
        if match:
            python_version = match[1]
    except (MetadataError, OSError, UnicodeError):
        pass
    try:
        values = json_value(read_text(root, 'installed-packages.json', required=False,
                                      max_bytes=1024 * 1024))
        if type(values) is list and len(values) <= 1024:
            seen = set()
            for row in values:
                if type(row) is not dict or type(row.get('name')) is not str:
                    continue
                name = re.sub(r'[-_.]+', '-', row['name']).lower()
                if name not in packages:
                    continue
                if name in seen:
                    packages[name] = None
                    continue
                seen.add(name)
                version = row.get('version')
                # Local/build tags and arbitrary text must never cross this boundary.
                if (type(version) is str and len(version) <= 64 and re.fullmatch(
                        r'(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?'
                        r'(?:\.post[0-9]+)?(?:\.dev[0-9]+)?', version)):
                    packages[name] = version
    except (MetadataError, OSError, UnicodeError, RecursionError):
        pass
    observed = sum(value is not None for value in packages.values()) + (python_version is not None)
    return {'runtime_versions': {
        'observation': 'before_pytest',
        'status': 'available' if observed == 29 else 'degraded' if observed else 'unavailable',
        'python_version': python_version, 'packages': packages,
        'direct_packages': list(RUNTIME_DIRECT_PACKAGES),
    }}


def rows(root, name, required=False):
    result = [json_value(line) for line in read_text(root, name, required).splitlines()]
    if any(type(row) is not dict for row in result):
        raise MetadataError('EVIDENCE_TYPE_INVALID')
    return result


def node(value):
    if type(value) is not str or not value:
        raise MetadataError('EVIDENCE_TYPE_INVALID')
    # Hash the complete original UTF-8 identity, before parameter removal.
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def node_list(value):
    if type(value) is not list:
        raise MetadataError('EVIDENCE_TYPE_INVALID')
    return [node(item) for item in value]


def git(source, *args):
    result = subprocess.run(
        ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-C', str(source), *args],
        env={'PATH': os.defpath, 'GIT_CONFIG_NOSYSTEM': '1',
             'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_OPTIONAL_LOCKS': '0', 'LANG': 'C.UTF-8'},
        capture_output=True, check=False)
    if result.returncode:
        raise MetadataError('SOURCE_GIT_ERROR')
    return result.stdout.decode('utf-8')


class PublicDefinitions:
    """Read only committed public test ASTs, never import test/backend modules."""

    def __init__(self, source, commit):
        self.source = source
        self.commit = commit
        self.paths = set(git(source, 'ls-tree', '-rz', '--name-only', commit,
                             '--', 'backend/tests').split('\0'))
        self.cache = {}
        self.source_paths = set(git(source, 'ls-tree', '-rz', '--name-only', commit,
                                    '--', 'backend', '.github/scripts').split('\0'))
        self.source_cache = {}

    def diagnostic(self, value):
        if type(value) is not dict:
            return None
        category = value.get('exception')
        safe = {'exception': category if type(category) is str and
                category in EXCEPTION_CATEGORIES else 'Other', 'frames': []}
        if safe['exception'] in SQLITE_EXCEPTION_CATEGORIES:
            safe.update(sqlite_error_fields(value))
        frames = value.get('frames', [])
        if type(frames) is not list or len(frames) > 8:
            return safe
        for frame in frames:
            if type(frame) is not dict:
                continue
            path, line = frame.get('path'), frame.get('line')
            if (type(path) is not str or path not in self.source_paths or
                    not path.endswith('.py') or type(line) is not int or line < 1):
                continue
            if path not in self.source_cache:
                raw = git(self.source, 'show', f'{self.commit}:{path}').encode('utf-8')
                self.source_cache[path] = (hashlib.sha256(raw).hexdigest(), len(raw.splitlines()))
            digest, count = self.source_cache[path]
            if frame.get('source_sha256') == digest and line <= count:
                safe['frames'].append({'path': path, 'line': line, 'source_sha256': digest})
        return safe

    def resolve(self, nodeid):
        parts = nodeid.split('[', 1)[0].split('::')
        path = parts[0]
        if path.startswith('tests/'):
            path = 'backend/' + path
        if path not in self.paths or not path.endswith('.py') or len(parts) < 2:
            return None
        if path not in self.cache:
            tree = ast.parse(git(self.source, 'show', f'{self.commit}:{path}'))
            definitions = set()
            for definition in tree.body:
                if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.add((definition.name,))
                elif isinstance(definition, ast.ClassDef):
                    for method in definition.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            definitions.add((definition.name, method.name))
            self.cache[path] = definitions
        if tuple(parts[1:]) not in self.cache[path]:
            return None
        modules = path.removeprefix('backend/tests/').removesuffix('.py').split('/')
        names = modules + parts[1:]
        if any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name) for name in names):
            return None
        return '.'.join(names)

    def interruption_diagnostic(self, value):
        if (type(value) is not dict
                or set(value) != {'schema_version', 'hook', 'category', 'frames'}
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or type(value['hook']) is not str or value['hook'] != 'pytest_keyboard_interrupt'
                or type(value['category']) is not str or value['category'] not in {
                    'KeyboardInterrupt', 'PytestInterrupted', 'PytestExit', 'Other'}
                or type(value['frames']) is not list or len(value['frames']) > 2):
            return None
        for frame in value['frames']:
            if (type(frame) is not dict or set(frame) != {'path', 'line', 'source_sha256'}
                    or type(frame['path']) is not str
                    or type(frame['line']) is not int or frame['line'] < 1
                    or type(frame['source_sha256']) is not str
                    or not re.fullmatch('[0-9a-f]{64}', frame['source_sha256'])):
                return None
        verified = self.diagnostic({'exception': 'Other', 'frames': value['frames']})
        if verified['frames'] != value['frames']:
            return None
        return {'schema_version': 1, 'hook': 'pytest_keyboard_interrupt',
                'category': value['category'], 'frames': verified['frames']}


def empty_metadata():
    return {
        'schema_version': 1, 'source_commit': None, 'pytest_exit_code': None,
        'coverage': {'all_collected_completed': False, 'ci_success_consistent': False,
                     'collected_count': None, 'unique_count': None, 'phase_counts': {},
                     'missing_phases': [], 'duplicate_phases': [],
                     'unexpected_node_sha256': []},
        'collected_node_sha256': [], 'discovered_node_sha256': [],
        'deselected_node_sha256': [], 'deselection_row_count': None,
        'phases': [], 'subtests': [], 'failures': [], 'collection_errors': [], 'sessions': [],
        'unresolved_failure_count': None, 'rows_exported': False,
        'skips_and_xfails_are_not_passes': True, 'metadata_error_codes': [],
        'timing': {'recorded_phase_count': 0, 'total_recorded_seconds': None,
                   'slowest_phases': []},
    }


def phase_timing(phases, public):
    measured = []
    for row in phases:
        seconds = row.get('duration_seconds')
        if (type(seconds) not in (int, float) or not 0 <= seconds <= 86400
                or not math.isfinite(seconds)):
            continue
        measured.append((seconds, row))
    # Resolve committed public ASTs only for the bounded exported summary.
    slowest = sorted(measured, key=lambda row: row[0], reverse=True)[:20]
    return {'recorded_phase_count': len(measured),
            'total_recorded_seconds': math.fsum(seconds for seconds, _ in measured) if measured else None,
            'slowest_phases': [{'nodeid_sha256': node(row['nodeid']),
                               'public_test': public.resolve(row['nodeid']),
                               'phase': row['phase'], 'seconds': seconds}
                              for seconds, row in slowest]}


def audit_evidence(root, exitcode):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        spec = importlib.util.spec_from_file_location(
            'metadata_existing_auditor', Path(__file__).with_name('ci_backend_evidence.py'))
        auditor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auditor)
    stream = io.StringIO()
    # Raw node IDs and exception strings printed by the old audit stay internal.
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(io.StringIO()):
        status = auditor.audit(root, exitcode)
    return json_value(stream.getvalue()), status


def interruption_fields(evidence, public):
    try:
        path = evidence / 'interruption.jsonl'
        if not path.exists() and not path.is_symlink():
            return {}
        observations = rows(evidence, 'interruption.jsonl')
        if len(observations) == 1:
            signature = public.interruption_diagnostic(observations[0])
            if signature is not None:
                return {'interruption': signature}
    except (MetadataError, OSError, UnicodeError, KeyError, TypeError, ValueError):
        pass
    return {'interruption_diagnostics_status': 'degraded'}


def _completed_phase_diagnostics(evidence, source, commit):
    """Observe complete report rows only; never infer terminal test coverage."""
    try:
        public = PublicDefinitions(source, commit)
        path = evidence / 'phases.jsonl'
        if has_symlink_component(path) or (path.exists() and not path.is_file()):
            raise MetadataError('EVIDENCE_NOT_REGULAR')
        if not path.exists():
            raise MetadataError('EVIDENCE_MISSING')
        with path.open('r', encoding='utf-8', newline='') as stream:
            text = stream.read()
        if not text or not text.endswith('\n'):
            raise MetadataError('EVIDENCE_JSON_INVALID')
        phases = [json_value(line) for line in text.split('\n')[:-1]]
        safe_phases = []
        for row in phases:
            if type(row) is not dict:
                raise MetadataError('EVIDENCE_TYPE_INVALID')
            identity = node(row['nodeid'])
            if type(row['phase']) is not str or row['phase'] not in ('setup', 'call', 'teardown'):
                raise MetadataError('PHASE_INVALID')
            if type(row['outcome']) is not str or row['outcome'] not in ('passed', 'failed', 'skipped'):
                raise MetadataError('OUTCOME_INVALID')
            safe_phases.append({'nodeid_sha256': identity, 'phase': row['phase'],
                                'outcome': row['outcome'], 'xfail_marker': 'wasxfail' in row})
        failures = [{'nodeid_sha256': node(row['nodeid']), 'phase': row['phase'],
                     'public_test': public.resolve(row['nodeid'])}
                    for row in phases if row['outcome'] == 'failed']
        return {'status': 'available', 'nonfinal': True, 'phases': safe_phases,
                'failures': failures, 'timing': phase_timing(phases, public)}
    except MetadataError as error:
        candidate = error.args[0] if error.args else None
        code = candidate if type(candidate) is str and candidate in ERROR_CODES else 'METADATA_INTERNAL_ERROR'
    except (OSError, UnicodeError):
        code = 'EVIDENCE_IO_ERROR'
    except (KeyError, TypeError, ValueError, SyntaxError):
        code = 'EVIDENCE_TYPE_INVALID'
    except Exception:
        code = 'METADATA_INTERNAL_ERROR'
    return {'status': 'unavailable', 'nonfinal': True, 'error_codes': [code]}


def build_metadata(evidence, source):
    document = empty_metadata()
    try:
        evidence, source = Path(evidence), Path(source)
        if has_symlink_component(evidence) or not evidence.is_dir():
            raise MetadataError('EVIDENCE_NOT_REGULAR')
        commit = read_text(evidence, 'source-head.txt').strip()
        if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit):
            raise MetadataError('SOURCE_COMMIT_INVALID')
        if commit != git(source, 'rev-parse', 'HEAD').strip():
            raise MetadataError('SOURCE_COMMIT_MISMATCH')
        document['source_commit'] = commit
        document.update(runtime_version_fields(evidence))
        try:
            exit_text = read_text(evidence, 'pytest-exit-code.txt').strip()
            if not re.fullmatch(r'[0-9]{1,3}', exit_text) or int(exit_text) > 255:
                raise MetadataError('EXIT_CODE_INVALID')
        except MetadataError as error:
            if error.args not in (('EVIDENCE_MISSING',), ('EXIT_CODE_INVALID',)):
                raise
            document['partial_diagnostics'] = _completed_phase_diagnostics(evidence, source, commit)
            raise
        exitcode = int(exit_text)
        document['pytest_exit_code'] = exitcode

        collected = json_value(read_text(evidence, 'collected.json'))
        if type(collected) is not dict:
            raise MetadataError('EVIDENCE_TYPE_INVALID')
        collected_hashes = node_list(collected['nodeids'])
        discovered = rows(evidence, 'discovered.jsonl')
        discovered_hashes = [node(row['nodeid']) for row in discovered]
        deselected = rows(evidence, 'deselected.jsonl')
        deselected_hashes = [identity for row in deselected for identity in node_list(row['nodeids'])]
        phases = rows(evidence, 'phases.jsonl')
        safe_phases = []
        for row in phases:
            identity = node(row['nodeid'])
            if row['phase'] not in ('setup', 'call', 'teardown'):
                raise MetadataError('PHASE_INVALID')
            if row['outcome'] not in ('passed', 'failed', 'skipped'):
                raise MetadataError('OUTCOME_INVALID')
            safe_phases.append({'nodeid_sha256': identity, 'phase': row['phase'],
                                'outcome': row['outcome'], 'xfail_marker': 'wasxfail' in row})
        subtests = rows(evidence, 'subtests.jsonl')
        safe_subtests = []
        for index, row in enumerate(subtests):
            identity = node(row['nodeid'])
            if row['phase'] != 'call':
                raise MetadataError('PHASE_INVALID')
            if row['outcome'] not in ('passed', 'failed', 'skipped'):
                raise MetadataError('OUTCOME_INVALID')
            seconds = row.get('duration_seconds')
            valid_seconds = (type(seconds) in (int, float) and 0 <= seconds <= 86400
                             and math.isfinite(seconds))
            safe_subtests.append({'nodeid_sha256': identity, 'subtest_index': index,
                                  'phase': 'call', 'outcome': row['outcome'],
                                  'xfail_marker': 'wasxfail' in row,
                                  'duration_seconds': seconds if valid_seconds else None})
        collection_errors = rows(evidence, 'collection-errors.jsonl')
        for row in collection_errors:
            node(row['nodeid'])
        sessions = rows(evidence, 'session.jsonl', required=True)
        safe_sessions = []
        for row in sessions:
            if row['event'] not in ('start', 'finish'):
                raise MetadataError('SESSION_INVALID')
            safe = {'event': row['event']}
            if row['event'] == 'finish':
                if type(row['exitstatus']) is not int or not 0 <= row['exitstatus'] <= 255:
                    raise MetadataError('SESSION_INVALID')
                safe['exitstatus'] = row['exitstatus']
            safe_sessions.append(safe)
        recorded = json_value(read_text(evidence, 'coverage.json'))
        audited, audit_status = audit_evidence(evidence, exitcode)
        if 'evidence_error' in audited:
            raise MetadataError('AUDIT_ERROR')

        public = PublicDefinitions(source, commit)
        document.update(interruption_fields(evidence, public))
        document['timing'] = phase_timing(phases, public)
        failures = [{'nodeid_sha256': node(row['nodeid']), 'phase': row['phase'],
                     'public_test': public.resolve(row['nodeid'])}
                    for row in phases if row['outcome'] == 'failed']
        failures.extend({'nodeid_sha256': node(row['nodeid']), 'phase': 'call',
                         'public_test': public.resolve(row['nodeid']),
                         'report_kind': 'subtest', 'subtest_index': index}
                        for index, row in enumerate(subtests) if row['outcome'] == 'failed')
        signatures = {}
        document['failure_diagnostics_status'] = 'not_recorded'
        try:
            signature_rows = rows(evidence, 'failure-signatures.jsonl')
            if signature_rows:
                document['failure_diagnostics_status'] = 'complete'
        except (MetadataError, OSError, UnicodeError):
            signature_rows = []
            document['failure_diagnostics_status'] = 'degraded'
        for row in signature_rows:
            try:
                if row.get('phase') not in ('setup', 'call', 'teardown'):
                    raise MetadataError('PHASE_INVALID')
                key = (node(row['nodeid']), row['phase'])
                if key in signatures:
                    # Ambiguous optional observations have no selected winner.
                    signatures[key] = None
                    document['failure_diagnostics_status'] = 'degraded'
                    continue
                signatures[key] = None
                signatures[key] = public.diagnostic(row.get('signature'))
                if signatures[key] is None:
                    document['failure_diagnostics_status'] = 'degraded'
            except (MetadataError, OSError, UnicodeError, KeyError, TypeError, ValueError):
                document['failure_diagnostics_status'] = 'degraded'
        for row in failures:
            signature = signatures.get((row['nodeid_sha256'], row['phase']))
            if signature is not None:
                row['diagnostic'] = signature
        errors = [{'nodeid_sha256': node(row['nodeid']), 'phase': 'collection',
                   'public_test': public.resolve(row['nodeid'])} for row in collection_errors]
        document.update(
            collected_node_sha256=collected_hashes, discovered_node_sha256=discovered_hashes,
            deselected_node_sha256=deselected_hashes, deselection_row_count=len(deselected),
            phases=safe_phases, subtests=safe_subtests, failures=failures,
            collection_errors=errors, sessions=safe_sessions,
            unresolved_failure_count=sum(row['public_test'] is None for row in failures + errors),
            rows_exported=True)
        document['coverage'] = {
            'all_collected_completed': audited['all_collected_completed'],
            'ci_success_consistent': audited['ci_success_consistent'],
            'collected_count': audited['collected_count'], 'unique_count': audited['unique_count'],
            'phase_counts': audited['phase_counts'],
            'missing_phases': [{'nodeid_sha256': node(identity), 'phase': phase}
                               for identity, phase in audited['missing_phases']],
            'duplicate_phases': [{'nodeid_sha256': node(identity), 'phase': phase}
                                 for identity, phase in audited['duplicate_phases']],
            'unexpected_node_sha256': [node(identity) for identity in audited['unexpected_nodes']],
        }
        if subtests:
            document['coverage']['subtest_report_count'] = audited['subtest_report_count']
            document['coverage']['subtest_counts'] = audited['subtest_counts']
        # Python equality alone treats true and 1 as equal; the ledger types matter.
        if json.dumps(recorded, sort_keys=True) != json.dumps(audited, sort_keys=True):
            document['metadata_error_codes'].append('COVERAGE_MISMATCH')
            document['coverage']['all_collected_completed'] = False
            document['coverage']['ci_success_consistent'] = False
        if not audited['all_collected_completed']:
            document['metadata_error_codes'].append('COVERAGE_INCOMPLETE')
        if exitcode == 0 and not audited['ci_success_consistent']:
            document['metadata_error_codes'].append('SUCCESS_INCONSISTENT')
        return document, 2 if audit_status or document['metadata_error_codes'] else 0
    except MetadataError as error:
        candidate = error.args[0] if error.args else None
        code = candidate if type(candidate) is str and candidate in ERROR_CODES else 'METADATA_INTERNAL_ERROR'
    except (OSError, UnicodeError):
        code = 'EVIDENCE_IO_ERROR'
    except (KeyError, TypeError, ValueError, SyntaxError):
        code = 'EVIDENCE_TYPE_INVALID'
    except Exception:
        code = 'METADATA_INTERNAL_ERROR'
    document['coverage']['all_collected_completed'] = False
    document['coverage']['ci_success_consistent'] = False
    document['metadata_error_codes'] = [code]
    return document, 2


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if len(args) != 3:
        print('CI_BACKEND_METADATA_ARGUMENT_ERROR', file=sys.stderr)
        return 2
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            document, status = build_metadata(args[0], args[1])
    except Exception:
        document = empty_metadata()
        document['metadata_error_codes'] = ['METADATA_INTERNAL_ERROR']
        status = 2
    temporary = None
    try:
        output = Path(args[2])
        if has_symlink_component(output) or output.exists():
            raise OSError
        descriptor, temporary = tempfile.mkstemp(prefix='.backend-metadata-', suffix='.tmp',
                                               dir=output.parent)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(document, sort_keys=True, indent=2) + '\n')
        os.replace(temporary, output)
        temporary = None
    except Exception:
        print('CI_BACKEND_METADATA_OUTPUT_ERROR', file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            # Cleanup failures must not replace the fixed error with a traceback.
            with contextlib.suppress(OSError):
                Path(temporary).unlink(missing_ok=True)
    if status:
        print('CI_BACKEND_METADATA_FAILED', file=sys.stderr)
    else:
        print('CI_BACKEND_METADATA_WRITTEN')
    return status


if __name__ == '__main__':
    raise SystemExit(main())
