"""Synthetic SQLite errors only: no backend, database allocation or private input."""
import sys


def deny_io(event, args):
    if event.startswith(('sqlite3.', 'socket.')):
        raise RuntimeError('SQL_SOCKET_DENIED')


sys.addaudithook(deny_io)

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_ci_failure_signatures as existing_signatures

SCRIPTS = Path(__file__).resolve().parents[1]
SECRET = 'SYNTHETIC_SQLITE_MESSAGE_NOT_PUBLIC_6421'
SQLITE_CLASSES = ('Error', 'DatabaseError', 'OperationalError', 'IntegrityError',
                  'ProgrammingError', 'InterfaceError', 'DataError',
                  'InternalError', 'NotSupportedError')
FIELDS = ('sqlite_errorcode', 'sqlite_errorname',
          'sqlite_primary_errorcode', 'sqlite_primary_errorname')


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SQLiteDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.capture = load('ci_backend_evidence')
        self.metadata = load('ci_backend_metadata')
        self.public = object.__new__(self.metadata.PublicDefinitions)
        self.public.source_paths = set()
        self.public.source_cache = {}

    def captured(self, error, reported_type=None):
        with tempfile.TemporaryDirectory(prefix='sqlite-signature-') as directory:
            root = Path(directory)
            source, evidence = root / 'source', root / 'evidence'
            source.mkdir()
            evidence.mkdir()
            call = SimpleNamespace(when='setup', excinfo=SimpleNamespace(
                type=type(error) if reported_type is None else reported_type,
                value=error, traceback=[]))
            with patch.dict(os.environ, MTG_ISOLATED_TEST_ROOT=str(source),
                            MTG_CI_EVIDENCE=str(evidence)):
                self.capture.pytest_runtest_makereport(SimpleNamespace(nodeid='public'), call)
            text = (evidence / 'failure-signatures.jsonl').read_text()
            self.assertNotIn(SECRET, text)
            return json.loads(text)['signature']

    def error(self, code):
        error = sqlite3.OperationalError(SECRET)
        error.sqlite_errorcode = code
        error.sqlite_errorname = SECRET
        return error

    def test_all_exact_native_sqlite_classes_and_derived_names(self):
        for name in SQLITE_CLASSES:
            with self.subTest(name=name):
                error = getattr(sqlite3, name)(SECRET)
                error.sqlite_errorcode = sqlite3.SQLITE_FULL
                error.sqlite_errorname = SECRET
                signature = self.captured(error)
                self.assertEqual(signature['exception'], 'SQLite' + name)
                self.assertEqual(signature.get('sqlite_errorcode'), 13)
                self.assertEqual(signature.get('sqlite_errorname'), 'SQLITE_FULL')
                self.assertEqual(signature.get('sqlite_primary_errorcode'), 13)
                self.assertEqual(signature.get('sqlite_primary_errorname'), 'SQLITE_FULL')
                self.assertEqual(self.public.diagnostic(signature), signature)

    def test_primary_and_explicit_extended_codes_capture_sanitize_parity(self):
        for name in ('SQLITE_FULL', 'SQLITE_BUSY', 'SQLITE_LOCKED', 'SQLITE_READONLY',
                     'SQLITE_IOERR', 'SQLITE_IOERR_WRITE', 'SQLITE_BUSY_SNAPSHOT',
                     'SQLITE_READONLY_DBMOVED', 'SQLITE_CONSTRAINT_UNIQUE'):
            with self.subTest(name=name):
                code = getattr(sqlite3, name)
                signature = self.captured(self.error(code))
                self.assertEqual(signature.get('sqlite_errorcode'), code)
                self.assertEqual(signature.get('sqlite_errorname'), name)
                self.assertEqual(signature.get('sqlite_primary_errorcode'), code & 255)
                self.assertEqual(self.public.diagnostic(signature), signature)

    def test_unlisted_extended_code_is_not_exported_as_raw_code(self):
        code = (42 << 8) | sqlite3.SQLITE_FULL
        signature = self.captured(self.error(code))
        self.assertEqual(signature['exception'], 'SQLiteOperationalError')
        self.assertIsNone(signature.get('sqlite_errorcode'))
        self.assertIsNone(signature.get('sqlite_errorname'))
        self.assertEqual(signature.get('sqlite_primary_errorcode'), sqlite3.SQLITE_FULL)
        self.assertEqual(signature.get('sqlite_primary_errorname'), 'SQLITE_FULL')
        self.assertEqual(self.public.diagnostic(signature), signature)

    def test_malformed_codes_and_private_names_never_cross_boundary(self):
        for code in (None, True, False, 13.0, SECRET, [13], {'code': 13}, -1,
                     1 << 80, 255):
            with self.subTest(kind=type(code).__name__):
                signature = self.captured(self.error(code))
                self.assertEqual(signature['exception'], 'SQLiteOperationalError')
                self.assertEqual([signature.get(key) for key in FIELDS], [None] * 4)
                safe = self.public.diagnostic(dict(signature, sqlite_errorcode=code,
                                                   sqlite_errorname=SECRET,
                                                   sqlite_primary_errorcode=13,
                                                   sqlite_primary_errorname=SECRET))
                self.assertEqual([safe.get(key) for key in FIELDS], [None] * 4)
                self.assertNotIn(SECRET, json.dumps(safe))

    def test_sanitizer_does_not_trust_raw_name_or_forged_primary(self):
        safe = self.public.diagnostic(dict(exception='SQLiteOperationalError', frames=[],
            sqlite_errorcode=13, sqlite_errorname=SECRET,
            sqlite_primary_errorcode=5, sqlite_primary_errorname=SECRET))
        self.assertEqual(safe.get('sqlite_errorname'), 'SQLITE_FULL')
        self.assertEqual(safe.get('sqlite_primary_errorcode'), 13)
        self.assertEqual(safe.get('sqlite_primary_errorname'), 'SQLITE_FULL')
        self.assertNotIn(SECRET, json.dumps(safe))

    def test_timeout_other_subclasses_and_fake_classes_preserve_fallback(self):
        class Child(sqlite3.OperationalError):
            pass
        fake = type('OperationalError', (Exception,), {'__module__': 'sqlite3'})
        for error, expected in ((TimeoutError(SECRET), 'TimeoutError'),
                                (Child(SECRET), 'Other'), (fake(SECRET), 'Other'),
                                (RuntimeError(SECRET), 'RuntimeError')):
            with self.subTest(expected=expected):
                error.sqlite_errorcode = 13
                signature = self.captured(error)
                self.assertEqual(signature, {'exception': expected, 'frames': []})
                self.assertEqual(self.public.diagnostic(dict(signature,
                    sqlite_errorcode=13, sqlite_errorname=SECRET)), signature)
        self.assertEqual(self.captured(RuntimeError(SECRET), sqlite3.OperationalError),
                         {'exception': 'Other', 'frames': []})

    def test_tables_are_identical_and_codes_have_unambiguous_sqlite_names(self):
        self.assertTrue(hasattr(self.capture, 'SQLITE_ERROR_CODES'), 'code table absent')
        self.assertTrue(hasattr(self.metadata, 'SQLITE_ERROR_CODES'), 'sanitizer table absent')
        self.assertEqual(self.capture.SQLITE_ERROR_CODES, self.metadata.SQLITE_ERROR_CODES)
        self.assertEqual(self.capture.EXCEPTION_CATEGORIES, self.metadata.EXCEPTION_CATEGORIES)
        for code, name in self.capture.SQLITE_ERROR_CODES.items():
            self.assertIs(type(code), int)
            self.assertEqual(getattr(sqlite3, name), code)
            self.assertTrue(name.startswith(('SQLITE_ERROR', 'SQLITE_INTERNAL', 'SQLITE_PERM',
                'SQLITE_ABORT', 'SQLITE_BUSY', 'SQLITE_LOCKED', 'SQLITE_NOMEM', 'SQLITE_READONLY',
                'SQLITE_INTERRUPT', 'SQLITE_IOERR', 'SQLITE_CORRUPT', 'SQLITE_NOTFOUND',
                'SQLITE_FULL', 'SQLITE_CANTOPEN', 'SQLITE_PROTOCOL', 'SQLITE_EMPTY',
                'SQLITE_SCHEMA', 'SQLITE_TOOBIG', 'SQLITE_CONSTRAINT', 'SQLITE_MISMATCH',
                'SQLITE_MISUSE', 'SQLITE_NOLFS', 'SQLITE_AUTH', 'SQLITE_FORMAT',
                'SQLITE_RANGE', 'SQLITE_NOTADB', 'SQLITE_NOTICE', 'SQLITE_WARNING')))

    def test_native_sql_and_socket_canaries_still_denied(self):
        import socket
        with self.assertRaisesRegex(RuntimeError, 'SQL_SOCKET_DENIED'):
            sqlite3.connect(':memory:')
        with self.assertRaisesRegex(RuntimeError, 'SQL_SOCKET_DENIED'):
            socket.socket()

    def test_actual_pytest_setup_call_and_export_preserve_complete_failure_ledger(self):
        with tempfile.TemporaryDirectory(prefix='sqlite-protocol-') as directory:
            root = Path(directory)
            source, evidence = root / 'source', root / 'evidence'
            tests = source / 'backend/tests'
            tests.mkdir(parents=True)
            evidence.mkdir()
            (tests / 'test_sqlite_public.py').write_text(
                'import sys\n'
                'def deny(event,args):\n'
                "    if event.startswith(('sqlite3.','socket.')): raise RuntimeError('DENIED')\n"
                'sys.addaudithook(deny)\n'
                'import sqlite3, socket, pytest\n'
                'for call in (lambda: sqlite3.connect(":memory:"), lambda: socket.socket()):\n'
                '    try: call()\n'
                '    except RuntimeError: pass\n'
                '    else: raise AssertionError("canary was not denied")\n'
                'def error(kind,code):\n'
                f'    value=kind({SECRET!r})\n'
                '    value.sqlite_errorcode=code\n'
                f'    value.sqlite_errorname={SECRET!r}\n'
                '    return value\n'
                '@pytest.fixture\n'
                'def rejected():\n'
                '    raise error(sqlite3.OperationalError,13)\n'
                'def test_setup(rejected): pass\n'
                'def test_call(): raise error(sqlite3.IntegrityError,2067)\n'
                f'def test_timeout(): raise TimeoutError({SECRET!r})\n'
                'def test_fake():\n'
                '    fake=type("OperationalError",(Exception,),{"__module__":"sqlite3"})\n'
                '    raise error(fake,13)\n')
            env = {
                'PATH': os.defpath, 'HOME': directory, 'LANG': 'C.UTF-8',
                'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
                'PYTHONPATH': str(SCRIPTS), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                'PYTHONDONTWRITEBYTECODE': '1', 'MTG_CI_EVIDENCE': str(evidence),
                'MTG_ISOLATED_TEST_ROOT': str(source),
            }
            for args in (('init', '-q'), ('add', '.'),
                         ('-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic SQLite errors')):
                subprocess.run(['git', '-C', str(source), *args], env=env,
                               check=True, capture_output=True)
            commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                             env=env, text=True).strip()
            result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q',
                '-p', 'no:cacheprovider', '-p', 'ci_backend_evidence', str(tests)],
                cwd=source, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            text = (evidence / 'failure-signatures.jsonl').read_text()
            self.assertNotIn(SECRET, text)
            rows = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(len(rows), 4)
            self.assertEqual({row['signature']['exception'] for row in rows},
                {'SQLiteOperationalError', 'SQLiteIntegrityError', 'TimeoutError', 'Other'})
            (evidence / 'source-head.txt').write_text(commit + '\n')
            (evidence / 'pytest-exit-code.txt').write_text('1\n')
            import contextlib
            import io
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(self.capture.audit(evidence, 1), 0)
            (evidence / 'coverage.json').write_text(output.getvalue())
            metadata = existing_signatures.load('ci_backend_metadata')
            document, status = metadata.build_metadata(evidence, source)
            self.assertEqual(status, 0)
            self.assertTrue(document['coverage']['all_collected_completed'])
            self.assertEqual(len(document['phases']), 11)
            self.assertEqual(len(document['failures']), 4)
            self.assertFalse(document['coverage']['ci_success_consistent'])
            self.assertEqual(document['metadata_error_codes'], [])
            self.assertNotIn(SECRET, json.dumps(document))
            by_kind = {row['diagnostic']['exception']: row['diagnostic']
                       for row in document['failures']}
            self.assertEqual(by_kind['SQLiteOperationalError']['sqlite_errorcode'], 13)
            self.assertEqual(by_kind['SQLiteIntegrityError']['sqlite_errorcode'], 2067)
            self.assertEqual(by_kind['SQLiteIntegrityError']['sqlite_primary_errorcode'], 19)


if __name__ == '__main__':
    unittest.main()
