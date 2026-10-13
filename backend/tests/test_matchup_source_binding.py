"""Source and output protocol; inert callbacks are NOT actual games."""
import builtins
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from tests.test_matchup_round_robin_protocol import BACKEND, roster


@contextmanager
def command(argv, database=None):
    old_argv = sys.argv
    old_database = os.environ.get('MTG_DATABASE_PATH')
    try:
        sys.argv = argv
        if database is not None:
            os.environ['MTG_DATABASE_PATH'] = str(database)
        yield
    finally:
        sys.argv = old_argv
        if old_database is None:
            os.environ.pop('MTG_DATABASE_PATH', None)
        else:
            os.environ['MTG_DATABASE_PATH'] = old_database


class SourceBindingTests(unittest.TestCase):
    def setUp(self):
        path = BACKEND / 'scripts/matchup_round_robin.py'
        self.api = {'__file__': str(path), '__name__': 'binding_protocol', '__builtins__': dict(vars(builtins))}
        exec(compile(path.read_text(), str(path), 'exec'), self.api)

    def require(self, name):
        self.assertTrue(callable(self.api.get(name)), 'Missing source-bound API: '+name)
        return self.api[name]

    def tree(self, root):
        (root/'ai').mkdir()
        (root/'rules_engine').mkdir()
        (root/'ai/agent.py').write_text('version = "cast-candidate"\n')
        (root/'rules_engine/engine.py').write_text('version = "engine"\n')
        (root/'ordinary.json').write_text('{"value": 1}')

    def binding(self, root):
        files = self.require('collect_source_manifest')(root)
        return dict(schema_version=1, source_base_commit='a'*40, backend_files=files,
                    backend_sha256=self.api['digest'](files))

    def test_01_actual_whole_source_includes_agent_engine_data(self):
        collect = self.require('collect_source_manifest')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root)
            files = collect(root)
            self.assertEqual(set(files), {'ai/agent.py', 'rules_engine/engine.py', 'ordinary.json'})
            self.assertEqual(files['ai/agent.py'], hashlib.sha256((root/'ai/agent.py').read_bytes()).hexdigest())

    def test_02_changed_agent_engine_input_and_extra_file_reject_before_callback(self):
        verify = self.require('verify_source_binding')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root)
            binding = self.binding(root)
            for path in ('ai/agent.py', 'rules_engine/engine.py', 'ordinary.json', 'new_source.py'):
                target = root/path
                previous = target.read_bytes() if target.exists() else None
                target.write_text('changed')
                with self.assertRaises(ValueError):
                    verify(binding, root)
                if previous is None:
                    target.unlink()
                else:
                    target.write_bytes(previous)
            self.assertEqual(verify(binding, root), binding['backend_sha256'])

    def test_03_explicit_epoch_digest_and_typed_fields_not_ambient_461(self):
        verify = self.require('verify_source_binding')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root)
            binding = self.binding(root)
            for bad in (None, {}, dict(binding, source_base_commit=None), dict(binding, source_base_commit='461'),
                        dict(binding, schema_version=True), dict(binding, backend_sha256='b'*64),
                        dict(binding, backend_files={'ai/agent.py': binding['backend_files']['ai/agent.py']})):
                with self.assertRaises(ValueError):
                    verify(bad, root)
            binding['source_base_commit'] = 'b'*40
            self.assertEqual(verify(binding, root), binding['backend_sha256'])

    def test_04_only_declared_runtime_and_cache_absences_excluded(self):
        collect = self.require('collect_source_manifest')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root)
            baseline = collect(root)
            for directory in ('__pycache__', '.pytest_cache', '.venv', 'node_modules', 'runtime', 'generated', 'evidence'):
                (root/directory).mkdir()
                (root/directory/'fake').write_text('not source')
            self.assertEqual(collect(root), baseline)
            (root/'nested').mkdir()
            (root/'nested/ordinary.py').write_text('retained')
            self.assertIn('nested/ordinary.py', collect(root))

    def test_05_missing_binding_stops_route_before_canonical_admission(self):
        run = self.require('run_round_robin')
        self.assertIn('source_binding', run.__kwdefaults__ or {})
        calls = []
        self.api['admit_execution_rows'] = lambda rows: calls.append('admitted')
        with self.assertRaises(ValueError):
            run(self.api['make_export'](roster(), corpus_sha256='a'*64), [0], difficulty='strong',
                max_ticks=1, limits={}, private_directory='unused', source_binding=None)
        self.assertEqual(calls, [])

    def test_06_source_after_drift_is_not_qualified(self):
        check = self.require('source_closure')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.tree(root)
            binding = self.binding(root)
            before = self.api['verify_source_binding'](binding, root)
            self.assertTrue(check(binding, root, before)['equal'])
            (root/'ai/agent.py').write_text('changed during protocol')
            result = check(binding, root, before)
            self.assertFalse(result['equal'])
            self.assertEqual(result['source_base_commit'], 'a'*40)
            self.assertEqual(result['before_sha256'], binding['backend_sha256'])
            self.assertNotEqual(result['after_sha256'], result['before_sha256'])

    def test_07_existing_output_stops_before_execution_callback(self):
        main = self.require('main')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'export.json').write_text(json.dumps(self.api['make_export'](roster(), corpus_sha256='a'*64)))
            (root/'limits.json').write_text('{}')
            (root/'binding.json').write_text('{}')
            sentinel = root/'summary.json'
            sentinel.write_bytes(b'original sentinel')
            calls = []
            supports_binding = 'source_binding' in (self.api['run_round_robin'].__kwdefaults__ or {})
            self.api['run_round_robin'] = lambda *a, **k: (calls.append(True), {'complete': True})[1]
            argv = ['runner', '--execute', '--deck-export', str(root/'export.json'), '--seed-token', '0',
                '--output', str(sentinel), '--private-directory', str(root/'private'), '--limits-json', str(root/'limits.json'),
                '--difficulty', 'strong', '--max-ticks', '1']
            if supports_binding:
                argv += ['--source-binding', str(root/'binding.json')]
            error = None
            with command(argv, root/'owned.sqlite'):
                try:
                    main()
                except BaseException as exc:
                    error = exc
            self.assertEqual(calls, [], 'Existing output must be admitted before matrix callback')
            self.assertIsInstance(error, FileExistsError)
            self.assertEqual(sentinel.read_bytes(), b'original sentinel')

    def test_08_export_alias_output_preserves_input(self):
        main = self.require('main')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'export.json'
            raw = json.dumps(self.api['make_export'](roster(), corpus_sha256='a'*64)).encode()
            path.write_bytes(raw)
            with command(['runner', '--deck-export', str(path), '--output', str(path), '--seed-token', '0']):
                with self.assertRaises(FileExistsError):
                    main()
            self.assertEqual(path.read_bytes(), raw)

    def test_09_unreadable_end_source_explicitly_unavailable(self):
        closure = self.require('source_closure')
        binding = dict(source_base_commit='a'*40, backend_sha256='b'*64, backend_files={'public.py': 'c'*64})
        def unavailable(root):
            raise OSError('inert inaccessible source')
        self.api['collect_source_manifest'] = unavailable
        result = closure(binding, Path('/unused'), binding['backend_sha256'])
        self.assertFalse(result['equal'])
        self.assertIsNone(result['after_sha256'])

    def test_10_export_baseline_is_not_measured_epoch(self):
        self.assertEqual(self.api.get('EXPORT_BASE_COMMIT'), '46158ddb40a2e67e27a37c0854eba8d2bc05a281')
        text = (BACKEND/'scripts/matchup_round_robin.py').read_text()
        self.assertNotIn("source_base_commit=SOURCE_COMMIT", text)
        self.assertIn("source_base_commit=source_binding['source_base_commit']", text)
        self.assertIn("input_export_base_commit=export['source_commit']", text)
