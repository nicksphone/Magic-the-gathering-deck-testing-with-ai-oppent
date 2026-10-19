"""PUBLIC fake-stream/filesystem controls; no backend, SQL or job execution."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


def module():
    path = Path(__file__).resolve().parents[1] / 'ci_backend_storage.py'
    assert path.is_file(), 'Missing bounded CI storage implementation'
    spec = importlib.util.spec_from_file_location('owned_ci_storage', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class BackendStorageTests(unittest.TestCase):
    def test_public_16mib_stream_is_bounded_unduplicated_and_digest_complete(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            payload = bytes(range(256)) * (16 * 1024 * 1024 // 256)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                sink = m.BoundedStream(root, 'pytest.log')
                for start in range(0, len(payload), 65536):
                    sink.write(payload[start:start+65536])
                receipt = sink.close()
            self.assertEqual(output.getvalue(), '')
            retained = (root / 'pytest.log.previous').read_bytes() + (root / 'pytest.log').read_bytes()
            self.assertEqual(retained, payload[-m.LOG_BYTES:])
            self.assertEqual(len(retained), m.LOG_BYTES)
            self.assertFalse((root / 'runner.log').exists())
            self.assertEqual(receipt['observed_bytes'], len(payload))
            self.assertEqual(receipt['retained_bytes'], len(retained))
            self.assertEqual(receipt['dropped_bytes'], len(payload)-len(retained))
            self.assertTrue(receipt['truncated'])
            self.assertEqual(receipt['full_stream_sha256'], hashlib.sha256(payload).hexdigest())

    def test_short_stream_remains_byte_exact_with_no_truncation(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sink = m.BoundedStream(root, 'runner.log')
            sink.write(b'PUBLIC diagnostic\x00\xff\n')
            receipt = sink.close()
            self.assertEqual((root / 'runner.log').read_bytes(), b'PUBLIC diagnostic\x00\xff\n')
            self.assertFalse(receipt['truncated'])
            self.assertEqual(receipt['dropped_bytes'], 0)

    def test_preexisting_failure_log_is_retained_and_rejected(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'pytest.log.previous').write_bytes(b'PUBLIC prior failure')
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_PATH'):
                m.BoundedStream(root, 'pytest.log')
            self.assertEqual((root / 'pytest.log.previous').read_bytes(), b'PUBLIC prior failure')
            self.assertFalse((root / 'pytest.log').exists())

    def test_symlink_root_or_filename_never_changes_foreign_file(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root = parent / 'evidence'; root.mkdir()
            foreign = parent / 'foreign'; foreign.write_bytes(b'PUBLIC foreign')
            (root / 'pytest.log').symlink_to(foreign)
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_PATH'):
                m.BoundedStream(root, 'pytest.log')
            alias = parent / 'alias'; alias.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_PATH'):
                m.BoundedStream(alias, 'runner.log')
            self.assertEqual(foreign.read_bytes(), b'PUBLIC foreign')

    def test_changed_owned_log_is_not_overwritten_or_removed(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sink = m.BoundedStream(root, 'pytest.log', limit=8)
            sink.write(b'1234')
            (root / 'pytest.log').rename(root / 'held-original')
            (root / 'pytest.log').write_bytes(b'PUBLIC foreign replacement')
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_CHANGED'):
                sink.write(b'56789')
            self.assertEqual((root / 'pytest.log').read_bytes(), b'PUBLIC foreign replacement')
            sink.abort()

    def test_reserve_is_allocated_early_and_released_before_terminal(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            m.prepare(root, reserve_bytes=4096)
            self.assertEqual((root / m.RESERVE_NAME).stat().st_size, 4096)
            guard = m.StoragePressure(root)
            guard.close()
            self.assertFalse((root / m.RESERVE_NAME).exists())
            self.assertEqual(json.loads((root / 'storage-status.json').read_text())['state'], 'released')

    def test_pressure_is_sticky_releases_reserve_and_retains_unknown_roots(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'failed-scratch').mkdir()
            (root / 'failed-scratch/source.py').write_text('PUBLIC = True\n')
            m.prepare(root, reserve_bytes=4096)
            guard = m.StoragePressure(root)
            low = SimpleNamespace(f_bavail=0, f_frsize=4096, f_favail=99999)
            self.assertTrue(guard.sample(low))
            self.assertTrue(guard.stopped)
            self.assertFalse((root / m.RESERVE_NAME).exists())
            good = SimpleNamespace(f_bavail=999999999, f_frsize=4096, f_favail=99999)
            self.assertTrue(guard.sample(good))
            self.assertEqual((root / 'failed-scratch/source.py').read_text(), 'PUBLIC = True\n')
            self.assertEqual(json.loads((root / 'storage-status.json').read_text())['reason'], 'byte-pressure')
            guard.close()

    def test_inode_pressure_and_invalid_observation_are_explicit_stops(self):
        m = module()
        for kind in ('inode', 'invalid'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                m.prepare(root, reserve_bytes=4096)
                guard = m.StoragePressure(root)
                values = SimpleNamespace(f_bavail=999999999, f_frsize=4096,
                                         f_favail=0 if kind == 'inode' else True)
                self.assertTrue(guard.sample(values))
                self.assertEqual(guard.reason, 'inode-pressure' if kind == 'inode' else 'observation-error')
                guard.close()

    def test_preexisting_or_replaced_reserve_is_never_removed(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / m.RESERVE_NAME).write_bytes(b'PUBLIC preexisting')
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_PATH'):
                m.prepare(root, reserve_bytes=4096)
            self.assertEqual((root / m.RESERVE_NAME).read_bytes(), b'PUBLIC preexisting')

    def test_policy_constants_preserve_twenty_gib_admission_and_private_markers(self):
        m = module()
        self.assertEqual(m.LOG_BYTES, 8 * 1024 * 1024)
        self.assertEqual(m.RESERVE_BYTES, 64 * 1024 * 1024)
        self.assertEqual(m.MIN_FREE_BYTES, 1024 ** 3)
        self.assertEqual(m.MIN_FREE_INODES, 4096)
        path = Path(__file__).resolve().parents[1]
        self.assertIn('MIN_FREE_BYTES = 20 * 1024 ** 3', (path / 'ci_backend_capacity.py').read_text())

    def test_bool_schema_is_not_a_valid_reserve_receipt(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            m.prepare(root, reserve_bytes=4096)
            value = json.loads((root / 'storage-status.json').read_text())
            value['schema'] = True
            (root / 'storage-status.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_CHANGED'):
                m.StoragePressure(root)
            self.assertTrue((root / m.RESERVE_NAME).exists())

    def test_replaced_status_is_retained_and_reserve_not_removed(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            m.prepare(root, reserve_bytes=4096)
            guard = m.StoragePressure(root)
            status = root / 'storage-status.json'
            status.rename(root / 'held-status')
            status.write_text('PUBLIC foreign status')
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_CHANGED'):
                guard.close()
            self.assertEqual(status.read_text(), 'PUBLIC foreign status')
            self.assertTrue((root / m.RESERVE_NAME).exists())

    def test_pytest_optin_restores_background_interrupt_only_when_enabled(self):
        m = module()
        with mock.patch.object(m.signal, 'signal') as install:
            with mock.patch.dict(os.environ, {'MTG_CI_STORAGE_GUARD': '1'}):
                self.assertTrue(hasattr(m, 'pytest_configure'), 'Missing background SIGINT restoration')
                m.pytest_configure(None)
                install.assert_called_once_with(m.signal.SIGINT, m.signal.default_int_handler)
            install.reset_mock()
            with mock.patch.dict(os.environ, {'MTG_CI_STORAGE_GUARD': '0'}):
                m.pytest_configure(None)
                install.assert_not_called()

    def test_full_volume_terminal_write_uses_released_reserve_and_phase_rows_exact(self):
        m = module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            m.prepare(root, reserve_bytes=4096)
            rows = b'{"nodeid":"PUBLIC","when":"setup","outcome":"passed"}\n' * 3
            (root / 'phases.jsonl').write_bytes(rows)
            guard = m.StoragePressure(root)
            original = m.write_status
            def full_volume(target, value):
                self.assertFalse((root / m.RESERVE_NAME).exists(), 'No terminal headroom')
                original(target, value)
            with mock.patch.object(m, 'write_status', side_effect=full_volume):
                self.assertTrue(guard.sample(SimpleNamespace(f_bavail=0, f_frsize=4096, f_favail=0)))
                guard.close()
            self.assertEqual((root / 'phases.jsonl').read_bytes(), rows)
            self.assertEqual(json.loads((root / 'storage-status.json').read_text())['state'], 'pressure-stopped')

    def test_actual_runner_16mib_split_preserves_all_observed_phases_and_no_public_stderr(self):
        path = Path(__file__).with_name('test_backend_ci_privacy.py')
        spec = importlib.util.spec_from_file_location('storage_public_fixture', path)
        privacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(privacy)
        fixture = privacy.RunnerPrivacyTests('runTest')
        fixture.setUp()
        try:
            python = fixture.bin / 'python'
            text = python.read_text().replace(
                "print('synthetic source echo: assert ' + repr(marker))",
                "print('SHELL_ONLY_PUBLIC_MARKER')")
            text = text.replace("print('synthetic captured pytest stdout: ' + marker)",
                "print('PYTEST_ONLY_PUBLIC_MARKER')\n"
                "sys.stdout.flush()\n"
                "sys.stdout.buffer.write(b'x' * (16 * 1024 * 1024))\n"
                "sys.stdout.flush()\n"
                "print('PYTEST_ONLY_PUBLIC_TAIL')")
            python.write_text(text)
            result, root = fixture.run_backend('pass')
            self.assertEqual(result.returncode, 0)
            self.assertEqual((result.stdout, result.stderr), ('', ''))
            runner = (root / 'runner.log').read_bytes()
            self.assertIn(b'SHELL_ONLY_PUBLIC_MARKER', runner)
            self.assertNotIn(b'PYTEST_ONLY_PUBLIC', runner)
            retained = (root / 'pytest.log.previous').read_bytes() + (root / 'pytest.log').read_bytes()
            self.assertIn(b'PYTEST_ONLY_PUBLIC_TAIL', retained)
            self.assertNotIn(b'SHELL_ONLY_PUBLIC_MARKER', retained)
            receipt = json.loads((root / 'pytest.log.stream.json').read_text())
            self.assertGreater(receipt['observed_bytes'], 16 * 1024 * 1024)
            self.assertLessEqual(len(retained), module().LOG_BYTES)
            self.assertTrue(receipt['truncated'])
            self.assertFalse(receipt['full_raw_retained'])
            document, status = fixture.metadata(root)
            self.assertEqual(status, 0)
            self.assertEqual(len(document['phases']), 9)
            self.assertEqual(document['coverage']['collected_count'], 3)
            self.assertTrue(document['coverage']['all_collected_completed'])
        finally:
            fixture.doCleanups()

    def test_watcher_never_signals_foreign_process_or_reused_identity(self):
        m = module()
        with mock.patch.object(m, 'process_identity', return_value=(os.getppid()+1, 42)), \
                mock.patch.object(m.os, 'kill') as kill:
            with self.assertRaisesRegex(RuntimeError, 'STORAGE_PROCESS'):
                m.watch('/unused', 999)
            kill.assert_not_called()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            m.prepare(root, reserve_bytes=4096)
            with mock.patch.object(m, 'process_identity', side_effect=[(os.getppid(), 42), (os.getppid(), 43)]), \
                    mock.patch.object(m.os, 'kill') as kill:
                self.assertEqual(m.watch(root, 999), 0)
                kill.assert_not_called()
            self.assertFalse((root / m.RESERVE_NAME).exists())


if __name__ == '__main__':
    unittest.main()
