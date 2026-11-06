"""SYNTHETIC profile-shape checks; no class compilation, runtime or games."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import runtime_profile as P


class SyntheticProfileTests(unittest.TestCase):
    def setUp(self):
        self.base = {"build_id": P.BASE_BUILD_ID, "cwd": "/old", "sessions_dir": "/old/sessions",
                     "argv": ["/usr/bin/bwrap", "--die-with-parent", "--new-session",
                              "--chdir", "/engine", "/jdk/java", "-Xmx2g", "-cp", "/base/classes:/base/engine.jar",
                              "forge.evaluation.NativeHumanWorker", "{session}"]}
        self.identity = {"build_id": P.BASE_BUILD_ID, "runtime_classpath": ["/base/classes", "/base/engine.jar"]}
        self.launch_pin = mock.patch.object(P, "LAUNCH_SHA", P._digest(self.base["argv"]))
        self.launch_pin.start()
        self.addCleanup(self.launch_pin.stop)
        self.digests = {"class_sha256": P.CLASS_SHA, "source_sha256": P.SOURCE_SHA}

    def make(self, base=None, identity=None, shadow="/build/shadow", output="/profile", digests=None):
        return P.derive(self.base if base is None else base, self.identity if identity is None else identity,
                        shadow, output, self.digests if digests is None else digests)

    def test_profile_has_new_identity_and_only_readonly_shadow_classpath_delta(self):
        before = copy.deepcopy(self.base)
        runtime, profile = self.make()
        self.assertEqual(self.base, before)
        self.assertNotEqual(runtime["build_id"], before["build_id"])
        self.assertEqual(profile["runtime_classpath"], ["/build/shadow", *self.identity["runtime_classpath"]])
        argv = runtime["argv"].copy()
        bind = argv.index("--chdir") - 3
        self.assertEqual(argv[bind:bind + 3], ["--ro-bind", "/build/shadow", "/build/shadow"])
        del argv[bind:bind + 3]
        argv[argv.index("-cp") + 1] = before["argv"][before["argv"].index("-cp") + 1]
        self.assertEqual(argv, before["argv"])
        self.assertEqual(runtime["sessions_dir"], "/profile/sessions")
        self.assertEqual(runtime, self.make()[0])

    def test_base_identity_classpath_and_command_shape_must_match(self):
        for mutate in [lambda b: b.update(build_id="b" * 64),
                       lambda b: b["argv"].__setitem__(0, "/bin/sh"),
                       lambda b: b["argv"].remove("--die-with-parent"),
                       lambda b: b["argv"].__setitem__(-1, "/another-session"),
                       lambda b: b["argv"].__setitem__(-3, "/foreign/classes")]:
            base = copy.deepcopy(self.base)
            mutate(base)
            with self.assertRaises(ValueError):
                self.make(base=base)

    def test_candidate_hash_or_unsafe_path_cannot_reuse_profile(self):
        with self.assertRaises(ValueError):
            self.make(digests={**self.digests, "class_sha256": "0" * 64})
        for path in ["relative", "/tmp/../other", "/tmp/colon:entry"]:
            with self.assertRaises(ValueError):
                self.make(shadow=path)

    def test_shadow_cannot_hide_additional_classes_behind_directory_symlink(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            build = root / "build"
            target = build / "shadow/forge/ai/ComputerUtil.class"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"SYNTHETIC; NOT A JAVA CLASS")
            source = build / "source/forge-ai/src/main/java/forge/ai/ComputerUtil.java"
            source.parent.mkdir(parents=True)
            source.write_text("SYNTHETIC; NOT JAVA")
            foreign = root / "foreign"
            foreign.mkdir()
            (build / "shadow/forge/game").symlink_to(foreign, target_is_directory=True)
            runtime, identity = root / "runtime.json", root / "identity.json"
            runtime.write_text(json.dumps(self.base))
            identity.write_text(json.dumps(self.identity))
            with self.assertRaisesRegex(ValueError, "symlink"):
                P.main(runtime, identity, build, root / "output")

    def test_matching_unqualified_base_ids_still_reject(self):
        base, identity = copy.deepcopy(self.base), copy.deepcopy(self.identity)
        base["build_id"] = identity["build_id"] = "b" * 64
        with self.assertRaises(ValueError):
            self.make(base=base, identity=identity)

    def test_changed_jvm_budget_or_late_overmount_rejects(self):
        variants = []
        for before, after in [("/jdk/java", "/foreign/java"), ("-Xmx2g", "-Xmx8g")]:
            base = copy.deepcopy(self.base)
            base["argv"][base["argv"].index(before)] = after
            variants.append(base)
        base = copy.deepcopy(self.base)
        base["argv"][base["argv"].index("--chdir") + 2:base["argv"].index("--chdir") + 2] = ["--ro-bind", "/", "/"]
        variants.append(base)
        for base in variants:
            with self.subTest(argv=base["argv"]):
                with self.assertRaises(ValueError):
                    self.make(base=base)

    def fixture(self, root):
        build = root / "build"
        target = build / "shadow/forge/ai/ComputerUtil.class"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"SYNTHETIC; NOT A JAVA CLASS")
        source = build / "source/forge-ai/src/main/java/forge/ai/ComputerUtil.java"
        source.parent.mkdir(parents=True)
        source.write_text("SYNTHETIC; NOT JAVA")
        runtime, identity = root / "runtime.json", root / "identity.json"
        runtime.write_text(json.dumps(self.base))
        identity.write_text(json.dumps(self.identity))
        return runtime, identity, build

    def test_second_file_failure_does_not_publish_partial_profile(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            real_open = os.open
            def fail_second(path, *a, **kw):
                if Path(path).name == "BUILD-IDENTITY.json":
                    raise OSError("Synthetic second-file failure")
                return real_open(path, *a, **kw)
            with mock.patch.object(P, "CLASS_SHA", hashlib.sha256(b"SYNTHETIC; NOT A JAVA CLASS").hexdigest()), \
                 mock.patch.object(P, "SOURCE_SHA", hashlib.sha256(b"SYNTHETIC; NOT JAVA").hexdigest()), \
                 mock.patch.object(P.os, "open", side_effect=fail_second):
                with self.assertRaises(OSError):
                    P.main(*args, root / "output")
            self.assertFalse((root / "output").exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["build", "identity.json", "runtime.json"])

    def test_success_fsyncs_staging_and_parent_directories(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            modes, real_fsync = [], os.fsync
            def synced(fd):
                modes.append(os.fstat(fd).st_mode)
                real_fsync(fd)
            with mock.patch.object(P, "CLASS_SHA", hashlib.sha256(b"SYNTHETIC; NOT A JAVA CLASS").hexdigest()), \
                 mock.patch.object(P, "SOURCE_SHA", hashlib.sha256(b"SYNTHETIC; NOT JAVA").hexdigest()), \
                 mock.patch.object(P.os, "fsync", side_effect=synced):
                P.main(*args, root / "output")
            self.assertGreaterEqual(sum(stat.S_ISDIR(mode) for mode in modes), 2)
            self.assertEqual(sorted(p.name for p in (root / "output").iterdir()), ["BUILD-IDENTITY.json", "runtime.json"])

    def test_known_mana_bundle_has_its_own_content_identity(self):
        self.assertTrue(callable(getattr(P, "derive_bundle", None)), "Separate pinned bundle derivation is missing")
        sources = {"forge-ai/src/main/java/forge/ai/" + name + ".java": "c" * 64
                   for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilMana"]}
        classes = {"forge/ai/" + name + ".class": "d" * 64
                   for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilCost$1", "ComputerUtilMana"]}
        bundle = {"schema": 1, "sources": sources, "classes": classes}
        runtime, profile = P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bundle)
        self.assertNotEqual(runtime["build_id"], self.make()[0]["build_id"])
        self.assertEqual(profile["overrides"], bundle)
        changed = copy.deepcopy(bundle)
        changed["classes"]["forge/ai/ComputerUtilCost.class"] = "e" * 64
        self.assertNotEqual(runtime["build_id"], P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", changed)[0]["build_id"])
        for bad in [{**bundle, "classes": {**classes, "forge/game/Card.class": "e" * 64}},
                    {**bundle, "sources": {}},
                    {**bundle, "classes": {**classes, "forge/ai/ComputerUtil.class": "BAD"}}]:
            with self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bad)

    def test_bad_bundle_paths_are_rejected_before_any_source_read(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            approval = root / "approval.json"
            approval.write_text(json.dumps({"schema": 1, "sources": {"../forbidden": "0" * 64},
                                            "classes": {"forge/ai/ComputerUtil.class": "0" * 64}}))
            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("No artifact read before approval")):
                with self.assertRaises(ValueError):
                    P.main(*args, root / "output", approval)
            self.assertFalse((root / "output").exists())

    def composed_bundle(self):
        sources = {"forge-ai/src/main/java/forge/ai/" + name + ".java": "c" * 64
                   for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilMana"]}
        classes = {"forge/ai/" + name + ".class": "d" * 64
                   for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilCost$1", "ComputerUtilMana"]}
        sources["tools/engine_evaluation/forge/actor-boundary/ActorBoundary.java"] = "a" * 64
        classes.update({"forge/evaluation/ActorBoundary.class": "b" * 64,
                        "forge/evaluation/ActorBoundary$Pending.class": "e" * 64})
        return {"schema": 2, "sources": sources, "classes": classes}

    def test_composed_actor_boundary_bundle_retains_launch_fence_and_distinct_identity(self):
        bundle = self.composed_bundle()
        before = copy.deepcopy(self.base)
        runtime, profile = P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bundle)
        self.assertEqual(self.base, before)
        self.assertEqual(profile["overrides"], bundle)
        self.assertNotEqual(runtime["build_id"], self.make()[0]["build_id"])
        self.assertEqual(runtime["argv"].count("--ro-bind"), 1)
        changed = copy.deepcopy(bundle)
        changed["classes"]["forge/evaluation/ActorBoundary.class"] = "f" * 64
        self.assertNotEqual(runtime["build_id"], P.derive_bundle(
            self.base, self.identity, "/build/shadow", "/profile", changed)[0]["build_id"])

    def test_composed_bundle_cannot_admit_partial_boundary_or_other_native_classes(self):
        bundle = self.composed_bundle()
        for bad in [
            {**bundle, "schema": True}, {**bundle, "schema": 2.0}, {**bundle, "schema": 3},
            {**bundle, "sources": {k: v for k, v in bundle["sources"].items() if "ActorBoundary" not in k}},
            {**bundle, "classes": {k: v for k, v in bundle["classes"].items() if "$Pending" not in k}},
            {**bundle, "classes": {**bundle["classes"], "forge/game/Game.class": "f" * 64}},
            {**bundle, "schema": 1},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bad)

    def test_composed_bundle_publication_checks_all_adapter_bytes(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-composed-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.composed_bundle()
            for folder, key in [("source", "sources"), ("shadow", "classes")]:
                for relative in bundle[key]:
                    path = build / folder / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(("SYNTHETIC; NOT NATIVE: " + relative).encode())
                    bundle[key][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            approval = root / "approval.json"
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / "output", approval)
            self.assertEqual(json.loads((root / "output/BUILD-IDENTITY.json").read_text())["overrides"], bundle)
            (build / "shadow/forge/evaluation/ActorBoundary$Pending.class").write_bytes(b"SYNTHETIC CHANGED")
            with self.assertRaisesRegex(ValueError, "byte identity"):
                P.main(*args, root / "rejected", approval)
            self.assertFalse((root / "rejected").exists())

    def test_explicit_null_bundle_is_not_single_class_approval(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            approval = root / "approval.json"
            approval.write_text("null")
            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("No artifact read for null approval")):
                with self.assertRaises(ValueError):
                    P.main(*args, root / "output", approval)

    def test_parent_replacement_cannot_redirect_profile_writes(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            parent, foreign = root / "publish", root / "foreign"
            parent.mkdir()
            foreign.mkdir()
            writes, real_mkdir, real_open = [], os.mkdir, os.open
            def swap(path, *a, **kw):
                if Path(path).name.startswith(".output.pending-"):
                    parent.rename(root / "old-parent")
                    parent.symlink_to(foreign, target_is_directory=True)
                return real_mkdir(path, *a, **kw)
            def observed(path, flags, *a, **kw):
                if flags & os.O_CREAT and Path(path).is_absolute() and Path(path).resolve().is_relative_to(foreign):
                    writes.append(str(path))
                return real_open(path, flags, *a, **kw)
            with mock.patch.object(P, "CLASS_SHA", hashlib.sha256(b"SYNTHETIC; NOT A JAVA CLASS").hexdigest()), \
                 mock.patch.object(P, "SOURCE_SHA", hashlib.sha256(b"SYNTHETIC; NOT JAVA").hexdigest()), \
                 mock.patch.object(P.os, "mkdir", side_effect=swap), \
                 mock.patch.object(P.os, "open", side_effect=observed):
                with self.assertRaises((OSError, ValueError)):
                    P.main(*args, parent / "output")
            self.assertEqual(writes, [], "Profile publication wrote into a replacement parent")
            self.assertEqual(list(foreign.iterdir()), [])

    def test_approved_bundle_files_must_match_before_atomic_publication(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            build = args[2]
            sources, classes = {}, {}
            for stem in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilMana"]:
                relative = "forge-ai/src/main/java/forge/ai/" + stem + ".java"
                target = build / "source" / relative
                target.write_text("SYNTHETIC SOURCE " + stem)
                sources[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
            for stem in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilCost$1", "ComputerUtilMana"]:
                relative = "forge/ai/" + stem + ".class"
                target = build / "shadow" / relative
                target.write_text("SYNTHETIC CLASS " + stem)
                classes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
            bundle = {"schema": 1, "sources": sources, "classes": classes}
            approval = root / "approval.json"
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / "output", approval)
            published = json.loads((root / "output/BUILD-IDENTITY.json").read_text())
            self.assertEqual(published["overrides"], bundle)
            (build / "shadow/forge/ai/ComputerUtilCost.class").write_text("CHANGED")
            with self.assertRaisesRegex(ValueError, "byte identity"):
                P.main(*args, root / "second-output", approval)
            self.assertFalse((root / "second-output").exists())

    def test_racing_existing_output_directory_is_not_replaced(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            real_mkdir = os.mkdir
            def raced(*a, **kw):
                if Path(a[0]).name.startswith(".output.pending-"):
                    real_mkdir(root / "output")
                return real_mkdir(*a, **kw)
            with mock.patch.object(P, "CLASS_SHA", hashlib.sha256(b"SYNTHETIC; NOT A JAVA CLASS").hexdigest()), \
                 mock.patch.object(P, "SOURCE_SHA", hashlib.sha256(b"SYNTHETIC; NOT JAVA").hexdigest()), \
                 mock.patch.object(P.os, "mkdir", side_effect=raced):
                with self.assertRaises(FileExistsError):
                    P.main(*args, root / "output")
            self.assertEqual(list((root / "output").iterdir()), [])
            self.assertFalse(list(root.glob(".output.pending-*")))

    def test_preexisting_staging_directory_is_never_cleaned(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            stage = root / (".output.pending-" + "0" * 32)
            stage.mkdir()
            with mock.patch.object(P, "CLASS_SHA", hashlib.sha256(b"SYNTHETIC; NOT A JAVA CLASS").hexdigest()), \
                 mock.patch.object(P, "SOURCE_SHA", hashlib.sha256(b"SYNTHETIC; NOT JAVA").hexdigest()), \
                 mock.patch.object(P.uuid, "uuid4", return_value=mock.Mock(hex="0" * 32)):
                with self.assertRaises(FileExistsError):
                    P.main(*args, root / "output")
            self.assertTrue(stage.is_dir())


if __name__ == "__main__":
    unittest.main()
