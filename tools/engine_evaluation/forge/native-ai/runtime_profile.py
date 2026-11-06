# SPDX-License-Identifier: GPL-3.0-or-later
# Original profile builder for Forge Team/Card-Forge native AI modifications.
"""Derive a distinct opt-in runtime identity; never deploy or reuse a base save ID."""
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

HEX = re.compile(r"[0-9a-f]{64}")
CLASS_SHA = "60ec0579438008e0c5a1eba4ef0ffde6b77f3eaf7ab9865c8fa3a2a1b97a1bfc"
SOURCE_SHA = "7a9341bc13900a1ad8a47a96ad29a5cba3110340ecb38895bef98669760f18d8"
BASE_BUILD_ID = "59228745bfcbec403b038019815d8e94f74273fd4494a2e5799479d61abd3605"
LAUNCH_SHA = "ee58d6110017448391e210c1722d6f1450904c239cc297282f34e4ed4c588562"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _base(runtime, identity, shadow, output):
    if set(runtime) != {"argv", "cwd", "sessions_dir", "build_id"}:
        raise ValueError("Expected the qualified four-field native runtime")
    if runtime["build_id"] != BASE_BUILD_ID or runtime["build_id"] != identity["build_id"]:
        raise ValueError("Base build identity mismatch")
    argv, cp = runtime["argv"], identity["runtime_classpath"]
    if (not isinstance(argv, list) or not all(isinstance(x, str) for x in argv)
            or not argv or argv[0] != "/usr/bin/bwrap" or argv.count("-cp") != 1
            or argv.count("--chdir") != 1 or "--die-with-parent" not in argv
            or not argv[-2:] == ["forge.evaluation.NativeHumanWorker", "{session}"]):
        raise ValueError("Unsupported qualified launch shape")
    if _digest(argv) != LAUNCH_SHA:
        raise ValueError("Base launch command is not the qualified command")
    if (not isinstance(cp, list) or not cp or not all(isinstance(x, str) and Path(x).is_absolute()
                                                    and ":" not in x for x in cp)):
        raise ValueError("Invalid native classpath")
    at = argv.index("-cp")
    if at + 1 >= len(argv) or argv[at + 1] != ":".join(cp):
        raise ValueError("Runtime classpath does not match base identity")
    for name in [shadow, output]:
        if not Path(name).is_absolute() or ".." in Path(name).parts or ":" in str(name):
            raise ValueError("Canonical absolute local profile paths required")
    return cp, at


def _finish(runtime, shadow, output, profile, at):
    profile["build_id"] = _digest(profile)
    updated = copy.deepcopy(runtime)
    updated["argv"][at + 1] = ":".join(profile["runtime_classpath"])
    bind = updated["argv"].index("--chdir")
    updated["argv"][bind:bind] = ["--ro-bind", str(shadow), str(shadow)]
    updated.update(build_id=profile["build_id"], cwd=str(output), sessions_dir=str(Path(output) / "sessions"))
    return updated, profile


def derive(runtime, identity, shadow, output, digests):
    """Pure, explicitly pinned profile transformation; no game or process creation."""
    cp, at = _base(runtime, identity, shadow, output)
    if digests != {"class_sha256": CLASS_SHA, "source_sha256": SOURCE_SHA}:
        raise ValueError("Candidate source/class byte identity mismatch")
    profile = {"schema": 2, "base_build_id": runtime["build_id"], "base_launch_sha256": LAUNCH_SHA,
               "runtime_classpath": [str(shadow), *cp],
               "override": {"class": "forge.ai.ComputerUtil", **digests}}
    return _finish(runtime, shadow, output, profile, at)


