"""Real unprivileged filesystem permissions; no SQL, servers or containers."""
from contextlib import closing, contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


FILE = Path(__file__).resolve().parents[3] / 'ops/caddy/run.py'
spec = importlib.util.spec_from_file_location('readonly_runtime_operator', FILE)
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


def inventory(root):
    return {
        str(path.relative_to(root)): (
            path.stat().st_mode & 0o777,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
        for path in [root, *root.rglob('*')]
    }


@contextmanager
def fixture(readonly=True):
    if os.geteuid() == 0:
        raise AssertionError('A root process cannot certify unprivileged write permission')
    previous = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'public'
            nested = source / 'backend/card_data/nested'
            nested.mkdir(parents=True)
            (source / 'backend/main.py').write_text('# Protocol source, never imported.\n')
            (nested / 'fixture.json').write_text('{"schema":1}\n')
            for path in source.rglob('*'):
                path.chmod(0o555 if readonly and path.is_dir() else 0o444 if readonly else 0o700 if path.is_dir() else 0o600)
            source.chmod(0o555 if readonly else 0o700)
            try:
                with patch.object(operator, 'SOURCE', source):
                    yield source, root / 'runtime'
            finally:
                # Restore only disposable fixture directories for normal cleanup.
                for path in [source, *source.rglob('*')]:
                    if path.is_dir():
                        path.chmod(0o700)
                runtime = root / 'runtime'
                if runtime.exists():
                    for path in [runtime, *runtime.rglob('*')]:
                        if path.is_dir():
                            path.chmod(0o700)
    finally:
        os.umask(previous)


class ReadonlyRuntimeTests(unittest.TestCase):
    def test_private_runtime_accepts_real_owner_writes_after_readonly_source_copy(self):
        with fixture() as (source, runtime):
            before = inventory(source)
            with closing(operator.prepare({'runtime': runtime})):
                created = []
                for directory in (runtime / 'backend', runtime / 'backend/card_data/nested'):
                    probe = directory / 'owner-write-probe'
                    try:
                        probe.write_bytes(b'private runtime probe')
                    except PermissionError:
                        created.append(False)
                    else:
                        created.append(True)
                        probe.unlink()
                self.assertEqual(created, [True, True], 'Private runtime directories must not inherit source write denial')
            self.assertEqual(inventory(source), before)

    def test_source_modes_and_bytes_stay_readonly_and_runtime_code_is_unchanged(self):
        with fixture() as (source, runtime):
            before = inventory(source)
            with closing(operator.prepare({'runtime': runtime})):
                self.assertEqual(inventory(source), before)
                for path in (source / 'backend').rglob('*'):
                    if path.is_file():
                        copied = runtime / 'backend' / path.relative_to(source / 'backend')
                        self.assertEqual(copied.read_bytes(), path.read_bytes())
                        self.assertEqual(copied.stat().st_mode & 0o222, 0)

    def test_existing_managed_readonly_runtime_recovers_without_source_changes(self):
        with fixture() as (source, runtime):
            before = inventory(source)
            with closing(operator.prepare({'runtime': runtime})):
                pass
            # Reproduce the existing managed layout left by an earlier launch.
            for directory in [runtime / 'backend', *(runtime / 'backend').rglob('*')]:
                if directory.is_dir():
                    directory.chmod(0o555)
            with closing(operator.prepare({'runtime': runtime})):
                probe = runtime / 'backend/restart-owner-write-probe'
                try:
                    probe.write_bytes(b'private restart probe')
                except PermissionError:
                    created = False
                else:
                    created = True
                    probe.unlink()
                self.assertTrue(created, 'Existing managed runtime must recover private directory writes')
            self.assertEqual(inventory(source), before)

    def test_restart_preserves_existing_private_data(self):
        with fixture(readonly=False) as (source, runtime):
            with closing(operator.prepare({'runtime': runtime})):
                data = runtime / 'backend/mtg_lab.db'
                data.write_bytes(b'opaque filesystem fixture, not an executed SQLite database')
            before = data.read_bytes(), data.stat().st_ino
            with closing(operator.prepare({'runtime': runtime})):
                self.assertEqual((data.read_bytes(), data.stat().st_ino), before)

    def test_changed_source_still_rejects_restart_without_rewriting_runtime(self):
        with fixture(readonly=False) as (source, runtime):
            with closing(operator.prepare({'runtime': runtime})):
                pass
            before = inventory(runtime)
            (source / 'backend/main.py').write_text('# Changed source must not silently replace runtime.\n')
            with self.assertRaises(ValueError):
                operator.prepare({'runtime': runtime})
            self.assertEqual(inventory(runtime), before)
