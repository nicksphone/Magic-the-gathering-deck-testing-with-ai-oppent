"""Parser stand-ins/local files only; no Node, native browser, app import or SQL.

The separate JavaScript module exercises the real publisher. Records here are
explicit protocol inputs, not claimed publisher artifacts or runtime authority.
"""
import builtins
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'firefox_bootstrap_body_cache', Path(__file__).with_name('firefox_body_cache_app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FactoryImportBoundary(Exception):
    """Stop before the genuine fixture is imported, without substituting an app."""


class DisabledBootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='firefox-bootstrap-parser-',
                                                dir=os.environ.get('TMPDIR', '/tmp'))
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.directory.chmod(0o700)
        self.file = self.directory / 'enrollment.json'
        self.bindings = {'run_nonce': '4' * 32, 'source_binding': 'b' * 64,
                         'api_origin': 'http://127.0.0.1:19000',
                         'frontend_origin': 'http://127.0.0.1:15173'}
        self.bootstrap = {**self.bindings, 'schema_version': 1, 'generation': 0,
                          'enabled': False, 'episode': None, 'publisher_uid': os.getuid(),
                          'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text()
                                                                 .rsplit(')', 1)[1].split()[19]),
                          'native_top_context': None, 'armed_ns': '0', 'expires_ns': '0'}

    def write(self, row):
        next_file = self.directory / 'parser-input.next'
        fd = os.open(next_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(row, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(next_file, self.file)

    def broker(self, upstream=None):
        return module.BodyCache(upstream, self.directory, self.bindings)

    def accept_bootstrap(self, broker):
        try:
            result = broker._control()
        except module.Unavailable as error:
            self.fail('Exact disabled generation zero must validate before inactive return: ' + str(error))
        self.assertIsNone(result)
        self.assertEqual(broker.control_generation, 0)
        self.assertIsNotNone(broker.control_identity)
        self.assertEqual(broker.publisher,
                         (os.getuid(), os.getpid(), self.bootstrap['start_ticks']))

    def real_window(self, generation=1, enabled=True, episode='human_vs_human'):
        began = time.monotonic_ns()
        milliseconds = 900000 if episode == 'human_vs_human' else 1200000
        return {**self.bootstrap, 'generation': generation, 'enabled': enabled,
                'episode': episode, 'native_top_context': 'protocol-top' if enabled else None,
                'armed_ns': str(began), 'expires_ns': str(began + milliseconds * 1000000)}

    def factory_probe(self):
        events = []
        original_import = builtins.__import__
        original_control = module.BodyCache._control

        def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'tests.current_built_browser_server':
                events.append(('fixture-import-boundary', name))
                raise FactoryImportBoundary()
            if name == 'main':
                raise AssertionError('No application import is authorized by this unit test')
            return original_import(name, globals, locals, fromlist, level)

        def observe_control(broker):
            result = original_control(broker)
            events.append(('control-validated', broker.control_generation,
                           broker.control_identity is not None, broker.publisher))
            return result

        environment = {'MTG_RELEASE_BODY_CACHE_ROOT': str(self.directory),
                       'MTG_RELEASE_BODY_CACHE_ENROLLMENT': str(self.file),
                       'MTG_BROKER_RUN_NONCE': self.bindings['run_nonce'],
                       'MTG_BROKER_SOURCE_BINDING': self.bindings['source_binding'],
                       'MTG_BUILT_BACKEND_PORT': '19000',
                       'MTG_BUILT_PAGE_ORIGIN': self.bindings['frontend_origin']}
        with patch.dict(os.environ, environment), patch.object(module.BodyCache, '_control', observe_control), \
                patch('builtins.__import__', side_effect=controlled_import):
            try:
                module.create_app()
            except FactoryImportBoundary:
                return 'validated-import-boundary', events
            except module.Unavailable as error:
                return 'rejected:' + str(error), events
        self.fail('The unit must stop at the genuine import boundary, never substitute an app')

    def test_first_zero_pins_publisher_and_file_before_inactive_return(self):
        self.write(self.bootstrap)
        self.accept_bootstrap(self.broker())

    def test_exact_same_zero_identity_can_be_read_again_without_rebinding(self):
        self.write(self.bootstrap)
        broker = self.broker()
        self.accept_bootstrap(broker)
        identity, publisher = broker.control_identity, broker.publisher
        self.accept_bootstrap(broker)
        self.assertEqual((broker.control_identity, broker.publisher), (identity, publisher))

    def test_zero_requires_exact_types_nulls_and_zero_decimal_strings(self):
        variants = [('generation', False), ('generation', 0.0), ('generation', '0'),
                    ('enabled', True), ('enabled', 0), ('enabled', None),
                    ('episode', 'human_vs_human'), ('episode', ''),
                    ('native_top_context', 'made-up-top'), ('native_top_context', ''),
                    ('armed_ns', '00'), ('armed_ns', 0), ('armed_ns', '1'),
                    ('expires_ns', '00'), ('expires_ns', 0), ('expires_ns', '1'),
                    ('schema_version', True), ('schema_version', 1.0)]
        for field, value in variants:
            with self.subTest(field=field, value=value):
                self.write({**self.bootstrap, field: value})
                with self.assertRaises(module.Unavailable):
                    self.broker()._control()

    def test_zero_retains_exact_schema_keyset(self):
        for row in ({**self.bootstrap, 'unexpected': None},
                    {key: value for key, value in self.bootstrap.items() if key != 'episode'}):
            with self.subTest(keys=sorted(row)):
                self.write(row)
                with self.assertRaises(module.Unavailable):
                    self.broker()._control()

    def test_zero_still_requires_every_immutable_binding(self):
        changes = {'run_nonce': '5' * 32, 'source_binding': 'c' * 64,
                   'api_origin': 'http://127.0.0.1:19001',
                   'frontend_origin': 'http://127.0.0.1:15174'}
        for field, value in changes.items():
            with self.subTest(field=field):
                self.write({**self.bootstrap, field: value})
                with self.assertRaises(module.Unavailable):
                    self.broker()._control()

    def test_zero_wrong_uid_and_actual_pid_start_are_rejected(self):
        for field, value in [('publisher_uid', os.getuid() + 1),
                             ('start_ticks', self.bootstrap['start_ticks'] + 1)]:
            with self.subTest(field=field):
                self.write({**self.bootstrap, field: value})
                with self.assertRaises(module.Unavailable):
                    self.broker()._control()

    def test_same_bytes_on_a_different_zero_inode_are_not_a_reread(self):
        self.write(self.bootstrap)
        broker = self.broker()
        self.accept_bootstrap(broker)
        self.write(self.bootstrap)
        with self.assertRaisesRegex(module.Unavailable, 'ENROLLMENT_GENERATION'):
            broker._control()

    def test_changed_zero_file_identity_is_rejected_even_without_inode_replacement(self):
        self.write(self.bootstrap)
        broker = self.broker()
        self.accept_bootstrap(broker)
        inode = self.file.stat().st_ino
        with self.file.open('a') as output:
            output.write(' ')
        self.assertEqual(self.file.stat().st_ino, inode)
        with self.assertRaisesRegex(module.Unavailable, 'ENROLLMENT_GENERATION'):
            broker._control()

    def test_zero_cannot_roll_back_an_accepted_real_generation(self):
        self.write(self.real_window())
        broker = self.broker()
        self.assertEqual(broker._control()['generation'], 1)
        self.write(self.bootstrap)
        with self.assertRaisesRegex(module.Unavailable, 'ENROLLMENT_GENERATION'):
            broker._control()

    def test_publisher_change_after_zero_cannot_be_admitted_as_a_real_window(self):
        self.write(self.bootstrap)
        broker = self.broker()
        self.accept_bootstrap(broker)
        self.write({**self.real_window(), 'pid': 999999})
        original_read_text = Path.read_text

        def process_standin(file, *args, **kwargs):
            if file == Path('/proc/999999/stat'):
                return '999999 (protocol-only) ' + ' '.join(['0'] * 19 + [str(self.bootstrap['start_ticks'])])
            return original_read_text(file, *args, **kwargs)

        with patch.object(Path, 'read_text', process_standin):
            with self.assertRaisesRegex(module.Unavailable, 'ENROLLMENT_PUBLISHER'):
                broker._control()

    def test_bootstrap_preserves_all_three_real_windows_and_six_generations(self):
        self.write(self.bootstrap)
        broker = self.broker()
        self.accept_bootstrap(broker)
        for index, episode in enumerate(('human_vs_human', 'player_vs_ai', 'player_vs_ai-seat2')):
            generation = 1 + index * 2
            self.write(self.real_window(generation, True, episode))
            current = broker._control()
            self.assertEqual((current['generation'], current['episode']), (generation, episode))
            self.write(self.real_window(generation + 1, False, episode))
            self.assertIsNone(broker._control())
        self.assertEqual(broker.control_generation, 6)
        self.write(self.real_window(7))
        with self.assertRaises(module.Unavailable):
            broker._control()
        self.assertEqual(module.MAX_BODY, 8 * 1024 * 1024)
        self.assertEqual(module.TTL_NS, 15_000_000_000)

    def test_original_generation_one_first_read_remains_valid_without_bootstrap(self):
        row = self.real_window()
        self.write(row)
        self.assertEqual(self.broker()._control(), row)

    def test_disabled_zero_never_captures_or_changes_the_upstream_response(self):
        self.write(self.bootstrap)
        calls, sent = [], []
        scope = {'type': 'http', 'method': 'POST', 'path': '/matches/test/action',
                 'raw_path': b'/matches/test/action', 'query_string': b'', 'headers': []}

        async def receive():
            return {'type': 'http.request', 'body': b'original', 'more_body': False}

        async def send(message):
            sent.append(message)

        messages = [{'type': 'http.response.start', 'status': 200, 'headers': [(b'x-original', b'yes')]},
                    {'type': 'http.response.body', 'body': b'unchanged', 'more_body': False}]

        async def upstream(actual_scope, actual_receive, actual_send):
            calls.append((actual_scope, actual_receive, actual_send))
            for message in messages:
                await actual_send(message)

        broker = self.broker(upstream)
        self.accept_bootstrap(broker)
        coroutine = broker(scope, receive, send)
        try:
            coroutine.send(None)
        except StopIteration:
            pass
        else:
            coroutine.close()
            self.fail('Pure inactive pass-through must not perform asynchronous IO')
        self.assertEqual(calls, [(scope, receive, send)])
        self.assertEqual(sent, messages)
        self.assertEqual(broker.entries, {})
        self.assertEqual(broker.pending, 0)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ['enrollment.json'])

    def test_valid_zero_is_checked_before_reaching_the_genuine_factory_import_boundary(self):
        self.write(self.bootstrap)
        outcome, events = self.factory_probe()
        self.assertEqual(outcome, 'validated-import-boundary')
        self.assertEqual(events[0], ('control-validated', 0, True,
                                    (os.getuid(), os.getpid(), self.bootstrap['start_ticks'])))
        self.assertEqual(events[1], ('fixture-import-boundary', 'tests.current_built_browser_server'))
        self.assertEqual(len(events), 2)

    def test_missing_bootstrap_is_rejected_without_any_fixture_import(self):
        outcome, events = self.factory_probe()
        self.assertEqual(outcome, 'rejected:CACHE_ENROLLMENT_MISSING')
        self.assertEqual(events, [])

    def test_forged_enabled_zero_is_rejected_before_any_fixture_import(self):
        self.write({**self.bootstrap, 'enabled': True, 'native_top_context': 'forged'})
        outcome, events = self.factory_probe()
        self.assertTrue(outcome.startswith('rejected:'))
        self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
