"""Failure-only closed projections; no original client/driver execution."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch


class HostedDiagnosticTests(unittest.TestCase):
    def modules(self):
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        modules = []
        for name in ('host', 'guest'):
            spec = importlib.util.spec_from_file_location(name, root / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'host': modules[0]} if modules else {}):
                spec.loader.exec_module(module)
            modules.append(module)
        return modules

    def terminal(self, **change):
        return dict(exit=1, failure_type='AssertionError',
                    checks=[{'check': 'PRIVATE_FIRST', 'passed': False},
                            {'check': 'PRIVATE_SUCCESS', 'passed': True},
                            {'check': 'PRIVATE_LAST', 'passed': False}],
                    identities={}, signals=[], closure_issues=[], pid_closure=False, **change)

    def test_client_failure_is_captured_even_when_native_closure_is_missing(self):
        host, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'observe_https', None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            https = root / 'https'
            evidence = https / 'evidence/runtime-gate'
            evidence.mkdir(parents=True)
            terminal = self.terminal()
            (evidence / 'terminal.json').write_text(json.dumps(terminal))
            life = host.empty_report('lifecycle', 'a' * 40)
            with patch.object(guest, 'ROOT', root):
                actual = guest.observe_https(https, life)
            self.assertEqual(actual, terminal)
            self.assertFalse((evidence / 'native-closure.json').exists())
            self.assertEqual((life['checks'], life['passed'], life['client_exit']), (3, 1, 1))
            self.assertEqual(life['error_class'], 'AssertionError')
            self.assertEqual(life['diagnostic'], dict(origin='client', error_class='AssertionError',
                line=None, last_failed_check_sha256=hashlib.sha256(b'PRIVATE_LAST').hexdigest()))
            self.assertNotIn('PRIVATE_', json.dumps(life))
            self.assertFalse(life['verified'])
            host.validate_report(life, 'lifecycle')

    def test_zero_check_client_failure_is_valid_but_not_qualified(self):
        host, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'project_client_terminal', None)))
        terminal = self.terminal()
        terminal.update(checks=[], failure_type='FileNotFoundError')
        life = host.empty_report('lifecycle', 'a' * 40)
        life.update(guest.project_client_terminal(terminal))
        self.assertEqual(life['checks'], 0)
        self.assertEqual(life['client_exit'], 1)
        self.assertIsNone(life['diagnostic']['last_failed_check_sha256'])
        self.assertEqual(life['diagnostic']['error_class'], 'FileNotFoundError')
        self.assertFalse(life['verified'])
        host.validate_report(life, 'lifecycle')

    def test_early_driver_traceback_projects_only_known_origin_line_and_class(self):
        host, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'observe_https', None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            https = root / 'https'
            https.mkdir()
            (root / 'private-logs').mkdir()
            text = ('Traceback (most recent call last):\n  File "' +
                    str(https / 'actors/native-one-shot-driver.py') +
                    '", line 21, in <module>\n    PRIVATE_SOURCE\nFileNotFoundError: PRIVATE_MESSAGE\n')
            (root / 'private-logs/https.stderr').write_text(text)
            life = host.empty_report('lifecycle', 'a' * 40)
            with patch.object(guest, 'ROOT', root):
                self.assertIsNone(guest.observe_https(https, life))
            self.assertEqual(life['diagnostic'], dict(origin='driver', error_class='FileNotFoundError',
                                                     line=21, last_failed_check_sha256=None))
            self.assertNotIn('PRIVATE', json.dumps(life))
            self.assertNotIn(str(root), json.dumps(life))

    def test_generic_outer_failure_never_replaces_valid_inner_cause(self):
        host, guest = self.modules()
        self.assertTrue(callable(getattr(host, 'outer_failure', None)))
        self.assertTrue(callable(getattr(guest, 'project_client_terminal', None)))
        life = host.empty_report('lifecycle', 'a' * 40)
        life.update(guest.project_client_terminal(self.terminal()))
        diagnostic = dict(life['diagnostic'])
        host.outer_failure(life, host.StageError(1), cancelled=False)
        self.assertEqual(life['error_class'], 'AssertionError')
        self.assertEqual(life['diagnostic'], diagnostic)
        self.assertEqual((life['checks'], life['passed'], life['client_exit']), (3, 1, 1))
        self.assertFalse(life['verified'])
        host.validate_report(life, 'lifecycle')

    def test_public_diagnostic_is_closed_typed_and_bounded(self):
        host, _ = self.modules()
        row = host.empty_report('lifecycle', 'a' * 40)
        self.assertIn('diagnostic', row)
        for change in ({'message': 'PRIVATE'}, {'origin': 'PRIVATE'}, {'error_class': 'PRIVATE'},
                       {'line': True}, {'line': 0}, {'line': -1}, {'line': 100001},
                       {'last_failed_check_sha256': 'PRIVATE'}, {'last_failed_check_sha256': 'a' * 65}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                host.validate_report(dict(row, diagnostic=dict(row['diagnostic'], **change)), 'lifecycle')
        self.assertLessEqual(len(json.dumps(row['diagnostic']).encode()), 512)

    def test_bounded_traceback_reader_does_not_expose_unknown_files_or_messages(self):
        _, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'trace_diagnostic', None)))
        root = Path('/tmp/mtg-hosted-clean/https')
        text = b'Traceback (most recent call last):\n  File "/PRIVATE_PATH", line 9, in unknown\nValueError: PRIVATE_BODY\n'
        row = guest.trace_diagnostic(text, root)
        self.assertEqual(row['origin'], 'unknown')
        self.assertIsNone(row['line'])
        self.assertNotIn('PRIVATE', json.dumps(row))
        with self.assertRaises(ValueError):
            guest.trace_diagnostic(b'x' * 65537, root)

    def test_real_guest_and_host_wire_projection_before_closure_and_outer_failure(self):
        host, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'observe_https', None)))
        root = Path(__file__).resolve().parents[3] / 'ops/ci/hosted-clean'
        tree = ast.parse((root / 'guest.py').read_bytes())
        observation = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Name) and n.func.id == 'observe_https']
        closure = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant)
                   and n.value == 'evidence/runtime-gate/native-closure.json']
        self.assertEqual(len(observation), 1)
        self.assertEqual(len(closure), 1)
        self.assertLess(observation[0], closure[0])
        host_tree = ast.parse((root / 'host.py').read_bytes())
        self.assertEqual(sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == 'outer_failure' for n in ast.walk(host_tree)), 1)

    def test_private_reader_rejects_link_even_if_path_precheck_is_stale(self):
        _, guest = self.modules()
        self.assertTrue(callable(getattr(guest, 'read_diagnostic_input', None)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'owned-dummy').write_bytes(b'OWNED_CANARY')
            link = root / 'expected-log'
            link.symlink_to(root / 'owned-dummy')
            with patch.object(type(link), 'is_symlink', return_value=False):
                with self.assertRaises((OSError, ValueError)):
                    guest.read_diagnostic_input(link, 65536)
