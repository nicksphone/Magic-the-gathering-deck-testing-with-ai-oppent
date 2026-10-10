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


class MetadataError(Exception):
    """Only fixed codes may cross the artifact boundary."""


def has_symlink_component(path):
    # Resolving or normalizing ".." first would erase preceding symlinks.
    path = path.absolute()
    return any(component.is_symlink() for component in (*reversed(path.parents), path))


def read_text(root, name, required=True):
    path = root / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise MetadataError('EVIDENCE_NOT_REGULAR')
    if not path.exists():
        if required:
            raise MetadataError('EVIDENCE_MISSING')
        return ''
    return path.read_text(encoding='utf-8')


def json_value(text):
    def invalid_constant(value):
        raise MetadataError('EVIDENCE_JSON_INVALID')
    try:
        return json.loads(text, parse_constant=invalid_constant)
    except ValueError:
        raise MetadataError('EVIDENCE_JSON_INVALID') from None


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


def empty_metadata():
    return {
        'schema_version': 1, 'source_commit': None, 'pytest_exit_code': None,
        'coverage': {'all_collected_completed': False, 'ci_success_consistent': False,
                     'collected_count': None, 'unique_count': None, 'phase_counts': {},
                     'missing_phases': [], 'duplicate_phases': [],
                     'unexpected_node_sha256': []},
        'collected_node_sha256': [], 'discovered_node_sha256': [],
        'deselected_node_sha256': [], 'deselection_row_count': None,
        'phases': [], 'failures': [], 'collection_errors': [], 'sessions': [],
        'unresolved_failure_count': None, 'rows_exported': False,
        'skips_and_xfails_are_not_passes': True, 'metadata_error_codes': [],
    }


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
        exit_text = read_text(evidence, 'pytest-exit-code.txt').strip()
        if not re.fullmatch(r'[0-9]{1,3}', exit_text) or int(exit_text) > 255:
            raise MetadataError('EXIT_CODE_INVALID')
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
        failures = [{'nodeid_sha256': node(row['nodeid']), 'phase': row['phase'],
                     'public_test': public.resolve(row['nodeid'])}
                    for row in phases if row['outcome'] == 'failed']
        errors = [{'nodeid_sha256': node(row['nodeid']), 'phase': 'collection',
                   'public_test': public.resolve(row['nodeid'])} for row in collection_errors]
        document.update(
            collected_node_sha256=collected_hashes, discovered_node_sha256=discovered_hashes,
            deselected_node_sha256=deselected_hashes, deselection_row_count=len(deselected),
            phases=safe_phases, failures=failures, collection_errors=errors, sessions=safe_sessions,
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
