"""Mock/AST plumbing only: no project imports, games, SQL, or native closure proof."""
import ast
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / 'backend/tests/human_bo3_series_fixture.py'


class MockProducerFailure(RuntimeError):
    pass


class HumanBo3CallFixtureProtocolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mtg-bo3-fixture-protocol-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.evidence = self.root / 'private-evidence'
        self.evidence.mkdir(mode=0o700)
        self.database = self.root / 'mock-database-never-opened.db'
        self.environ = {'MTG_HUMAN_BO3_EVIDENCE': str(self.evidence),
                        'MTG_DATABASE_PATH': str(self.database)}

    def factory(self, name, producer):
        # Compile only this exact fixture definition, never the real series body.
        tree = ast.parse(HELPER.read_text(), filename=str(HELPER))
        nodes = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == 'native_human_bo3_series']
        self.assertEqual(len(nodes), 1)
        node = deepcopy(nodes[0])
        self.assertEqual([type(row).__name__ for row in node.body],
                         ['Assign', 'FunctionDef', 'Return'])
        node.decorator_list = []
        namespace = {'__file__': str(HELPER), 'Path': Path,
                     'os': SimpleNamespace(environ=self.environ),
                     'DATABASE_PATH': self.database,
                     'engine': SimpleNamespace(url=SimpleNamespace(database=str(self.database))),
                     '_run_checked_human_bo3_series': producer}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(HELPER), 'exec'), namespace)
        case = self.root / name
        case.mkdir(mode=0o700)
        return namespace['native_human_bo3_series'](case), case

    def test_setup_is_inert_and_both_original_callsites_run_during_call(self):
        events = ['SETUP']

        def producer(root, out):
            self.assertEqual(events, ['SETUP', 'CALL'])
            self.assertEqual(root, ROOT)
            try:
                events.append('mock-producer')
                (out / 'terminal.json').write_text('MOCK_ONLY_NOT_A_NATIVE_CERTIFICATE')
            finally:
                events.append('mock-cleanup')

        produce, case = self.factory('call-site', producer)
        self.assertEqual(events, ['SETUP'])
        self.assertFalse((self.evidence / ('series-' + case.name)).exists())
        events.append('CALL')
        terminal, database = produce()
        self.assertEqual(events, ['SETUP', 'CALL', 'mock-producer', 'mock-cleanup'])
        self.assertEqual(terminal, self.evidence / ('series-' + case.name) / 'interactive/terminal.json')
        self.assertFalse(terminal.is_relative_to(case))
        self.assertEqual(database, self.database)
        self.assertEqual(terminal.read_text(), 'MOCK_ONLY_NOT_A_NATIVE_CERTIFICATE')
        names = {
            'test_human_bo3_interactive.py': 'test_seeded_human_bo3_checked_http_cold_restart',
            'test_human_bo3_terminal_restore.py':
                'test_native_completed_series_survives_cold_read_without_sql_mutation',
        }
        for filename, name in names.items():
            tree = ast.parse((HELPER.parent / filename).read_text())
            node, = [row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == name]
            self.assertIn('native_human_bo3_series', [arg.arg for arg in node.args.args])
            calls = [index for index, row in enumerate(node.body)
                     if any(isinstance(part, ast.Call) and isinstance(part.func, ast.Name)
                            and part.func.id == 'native_human_bo3_series' for part in ast.walk(row))]
            self.assertEqual(len(calls), 1)
            if filename.endswith('terminal_restore.py'):
                reads = [index for index, row in enumerate(node.body)
                         if any(isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute)
                                and part.func.attr == 'read_text' for part in ast.walk(row))]
                self.assertTrue(reads)
                self.assertLess(calls[0], min(reads))

    def test_single_use_remains_consumed_after_success_or_producer_failure(self):
        for fail in (False, True):
            with self.subTest(failure=fail):
                calls = []

                def producer(_root, _out):
                    calls.append('mock-producer')
                    if fail:
                        raise MockProducerFailure('mock failure')

                produce, _ = self.factory('single-' + str(fail), producer)
                if fail:
                    with self.assertRaises(MockProducerFailure):
                        produce()
                else:
                    produce()
                with self.assertRaisesRegex(RuntimeError, 'single-use'):
                    produce()
                self.assertEqual(calls, ['mock-producer'])

    def test_preexisting_directory_or_symlink_never_adopts_stale_terminal(self):
        stale = self.evidence / 'interactive'
        stale.mkdir(mode=0o700)
        (stale / 'terminal.json').write_text('MOCK_STALE_MUST_NOT_BE_CONSUMED')
        for kind in ('directory', 'symlink'):
            with self.subTest(kind=kind):
                calls = []
                produce, case = self.factory('existing-' + kind, lambda *_: calls.append('mock-producer'))
                destination = self.evidence / ('series-' + case.name)
                if kind == 'directory':
                    destination.mkdir(mode=0o700)
                else:
                    destination.symlink_to(stale, target_is_directory=True)
                with self.assertRaises(FileExistsError):
                    produce()
                self.assertEqual(calls, [])
                self.assertEqual((stale / 'terminal.json').read_text(), 'MOCK_STALE_MUST_NOT_BE_CONSUMED')
                with self.assertRaisesRegex(RuntimeError, 'single-use'):
                    produce()

    def test_mock_producer_or_cleanup_exception_prevents_handoff(self):
        for stage in ('producer', 'cleanup'):
            with self.subTest(stage=stage):
                events = []
                failure = MockProducerFailure('mock ' + stage)

                def producer(_root, _out):
                    try:
                        events.append('mock-enter')
                        if stage == 'producer':
                            raise failure
                    finally:
                        events.append('mock-cleanup')
                        if stage == 'cleanup':
                            raise failure

                produce, _ = self.factory('failure-' + stage, producer)
                with self.assertRaises(MockProducerFailure) as caught:
                    produce()
                self.assertIs(caught.exception, failure)
                self.assertEqual(events, ['mock-enter', 'mock-cleanup'])
                with self.assertRaisesRegex(RuntimeError, 'single-use'):
                    produce()

    def test_database_mismatch_or_postproducer_drift_prevents_handoff(self):
        calls = []
        produce, case = self.factory('wrong-db', lambda *_: calls.append('mock-producer'))
        self.environ['MTG_DATABASE_PATH'] = str(self.root / 'other-mock.db')
        with self.assertRaisesRegex(RuntimeError, 'binding mismatch'):
            produce()
        self.assertEqual(calls, [])
        self.assertFalse((self.evidence / ('series-' + case.name)).exists())
        self.environ['MTG_DATABASE_PATH'] = str(self.database)

        def drift(_root, _out):
            calls.append('mock-producer')
            self.environ['MTG_DATABASE_PATH'] = str(self.root / 'changed-mock.db')

        produce, _ = self.factory('changed-db', drift)
        with self.assertRaisesRegex(RuntimeError, 'binding changed'):
            produce()
        self.assertEqual(calls, ['mock-producer'])
        with self.assertRaisesRegex(RuntimeError, 'single-use'):
            produce()


if __name__ == '__main__':
    unittest.main()
