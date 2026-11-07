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

    def tactical_bundle(self):
        bundle = self.composed_bundle()
        bundle["schema"] = 3
        bundle["sources"]["forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java"] = "f" * 64
        bundle["classes"]["forge/ai/ability/DamageDealAi.class"] = "a" * 64
        return bundle

    def test_tactical_bundle_requires_the_exact_complete_seven_class_composition(self):
        bundle = self.tactical_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bundle)
        self.assertEqual(profile["overrides"], bundle)
        self.assertNotEqual(runtime["build_id"], P.derive_bundle(
            self.base, self.identity, "/build/shadow", "/profile", self.composed_bundle())[0]["build_id"])
        for bad in [
            {**bundle, "schema": 3.0},
            {**bundle, "sources": {k: v for k, v in bundle["sources"].items() if "DamageDealAi" not in k}},
            {**bundle, "classes": {k: v for k, v in bundle["classes"].items() if "DamageDealAi" not in k}},
            {**bundle, "classes": {**bundle["classes"], "forge/game/Game.class": "d" * 64}},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bad)

    def test_tactical_publication_rejects_changed_damage_class_bytes(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-tactical-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.tactical_bundle()
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
            (build / "shadow/forge/ai/ability/DamageDealAi.class").write_bytes(b"SYNTHETIC CHANGED")
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

    def pressure_bundle(self):
        bundle = self.tactical_bundle()
        bundle["schema"] = 4
        bundle["sources"]["forge-ai/src/main/java/forge/ai/ability/DamageAiBase.java"] = "1" * 64
        bundle["classes"]["forge/ai/ability/DamageAiBase.class"] = "2" * 64
        return bundle

    def test_pressure_bundle_requires_exact_six_sources_and_eight_classes(self):
        bundle = self.pressure_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bundle)
        self.assertEqual(profile["overrides"], bundle)
        self.assertEqual(len(bundle["sources"]), 6)
        self.assertEqual(len(bundle["classes"]), 8)
        self.assertNotEqual(runtime["build_id"], P.derive_bundle(
            self.base, self.identity, "/build/shadow", "/profile", self.tactical_bundle())[0]["build_id"])
        for bad in [
            {**bundle, "schema": 4.0}, {**bundle, "schema": 3},
            {**bundle, "sources": {k: v for k, v in bundle["sources"].items() if "DamageAiBase" not in k}},
            {**bundle, "classes": {k: v for k, v in bundle["classes"].items() if "DamageAiBase" not in k}},
            {**bundle, "classes": {**bundle["classes"], "forge/game/Game.class": "3" * 64}},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bad)

    def test_pressure_publication_rejects_changed_shared_policy_bytes(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-pressure-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.pressure_bundle()
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
            for folder, relative in [
                ("source", "forge-ai/src/main/java/forge/ai/ability/DamageAiBase.java"),
                ("shadow", "forge/ai/ability/DamageAiBase.class"),
            ]:
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b"SYNTHETIC CHANGED")
                with self.assertRaisesRegex(ValueError, "byte identity"):
                    P.main(*args, root / ("rejected-" + folder), approval)
                self.assertFalse((root / ("rejected-" + folder)).exists())
                path.write_bytes(original)

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

    def draw_bundle(self):
        bundle = self.pressure_bundle()
        bundle["schema"] = 5
        bundle["sources"]["forge-ai/src/main/java/forge/ai/ability/DrawAi.java"] = "3" * 64
        bundle["classes"]["forge/ai/ability/DrawAi.class"] = "4" * 64
        return bundle

    def test_draw_bundle_requires_exact_seven_sources_and_nine_classes(self):
        bundle = self.draw_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bundle)
        self.assertEqual(profile["overrides"], bundle)
        self.assertEqual((len(bundle["sources"]), len(bundle["classes"])), (7, 9))
        self.assertNotEqual(runtime["build_id"], P.derive_bundle(
            self.base, self.identity, "/build/shadow", "/profile", self.pressure_bundle())[0]["build_id"])
        for bad in [
            {**bundle, "schema": 5.0}, {**bundle, "schema": 4},
            {**bundle, "sources": {k: v for k, v in bundle["sources"].items() if "DrawAi" not in k}},
            {**bundle, "classes": {k: v for k, v in bundle["classes"].items() if "DrawAi" not in k}},
            {**bundle, "classes": {**bundle["classes"], "forge/game/Game.class": "5" * 64}},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, "/build/shadow", "/profile", bad)

    def test_draw_publication_rejects_changed_draw_bytes_before_publication(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-draw-profile-") as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.draw_bundle()
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
            for folder, relative in [("shadow", "forge/ai/ability/DrawAi.class"),
                                     ("source", "forge-ai/src/main/java/forge/ai/ability/DrawAi.java")]:
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b"SYNTHETIC CHANGED")
                with self.assertRaisesRegex(ValueError, "byte identity"):
                    P.main(*args, root / ("rejected-" + folder), approval)
                self.assertFalse((root / ("rejected-" + folder)).exists())
                path.write_bytes(original)

    def worker_bundle(self):
        bundle = self.draw_bundle()
        bundle['schema'] = 6
        bundle['sources']['tools/engine_evaluation/forge/stdio/NativeHumanWorker.java'] = '6' * 64
        for suffix in ('', '$1', '$2', '$3', '$Answer', '$Input'):
            bundle['classes']['forge/evaluation/NativeHumanWorker' + suffix + '.class'] = '7' * 64
        return bundle

    def test_worker_bundle_requires_complete_fifteen_class_composition_and_new_identity(self):
        bundle = self.worker_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bundle)
        self.assertEqual(profile['overrides'], bundle)
        self.assertEqual((len(bundle['sources']), len(bundle['classes'])), (8, 15))
        self.assertNotEqual(runtime['build_id'], P.derive_bundle(
            self.base, self.identity, '/build/shadow', '/profile', self.draw_bundle())[0]['build_id'])
        for bad in (
            {**bundle, 'schema': 6.0}, {**bundle, 'schema': 5},
            {**bundle, 'sources': {k: v for k, v in bundle['sources'].items() if 'NativeHumanWorker' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if '$Input' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if 'DrawAi' not in k}},
            {**bundle, 'classes': {**bundle['classes'], 'forge/evaluation/NativeHumanWorker$4.class': '8' * 64}},
            {**bundle, 'classes': {**bundle['classes'], 'forge/game/Game.class': '8' * 64}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_worker_publication_checks_all_six_class_payloads_and_source(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-worker-profile-') as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.worker_bundle()
            for folder, key in [('source', 'sources'), ('shadow', 'classes')]:
                for relative in bundle[key]:
                    path = build / folder / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(('SYNTHETIC; NOT NATIVE: ' + relative).encode())
                    bundle[key][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            approval = root / 'approval.json'
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / 'output', approval)
            self.assertEqual(json.loads((root / 'output/BUILD-IDENTITY.json').read_text())['overrides'], bundle)
            cases = [('shadow', name) for name in bundle['classes'] if 'NativeHumanWorker' in name]
            cases.append(('source', 'tools/engine_evaluation/forge/stdio/NativeHumanWorker.java'))
            for index, (folder, relative) in enumerate(cases):
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b'SYNTHETIC CHANGED')
                output = root / ('rejected-' + str(index))
                with self.assertRaisesRegex(ValueError, 'byte identity'):
                    P.main(*args, output, approval)
                self.assertFalse(output.exists())
                path.write_bytes(original)

    def chalice_bundle(self):
        bundle = self.worker_bundle()
        bundle['schema'] = 7
        bundle['sources']['forge-ai/src/main/java/forge/ai/ability/PermanentAi.java'] = '8' * 64
        bundle['classes']['forge/ai/ability/PermanentAi.class'] = '9' * 64
        return bundle

    def test_chalice_bundle_requires_all_prior_classes_and_distinct_identity(self):
        bundle = self.chalice_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bundle)
        self.assertEqual(profile['overrides'], bundle)
        self.assertEqual((len(bundle['sources']), len(bundle['classes'])), (9, 16))
        self.assertNotEqual(runtime['build_id'], P.derive_bundle(
            self.base, self.identity, '/build/shadow', '/profile', self.worker_bundle())[0]['build_id'])
        for bad in (
            {**bundle, 'schema': 7.0}, {**bundle, 'schema': 6},
            {**bundle, 'sources': {k: v for k, v in bundle['sources'].items() if 'PermanentAi' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if 'PermanentAi' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if '$Input' not in k}},
            {**bundle, 'classes': {**bundle['classes'], 'forge/game/Game.class': 'a' * 64}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_chalice_publication_checks_new_source_and_class_bytes(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-chalice-profile-') as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.chalice_bundle()
            for folder, key in [('source', 'sources'), ('shadow', 'classes')]:
                for relative in bundle[key]:
                    path = build / folder / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(('SYNTHETIC; NOT NATIVE: ' + relative).encode())
                    bundle[key][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            approval = root / 'approval.json'
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / 'output', approval)
            self.assertEqual(json.loads((root / 'output/BUILD-IDENTITY.json').read_text())['overrides'], bundle)
            for folder, relative in (
                ('source', 'forge-ai/src/main/java/forge/ai/ability/PermanentAi.java'),
                ('shadow', 'forge/ai/ability/PermanentAi.class'),
            ):
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b'SYNTHETIC CHANGED')
                output = root / ('rejected-' + folder)
                with self.assertRaisesRegex(ValueError, 'byte identity'):
                    P.main(*args, output, approval)
                self.assertFalse(output.exists())
                path.write_bytes(original)

    def counter_bundle(self):
        bundle = self.chalice_bundle()
        bundle['schema'] = 8
        bundle['sources']['forge-ai/src/main/java/forge/ai/ability/CounterAi.java'] = 'a' * 64
        bundle['classes']['forge/ai/ability/CounterAi.class'] = 'b' * 64
        return bundle

    def test_counter_bundle_requires_complete_ten_source_seventeen_class_prefix(self):
        bundle = self.counter_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bundle)
        self.assertEqual(profile['overrides'], bundle)
        self.assertEqual((len(bundle['sources']), len(bundle['classes'])), (10, 17))
        self.assertNotEqual(runtime['build_id'], P.derive_bundle(
            self.base, self.identity, '/build/shadow', '/profile', self.chalice_bundle())[0]['build_id'])
        for bad in (
            {**bundle, 'schema': 8.0}, {**bundle, 'schema': 7},
            {**bundle, 'sources': {k: v for k, v in bundle['sources'].items() if 'CounterAi' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if 'CounterAi' not in k}},
            {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if '$Input' not in k}},
            {**bundle, 'classes': {**bundle['classes'], 'forge/ai/ability/CounterAi$Extra.class': 'c' * 64}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_counter_publication_checks_new_policy_source_and_class(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-counter-profile-') as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.counter_bundle()
            for folder, key in [('source', 'sources'), ('shadow', 'classes')]:
                for relative in bundle[key]:
                    path = build / folder / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(('SYNTHETIC; NOT NATIVE: ' + relative).encode())
                    bundle[key][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            approval = root / 'approval.json'
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / 'output', approval)
            self.assertEqual(json.loads((root / 'output/BUILD-IDENTITY.json').read_text())['overrides'], bundle)
            for folder, relative in (
                ('source', 'forge-ai/src/main/java/forge/ai/ability/CounterAi.java'),
                ('shadow', 'forge/ai/ability/CounterAi.class'),
            ):
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b'SYNTHETIC CHANGED')
                output = root / ('rejected-' + folder)
                with self.assertRaisesRegex(ValueError, 'byte identity'):
                    P.main(*args, output, approval)
                self.assertFalse(output.exists())
                path.write_bytes(original)

    def sacrifice_bundle(self):
        bundle = self.counter_bundle()
        bundle['schema'] = 9
        for name in ('SpellAbilityAi', 'AiController'):
            bundle['sources']['forge-ai/src/main/java/forge/ai/' + name + '.java'] = 'c' * 64
        for name in ('SpellAbilityAi', 'AiController', 'AiController$1'):
            bundle['classes']['forge/ai/' + name + '.class'] = 'd' * 64
        return bundle

    def test_sacrifice_bundle_requires_complete_twelve_source_twenty_class_prefix(self):
        bundle = self.sacrifice_bundle()
        runtime, profile = P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bundle)
        self.assertEqual(profile['overrides'], bundle)
        self.assertEqual((len(bundle['sources']), len(bundle['classes'])), (12, 20))
        self.assertNotEqual(runtime['build_id'], P.derive_bundle(
            self.base, self.identity, '/build/shadow', '/profile', self.counter_bundle())[0]['build_id'])
        bad_bundles = [{**bundle, 'schema': 9.0}, {**bundle, 'schema': 8}]
        for group in ('sources', 'classes'):
            for missing in bundle[group]:
                bad_bundles.append({**bundle, group: {k: v for k, v in bundle[group].items() if k != missing}})
        bad_bundles.append({**bundle, 'classes': {**bundle['classes'], 'forge/ai/AiController$Extra.class': 'e' * 64}})
        for bad in bad_bundles:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_sacrifice_publication_checks_both_sources_and_all_three_classes(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-sacrifice-profile-') as name:
            root = Path(name)
            args = self.fixture(root)
            build, bundle = args[2], self.sacrifice_bundle()
            for folder, key in [('source', 'sources'), ('shadow', 'classes')]:
                for relative in bundle[key]:
                    path = build / folder / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(('SYNTHETIC; NOT NATIVE: ' + relative).encode())
                    bundle[key][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            approval = root / 'approval.json'
            approval.write_text(json.dumps(bundle))
            P.main(*args, root / 'output', approval)
            self.assertEqual(json.loads((root / 'output/BUILD-IDENTITY.json').read_text())['overrides'], bundle)
            for folder, relative in (
                ('source', 'forge-ai/src/main/java/forge/ai/SpellAbilityAi.java'),
                ('source', 'forge-ai/src/main/java/forge/ai/AiController.java'),
                ('shadow', 'forge/ai/SpellAbilityAi.class'),
                ('shadow', 'forge/ai/AiController.class'),
                ('shadow', 'forge/ai/AiController$1.class'),
            ):
                path = build / folder / relative
                original = path.read_bytes()
                path.write_bytes(b'SYNTHETIC CHANGED')
                output = root / ('rejected-' + folder + '-' + path.stem)
                with self.assertRaisesRegex(ValueError, 'byte identity'):
                    P.main(*args, output, approval)
                self.assertFalse(output.exists())
                path.write_bytes(original)

    def observer_bundle(self):
        bundle = self.sacrifice_bundle()
        bundle['schema'] = 10
        bundle['sources']['forge-game/src/main/java/forge/game/trigger/TriggerHandler.java'] = 'e' * 64
        bundle['classes']['forge/game/trigger/TriggerHandler.class'] = 'f' * 64
        return bundle

    def test_observer_bundle_accepts_only_the_thirteen_source_twenty_one_class_extension(self):
        parent, bundle = self.sacrifice_bundle(), self.observer_bundle()
        before = copy.deepcopy(bundle)
        runtime, profile = P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bundle)
        self.assertEqual(bundle, before)
        self.assertEqual(profile['overrides'], bundle)
        self.assertEqual((len(bundle['sources']), len(bundle['classes'])), (13, 21))
        self.assertEqual(set(bundle['sources']) - set(parent['sources']),
                         {'forge-game/src/main/java/forge/game/trigger/TriggerHandler.java'})
        self.assertEqual(set(bundle['classes']) - set(parent['classes']),
                         {'forge/game/trigger/TriggerHandler.class'})
        self.assertNotEqual(runtime['build_id'], P.derive_bundle(
            self.base, self.identity, '/build/shadow', '/profile', parent)[0]['build_id'])
        for group, name in (
            ('sources', 'forge-game/src/main/java/forge/game/trigger/TriggerHandler.java'),
            ('classes', 'forge/game/trigger/TriggerHandler.class'),
        ):
            changed = copy.deepcopy(bundle)
            changed[group][name] = '0' * 64
            self.assertNotEqual(runtime['build_id'], P.derive_bundle(
                self.base, self.identity, '/build/shadow', '/profile', changed)[0]['build_id'])

    def test_observer_bundle_rejects_every_missing_source(self):
        bundle = self.observer_bundle()
        for missing in bundle['sources']:
            bad = {**bundle, 'sources': {k: v for k, v in bundle['sources'].items() if k != missing}}
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_observer_bundle_rejects_every_missing_class(self):
        bundle = self.observer_bundle()
        for missing in bundle['classes']:
            bad = {**bundle, 'classes': {k: v for k, v in bundle['classes'].items() if k != missing}}
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_observer_bundle_rejects_extra_sources(self):
        bundle = self.observer_bundle()
        for extra in ('forge-game/src/main/java/forge/game/Game.java',
                      'forge-game/src/main/java/forge/game/trigger/TriggerHandlerExtra.java',
                      '../forbidden.java'):
            bad = {**bundle, 'sources': {**bundle['sources'], extra: '0' * 64}}
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_observer_bundle_rejects_extra_classes(self):
        bundle = self.observer_bundle()
        for extra in ('forge/game/trigger/TriggerHandler$Extra.class',
                      'forge/game/Game.class', '../forbidden.class'):
            bad = {**bundle, 'classes': {**bundle['classes'], extra: '0' * 64}}
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile', bad)

    def test_observer_bundle_rejects_schema_relabeling_and_non_integer_schemas(self):
        bundle = self.observer_bundle()
        for schema in (*range(1, 10), 0, 11, True, False, 10.0, '10', None):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                P.derive_bundle(self.base, self.identity, '/build/shadow', '/profile',
                                {**bundle, 'schema': schema})

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
