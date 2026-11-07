# SPDX-License-Identifier: GPL-3.0-or-later
# Original bounded native compatibility runner. Forge Team/Card-Forge engine,
# https://github.com/Card-Forge/forge, pin 61e9442c433711a82258daca3236f936a1d6f70e.
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(root, label, argv, cwd=None):
    log = root / (label + ".log")
    (root / (label + ".command.txt")).write_text(shlex.join(argv) + "\n")
    start = time.monotonic()
    with log.open("wb") as stream:
        child = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        launch = {"pid": child.pid, "pgid": child.pid, "argv": argv}
        write(root / (label + ".launch.json"), launch)
        code = child.wait()
    try:
        os.killpg(child.pid, 0)
        group_absent = False
    except ProcessLookupError:
        group_absent = True
    result = {**launch, "exit": code, "wall_seconds": time.monotonic() - start,
              "process_group_absent": group_absent}
    write(root / (label + ".exit.json"), result)
    print(label, "exit", code, "group_absent", group_absent, flush=True)
    return result


def main():
    os.umask(0o077)
    root = Path(sys.argv[1]).resolve()
    k = root.parent
    forge = Path((k / "forge.source.path").read_text().strip())
    java = Path((k / "JDK.path").read_text().strip()) / "bin/java"
    cp = (root / "classpath.txt").read_text().strip()
    source = Path(__file__).resolve().parent
    sources = [forge / item for item in (
        "forge-game/src/main/java/forge/game/GameState.java",
        "forge-game/src/main/java/forge/game/Game.java",
        "forge-game/src/main/java/forge/game/GameAction.java",
        "forge-game/src/main/java/forge/game/Match.java",
        "forge-game/src/main/java/forge/game/card/Card.java",
        "forge-game/src/main/java/forge/game/zone/MagicStack.java",
        "forge-ai/src/main/java/forge/ai/ComputerUtil.java",
        "forge-core/src/main/java/forge/util/MyRandom.java",
        "forge-gui/res/cardsfolder/l/lightning_bolt.txt",
    )]
    sources += sorted(source.glob("*.py")) + sorted(source.glob("*.java"))
    sources += sorted((root / "classes").rglob("*.class"))
    sources += [k / "run_java_sandbox.sh", root / "classpath.txt"]
    before = {str(p): {"sha256": digest(p), "mode": p.stat().st_mode & 0o777}
              for p in sources}
    write(root / "SOURCE-BEFORE.json", before)
    # No java.sql module is resolved. Network is isolated by the shared bwrap wrapper.
    command = ["nice", "-n", "15", "taskset", "-c", "6", "timeout", "--signal=TERM",
               "--kill-after=5s", "60", "bash", str(k / "run_java_sandbox.sh"), "offline",
               str(root), str(forge / "forge-gui-desktop"), str(java), "-Xmx2g",
               "-XX:ActiveProcessorCount=1", "-Djava.awt.headless=true",
               "--limit-modules", "java.base,java.desktop,java.logging,java.management,java.naming,java.xml,jdk.unsupported,jdk.crypto.ec,jdk.zipfs",
               "-Duser.home=" + str(root / "home"), "-Djava.io.tmpdir=" + str(root / "tmp"),
               "-Dsentry.dsn=", "-cp", str(root / "classes") + ":" + cp,
               "forge.evaluation.NativeSaveAudit"]
    calls, comparisons = [], []
    for seat in (0, 1):
        exported = root / ("export-seat" + str(seat))
        result = run(root, "export-seat" + str(seat), command + ["export", str(seat), str(exported)])
        calls.append(result)
        if result["exit"] != 0:
            continue
        for stage in ("pending", "settled"):
            label = "restore-seat" + str(seat) + "-" + stage
            restored = root / label
            restored.mkdir()
            original = exported / stage
            result = run(root, label, command + ["restore", str(seat), str(original), str(restored)])
            calls.append(result)
            if result["exit"] != 0:
                continue
            comparison = run(root, label + "-strict", [sys.executable, "-I", "-B",
                             str(source / "compare.py"), str(original / "facts.private.json"),
                             str(restored / "facts.private.json"), str(restored / "COMPARISON.json")])
            comparisons.append({"seat": seat, "stage": stage, "check_exit": comparison["exit"],
                                **json.loads((restored / "COMPARISON.json").read_text())})
    after = {str(p): {"sha256": digest(p), "mode": p.stat().st_mode & 0o777}
             for p in sources}
    write(root / "SOURCE-AFTER.json", after)
    result = {"status": "COMPATIBILITY_OBSERVATION_NOT_NATURAL_GAME_QUALIFICATION",
              "engine_pin": "61e9442c433711a82258daca3236f936a1d6f70e",
              "calls": calls, "comparisons": comparisons, "source_bytes_modes_unchanged": before == after,
              "desired_full_save_invariant_relaxed": False, "custom_stack_reconstruction": False,
              "rng_resume_tested": False, "bo3_resume_tested": False,
              "sql_module_unavailable": True, "network_namespace_isolated": True,
              "all_native_calls_returned_zero": len(calls) == 6 and all(c["exit"] == 0 for c in calls),
              "all_owned_groups_absent": all(c["process_group_absent"] for c in calls)}
    write(root / "REPORT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "calls"}, sort_keys=True), flush=True)
    return 0 if result["all_native_calls_returned_zero"] and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
