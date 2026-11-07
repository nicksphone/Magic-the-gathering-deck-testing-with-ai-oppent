"""SYNTHETIC private-repository checks, not native games or cold restores."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import native_forge_persistence as P

FIXTURE = Path(__file__).resolve().parents[2] / "tools/engine_evaluation/forge/stdio/tests/test_checkpoint_store.py"
spec = importlib.util.spec_from_file_location("synthetic_native_checkpoint", FIXTURE)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
SID, CAP, BUILD = "1" * 32, b"a" * 32, "b" * 64


def record():
    return {"public": {"engine": "forge", "session_id": SID, "sequence": 7,
            "status": "suspended", "actor_id": 17, "state": {"actor_id": 17},
            "question": None, "info": {}, "last_answer": None, "result": None, "error": None},
            "actions": {}, "invocations": {}, "last_action": None,
            "controls": {"save-1": {"operation": "checkpoint", "fingerprint": "c" * 64}},
            "start": {"key": "original-start", "fingerprint": "d" * 64}}


class SyntheticNativeSaveRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-native-save-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.repo = P.NativeSaves(self.runtime, BUILD)
        self.addCleanup(self.repo.release)
        self.snapshot = self.root / "CHECKPOINT.json"
        self.snapshot.write_text(json.dumps(fixture.synthetic_checkpoint()))

    def save(self, value=None):
        return self.repo.publish(SID, CAP, self.snapshot, record() if value is None else value)

    def test_private_hash_verified_generation_roundtrip(self):
        meta, checkpoint = self.save()
        other = P.NativeSaves(self.runtime, BUILD)
        loaded, restored = other.load(SID, CAP)
        self.assertEqual((loaded, restored), (meta, checkpoint))
        self.assertEqual(restored, fixture.synthetic_checkpoint())
        self.assertEqual(meta["capability_hash"], CAP.hex())
        path = self.runtime / (".saved-" + SID)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((path / "SESSION.json").stat().st_mode), 0o600)
        self.assertNotIn('"tokens"', (path / "SESSION.json").read_text())

    def test_wrong_capability_is_not_found_before_build_check(self):
        self.save()
        for cap in [b"x" * 32, b"", b"a"]:
            with self.assertRaises(P.SaveError) as error:
                P.NativeSaves(self.runtime, "e" * 64).load(SID, cap)
            self.assertEqual(error.exception.code, "not_found")
        with self.assertRaises(P.SaveError) as error:
            P.NativeSaves(self.runtime, "e" * 64).load(SID, CAP)
        self.assertEqual(error.exception.code, "build_mismatch")

    def test_missing_and_unsafe_session_ids_do_not_touch_foreign_paths(self):
        for sid in [SID, "../elsewhere", "A" * 32, "1/" + SID, "", None]:
            with self.assertRaises(P.SaveError):
                self.repo.load(sid, CAP)
        self.assertEqual(list(self.runtime.iterdir()), [])

    def test_corrupt_checkpoint_hash_rejects_without_rewriting(self):
        meta, _ = self.save()
        path = self.runtime / (".saved-" + SID) / meta["checkpoint"] / "CHECKPOINT.json"
        path.write_text("{}")
        with self.assertRaises(P.SaveError):
            self.repo.load(SID, CAP)
        self.assertEqual(path.read_text(), "{}")

    def test_symlink_saved_root_and_metadata_reject(self):
        outside = self.root / "foreign"
        outside.mkdir()
        target = self.runtime / (".saved-" + SID)
        target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(P.SaveError):
            self.save()
        self.assertEqual(list(outside.iterdir()), [])
        target.unlink()
        self.save()
        metadata = target / "SESSION.json"
        original = metadata.read_bytes()
        metadata.unlink()
        foreign = outside / "unchanged"
        foreign.write_bytes(original)
        metadata.symlink_to(foreign)
        with self.assertRaises(P.SaveError):
            self.repo.load(SID, CAP)
        self.assertEqual(foreign.read_bytes(), original)

    def test_metadata_unknown_duplicate_nonfinite_or_wrong_type_rejects(self):
        self.save()
        path = self.runtime / (".saved-" + SID) / "SESSION.json"
        raw = path.read_text()
        variants = [raw[:-1] + ',"unknown":null}',
                    raw[:-1] + ',"schema":1}', raw.replace('"sequence":7', '"sequence":true'),
                    raw.replace('"sequence":7', '"sequence":NaN')]
        for changed in variants:
            self.assertNotEqual(changed, raw)
            path.write_text(changed)
            with self.assertRaises(P.SaveError):
                self.repo.load(SID, CAP)
        path.write_text(raw)

    def test_failed_new_metadata_publication_preserves_previous_save(self):
        before, checkpoint = self.save()
        value = record()
        value["public"]["sequence"] = 8
        with mock.patch.object(P.os, "replace", side_effect=OSError("SYNTHETIC replace failure")):
            with self.assertRaises(P.SaveError):
                self.save(value)
        self.assertEqual(self.repo.load(SID, CAP), (before, checkpoint))

    def test_result_or_abandonment_update_retains_exact_checkpoint(self):
        before, saved = self.save()
        value = record()
        value["public"]["status"] = "aborted"
        value["public"]["sequence"] += 1
        after = self.repo.update(SID, CAP, value)
        current, checkpoint = self.repo.load(SID, CAP)
        self.assertEqual(after, current)
        self.assertEqual(checkpoint, saved)
        self.assertEqual(before["checkpoint"], after["checkpoint"])
        self.assertEqual(current["record"]["public"]["status"], "aborted")

    def test_runtime_lease_excludes_a_second_manager_until_release(self):
        other = P.NativeSaves(self.runtime, BUILD)
        self.addCleanup(other.release)
        self.repo.acquire()
        self.repo.acquire()
        with self.assertRaises(P.SaveError) as error:
            other.acquire()
        self.assertEqual(error.exception.code, "runtime_owned")
        self.repo.release()
        other.acquire()

    def test_bad_receipt_and_record_cannot_be_published(self):
        for mutate in [lambda r: r.update(unknown=None),
                       lambda r: r["public"].update(sequence=True),
                       lambda r: r["public"].update(question={"tokens": []}),
                       lambda r: r["controls"].update(x={"operation": "shell", "fingerprint": "c" * 64}),
                       lambda r: r["invocations"].update({"0": "missing"})]:
            value = record()
            mutate(value)
            with self.assertRaises(P.SaveError):
                self.save(value)

    def test_existing_session_cannot_be_rebound_to_another_capability(self):
        before, checkpoint = self.save()
        files = sorted(x.name for x in (self.runtime / (".saved-" + SID)).iterdir())
        with self.assertRaises(P.SaveError) as error:
            self.repo.publish(SID, b"x" * 32, self.snapshot, record())
        self.assertEqual(error.exception.code, "not_found")
        self.assertEqual(self.repo.load(SID, CAP), (before, checkpoint))
        self.assertEqual(sorted(x.name for x in (self.runtime / (".saved-" + SID)).iterdir()), files)

    def test_after_replace_fsync_failure_is_marked_committed_not_old_save(self):
        before, old_checkpoint = self.save()
        value = record()
        value["public"]["sequence"] = 8
        replaced = []
        real_replace, real_sync = P.os.replace, P.os.fsync

        def replace(*args, **kwargs):
            result = real_replace(*args, **kwargs)
            replaced.append(True)
            return result

        def sync(fd):
            if replaced:
                raise OSError("SYNTHETIC post-commit directory sync failure")
            return real_sync(fd)

        with mock.patch.object(P.os, "replace", side_effect=replace), mock.patch.object(P.os, "fsync", side_effect=sync):
            with self.assertRaises(P.SaveError) as error:
                self.save(value)
        self.assertTrue(error.exception.committed)
        after, _ = self.repo.load(SID, CAP)
        self.assertEqual(after["record"]["public"]["sequence"], 8)
        original = P.checkpoints.load_checkpoint(
            self.runtime / (".saved-" + SID) / before["checkpoint"], build_id=BUILD)
        self.assertEqual(original, old_checkpoint)

    def test_hardlinked_or_overbroad_metadata_is_not_loaded(self):
        self.save()
        path = self.runtime / (".saved-" + SID) / "SESSION.json"
        other = self.root / "alias"
        os.link(path, other)
        with self.assertRaises(P.SaveError):
            self.repo.load(SID, CAP)
        other.unlink()
        path.chmod(0o644)
        with self.assertRaises(P.SaveError):
            self.repo.load(SID, CAP)

    def test_oversized_metadata_is_rejected_before_json_loading(self):
        self.save()
        path = self.runtime / (".saved-" + SID) / "SESSION.json"
        path.write_bytes(b"x" * (P._LIMIT + 1))
        with mock.patch.object(P.json, "loads", side_effect=AssertionError("Must not parse oversized metadata")):
            with self.assertRaises(P.SaveError):
                self.repo.load(SID, CAP)

    def test_restart_epochs_are_durable_monotonic_and_javascript_safe(self):
        first = self.repo.reserve_epoch()
        second = self.repo.reserve_epoch()
        self.assertEqual(second - first, 1_000_000)
        self.repo.release()
        other = P.NativeSaves(self.runtime, BUILD)
        self.addCleanup(other.release)
        third = other.reserve_epoch()
        self.assertEqual(third - second, 1_000_000)
        self.assertLess(third, 2**53)
        self.assertEqual(stat.S_IMODE((self.runtime / "EPOCH.json").stat().st_mode), 0o600)

    def test_epoch_corruption_and_symlink_fail_closed(self):
        self.repo.reserve_epoch()
        path = self.runtime / "EPOCH.json"
        for raw in [b'{"epoch":true}', b'{"epoch":-1}', b'{"epoch":1,"epoch":2}',
                    b'{"epoch":1,"unknown":0}', b'{"epoch":NaN}', b"x" * 129]:
            path.write_bytes(raw)
            with self.assertRaises(P.SaveError):
                self.repo.reserve_epoch()
        path.unlink()
        outside = self.root / "foreign-epoch"
        outside.write_text('{"epoch":1}')
        path.symlink_to(outside)
        with self.assertRaises(P.SaveError):
            self.repo.reserve_epoch()
        self.assertEqual(outside.read_text(), '{"epoch":1}')

    def test_saved_inventory_probe_does_not_create_or_read_games(self):
        self.assertFalse(self.repo.has_saves())
        self.assertEqual(list(self.runtime.iterdir()), [])
        self.save()
        self.assertTrue(self.repo.has_saves())

    def test_root_symlink_ancestor_is_rejected_before_directory_creation(self):
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        repo = P.NativeSaves(alias / "must-not-be-created", BUILD)
        self.addCleanup(repo.release)
        with self.assertRaises(P.SaveError):
            repo.acquire()
        self.assertEqual(list(outside.iterdir()), [])

    def test_failed_publications_do_not_accumulate_unreferenced_generations(self):
        before, saved = self.save()
        path = self.runtime / (".saved-" + SID)
        for _ in range(3):
            with mock.patch.object(P.os, "replace", side_effect=OSError("SYNTHETIC publication failure")):
                with self.assertRaises(P.SaveError):
                    self.save()
        generations = [x.name for x in path.iterdir() if x.is_dir()]
        self.assertEqual(generations, [before["checkpoint"]])
        self.assertEqual(self.repo.load(SID, CAP), (before, saved))

    def test_successful_save_retention_keeps_current_and_previous_only(self):
        saved = []
        for sequence in range(7, 12):
            value = record()
            value["public"]["sequence"] = sequence
            meta, _ = self.save(value)
            saved.append(meta["checkpoint"])
        path = self.runtime / (".saved-" + SID)
        self.assertEqual({x.name for x in path.iterdir() if x.is_dir()}, set(saved[-2:]))
        self.assertEqual(self.repo.load(SID, CAP)[0]["checkpoint"], saved[-1])


if __name__ == "__main__":
    unittest.main()
