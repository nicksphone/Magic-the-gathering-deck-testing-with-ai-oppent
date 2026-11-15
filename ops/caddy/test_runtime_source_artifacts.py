"""Real inventory/prepare calls with disposable files; no SQL, servers or secrets."""
from contextlib import contextmanager
from contextvars import ContextVar
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_artifact_operator", HERE / "run.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
FORBIDDEN_READS = ContextVar("operator_fixture_forbidden_reads", default=frozenset())
BACKUP = "mtg_lab.db.before-capacity-0123456789abcdef0123456789abcdef.db"
LOCK = "mtg_lab.db.capacity-owner.lock"


class ArtifactContentsRead(AssertionError):
    pass


def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        if os.fsdecode(args[0]) in FORBIDDEN_READS.get():
            raise ArtifactContentsRead("Inventory opened a forbidden synthetic artifact")


sys.addaudithook(audit)


@contextmanager
def forbid_contents(*paths):
    token = FORBIDDEN_READS.set(frozenset(str(path) for path in paths))
    try:
        yield
    finally:
        FORBIDDEN_READS.reset(token)


class SourceArtifactInventory(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.temp = tempfile.TemporaryDirectory(prefix="mtg-operator-source-artifacts-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.backend = self.source / "backend"
        self.backend.mkdir(parents=True)
        (self.backend / "module.py").write_text("# Explicit inert source fixture.\n")
        (self.backend / "fixture.json").write_text('{"fixture": true}\n')
        self.old_source = operator.SOURCE
        operator.SOURCE = self.source
        self.addCleanup(setattr, operator, "SOURCE", self.old_source)

    def artifact(self, root, name):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Synthetic artifact: never real owner state or a SQLite database.\n")
        return path

    def test_source_runtime_artifacts_reject_before_any_content_read(self):
        for name in ("mtg_lab.db", "mtg_lab.db-wal", "mtg_lab.db-shm",
                     "mtg_lab.db-journal", LOCK, BACKUP):
            with self.subTest(name=name):
                path = self.artifact(self.backend, name)
                try:
                    with forbid_contents(path), self.assertRaises(ValueError):
                        operator.inventory(self.backend)
                finally:
                    path.unlink()

    def test_unrecognized_owner_lock_names_never_get_read_in_either_inventory(self):
        for name in ("nested/" + LOCK, "unrecognized.capacity-owner.lock"):
            path = self.artifact(self.backend, name)
            try:
                for runtime in (False, True):
                    with self.subTest(name=name, runtime=runtime):
                        with forbid_contents(path), self.assertRaises(ValueError):
                            operator.inventory(self.backend, runtime=runtime)
            finally:
                path.unlink()

    def test_prepare_rejects_source_artifacts_before_copy_and_releases_lease(self):
        for index, name in enumerate((LOCK, BACKUP)):
            runtime = self.root / f"runtime-{index}"
            with self.subTest(name=name):
                path = self.artifact(self.backend, name)
                try:
                    with forbid_contents(path), self.assertRaises(ValueError):
                        operator.prepare({"runtime": runtime})
                    self.assertFalse((runtime / "backend").exists())
                    self.assertFalse((runtime / "source.sha256").exists())
                finally:
                    path.unlink()
                # A corrected source can prepare against the same runtime: no leaked lease.
                with operator.prepare({"runtime": runtime}):
                    self.assertTrue((runtime / "backend/module.py").is_file())

    def test_recognized_runtime_artifacts_still_allow_real_prepare_restart_without_reads(self):
        runtime = self.root / "runtime"
        with operator.prepare({"runtime": runtime}):
            pass
        real = runtime / "backend"
        artifacts = [self.artifact(real, name) for name in (LOCK, BACKUP)]
        with forbid_contents(*artifacts), operator.prepare({"runtime": runtime}):
            self.assertEqual(operator.inventory(real, runtime=True), operator.inventory(self.backend))

    def test_mutable_runtime_subtrees_keep_their_content_free_exemptions(self):
        (self.backend / "card_data").mkdir()
        before = operator.inventory(self.backend, runtime=True)
        artifacts = [self.artifact(self.backend, prefix + "/unrecognized.capacity-owner.lock")
                     for prefix in ("diagnostics", "training_runs", "card_data/image_cache")]
        with forbid_contents(*artifacts):
            self.assertEqual(operator.inventory(self.backend, runtime=True), before)


if __name__ == "__main__":
    unittest.main()