def _check_bundle(bundle):
    sources = {"forge-ai/src/main/java/forge/ai/" + name + ".java"
               for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilMana"]}
    classes = {"forge/ai/" + name + ".class"
               for name in ["ComputerUtil", "ComputerUtilCost", "ComputerUtilCost$1", "ComputerUtilMana"]}
    if isinstance(bundle, dict) and bundle.get("schema") in (2, 3, 4):
        sources.add("tools/engine_evaluation/forge/actor-boundary/ActorBoundary.java")
        classes.update({"forge/evaluation/ActorBoundary.class", "forge/evaluation/ActorBoundary$Pending.class"})
    if isinstance(bundle, dict) and bundle.get("schema") in (3, 4):
        sources.add("forge-ai/src/main/java/forge/ai/ability/DamageDealAi.java")
        classes.add("forge/ai/ability/DamageDealAi.class")
    if isinstance(bundle, dict) and bundle.get("schema") == 4:
        sources.add("forge-ai/src/main/java/forge/ai/ability/DamageAiBase.java")
        classes.add("forge/ai/ability/DamageAiBase.class")
    if (not isinstance(bundle, dict) or set(bundle) != {"schema", "sources", "classes"}
            or type(bundle["schema"]) is not int or bundle["schema"] not in (1, 2, 3, 4)
            or not isinstance(bundle["sources"], dict) or set(bundle["sources"]) != sources
            or not isinstance(bundle["classes"], dict) or set(bundle["classes"]) != classes
            or not all(isinstance(v, str) and HEX.fullmatch(v)
                       for group in [bundle["sources"], bundle["classes"]] for v in group.values())):
        raise ValueError("Expected an approved AI, actor-boundary, lethal-timing or pressure composition")


def derive_bundle(runtime, identity, shadow, output, bundle):
    """Compose the separately approved three-source cost correction, never a base save."""
    cp, at = _base(runtime, identity, shadow, output)
    _check_bundle(bundle)
    profile = {"schema": 3, "base_build_id": runtime["build_id"], "base_launch_sha256": LAUNCH_SHA,
               "runtime_classpath": [str(shadow), *cp], "overrides": copy.deepcopy(bundle)}
    return _finish(runtime, shadow, output, profile, at)


def _publish(output, runtime, profile):
    parent = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging, directory, created = None, None, False
    try:
        staging = "." + output.name + ".pending-" + uuid.uuid4().hex
        os.mkdir(staging, 0o700, dir_fd=parent)
        created = True
        directory = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        for name, value in [("runtime.json", runtime), ("BUILD-IDENTITY.json", profile)]:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, "w") as handle:
                json.dump(value, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        os.fsync(directory)
        current, held = os.stat(output.parent, follow_symlinks=False), os.fstat(parent)
        if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
            raise ValueError("Profile parent changed during publication")
        # A competing empty output must not be overwritten by directory rename.
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent, os.fsencode(staging), parent, os.fsencode(output.name), 1):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(output))
        staging = None
        os.fsync(parent)
    finally:
        try:
            if directory is not None:
                try:
                    if staging is not None:
                        for name in ["runtime.json", "BUILD-IDENTITY.json"]:
                            try:
                                os.unlink(name, dir_fd=directory)
                            except FileNotFoundError:
                                pass
                finally:
                    os.close(directory)
            if staging is not None and created:
                os.rmdir(staging, dir_fd=parent)
        finally:
            os.close(parent)


def main(runtime_path, identity_path, build_path, output_path, approved_bundle_path=None):
    root, output = Path(build_path), Path(output_path)
    if output.exists() or output.is_symlink():
        raise ValueError("Fresh profile output required")
    shadow = root / "shadow"
    bundle = json.loads(Path(approved_bundle_path).read_text()) if approved_bundle_path else None
    if approved_bundle_path is not None:
        _check_bundle(bundle)
    expected = bundle["classes"] if bundle is not None else {"forge/ai/ComputerUtil.class": CLASS_SHA}
    sources = bundle["sources"] if bundle is not None else {"forge-ai/src/main/java/forge/ai/ComputerUtil.java": SOURCE_SHA}
    for path in [root, shadow, output.parent, *[shadow / p for p in expected],
                 *[root / "source" / p for p in sources]]:
        if not path.is_absolute() or any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError("No symlink profile inputs")
    entries = list(shadow.rglob("*"))
    if any(p.is_symlink() for p in entries):
        raise ValueError("No symlink entries in the candidate shadow")
    if {p.relative_to(shadow).as_posix() for p in entries if p.is_file()} != set(expected):
        raise ValueError("Candidate shadow class set differs from its approval")
    for directory, group in [(shadow, expected), (root / "source", sources)]:
        for name, digest in group.items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Candidate source/class byte identity mismatch")
    base, identity = json.loads(Path(runtime_path).read_text()), json.loads(Path(identity_path).read_text())
    if bundle is not None:
        runtime, profile = derive_bundle(base, identity, shadow, output, bundle)
    else:
        runtime, profile = derive(base, identity, shadow, output, {"class_sha256": CLASS_SHA, "source_sha256": SOURCE_SHA})
    _publish(output, runtime, profile)
    print(json.dumps({"build_id": profile["build_id"], "overrides": sorted(expected),
                      "no_deployment_or_game": True}))


if __name__ == "__main__":
    main(*sys.argv[1:])
