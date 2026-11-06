#!/usr/bin/env python3
"""Bounded offline audit only. Exit 1 preserves native policy RED, never repairs it."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


here = Path(__file__).resolve().parent
identity_path, prefix, out = [Path(arg).resolve() for arg in sys.argv[1:4]]
assert len(sys.argv) == 4
assert sha(identity_path) == "cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0"
identity = json.loads(identity_path.read_text())
k, j, cache = [Path(identity[key]) for key in ("forge", "jdk", "cache")]
pin = json.loads((here / "PREFIX-PIN.json").read_text())
assert pin == json.loads((prefix.parent / "MANIFEST.json").read_text())
assert pin["content_id"] == "3f595b71da5b339b2c9f5f6bced98fb25291db7d55c6427835d52b6d532e38ee"
assert pin["identity"]["base_build_id"] == identity["build_id"]
assert len(pin["identity"]["payloads"]) == 8
assert {str(p.relative_to(prefix)) for p in prefix.rglob("*.class")} == {
    item["path"] for item in pin["identity"]["payloads"]}
payloads = {str(prefix / item["path"]): item["sha256"] for item in pin["identity"]["payloads"]}
base_pins = {
    str(k / "forge-ai/target/classes/forge/ai/ability/DrawAi.class"):
        "5ca377a3c844add6b7655b3f1c7515378699221c1cf44b60d9bb7717d0bb097c",
    str(k / "forge-ai/src/main/java/forge/ai/ability/DrawAi.java"):
        "e1180554abd656c86e9081fbe1ab2ecc292dffa21231b3ca4337eece275dc6c4",
    str(k / "forge-gui-desktop/target/test-classes/forge/ai/AITest.class"):
        "f9fef0ece6f0b384d7646096ddfa0d1ab58c11408f1b490f952e1902ccd0ac53"}
for name, digest in {**payloads, **base_pins}.items():
    assert sha(Path(name)) == digest, name
for line in (here / "canonical.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    card = here / name
    assert sha(card) == digest
    assert card.read_bytes() == (k / "forge-gui/res/cardsfolder" / card.name[0] / card.name).read_bytes()
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=here, text=True).strip() == \
    "fd0fe1dfc77c5d3a647b57b7211c4098385b48cc"
assert not out.exists()
assert not subprocess.check_output(["findmnt", "-T", str(out.parent), "-n", "-o", "FSTYPE"],
                                   text=True).strip().startswith(("nfs", "cifs"))
os.umask(0o077)
out.mkdir(mode=0o700)
for name in ("classes", "test-source", "home", "tmp"):
    (out / name).mkdir(mode=0o700)
for name in ("DECLARATION.json", "NativeTargetedDrawAudit.java"):
    shutil.copyfile(here / name, out / ("test-source/" + name if name.endswith(".java") else name))
own_pins = {str(p): sha(p) for p in here.rglob("*") if p.is_file()}
runtime = [str(prefix)] + identity["runtime_classpath"]
draw_class = "forge/ai/ability/DrawAi.class"
assert next(Path(p) for p in runtime if Path(p).is_dir() and (Path(p) / draw_class).is_file()) == \
    k / "forge-ai/target/classes"
cp = ":".join(runtime)
save(out / "BEFORE.json", {"base_identity_sha256": sha(identity_path), "base_build_id": identity["build_id"],
    "prefix": pin, "base_pins": base_pins, "test_pins": own_pins,
    "runtime_classpath": runtime, "engine_clock": "unchanged", "natural_games": 0})
with (out / "compile.private.log").open("wb") as log:
    subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
        "-implicit:none", "-sourcepath", str(out / "test-source"), "-cp", cp, "-d", str(out / "classes"),
        str(out / "test-source/NativeTargetedDrawAudit.java")], stdout=log, stderr=log, check=True, timeout=60)
assert len(list((out / "classes").rglob("*.class"))) == 2
with (out / "base-DrawAi-bytecode.private.txt").open("wb") as log:
    subprocess.run([str(j / "bin/javap"), "-p", "-c", "-classpath", cp, "forge.ai.ability.DrawAi"],
                   stdout=log, stderr=log, check=True, timeout=30)
java_processes = subprocess.check_output(["ps", "-eo", "comm="], text=True).splitlines().count("java")
assert java_processes <= 1, "Would exceed parent maximum two native audit JVMs"
argv = ["timeout", "-k", "5s", "180", "strace", "--seccomp-bpf", "-f", "-qq", "-e", "trace=network",
    "-o", str(out / "network.private.strace"), "bwrap", "--unshare-user", "--unshare-net", "--unshare-pid",
    "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session"]
for path in ["/usr", "/lib", "/lib64", "/bin", "/etc", str(cache), str(identity_path.parent), str(prefix)]:
    argv += ["--ro-bind", path, path]
argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(out), str(out),
    "--chdir", str(k / "forge-gui-desktop"), "--clearenv", "--setenv", "PATH", str(j / "bin") + ":/usr/bin:/bin",
    "--setenv", "HOME", str(out / "home"), "--setenv", "LANG", "C.UTF-8", str(j / "bin/java"),
    "-Xmx1500m", "-XX:ActiveProcessorCount=1", "-Djava.awt.headless=true", "-Duser.home=" + str(out / "home"),
    "-Djava.io.tmpdir=" + str(out / "tmp"), "-Dsentry.dsn=", "-Xlog:class+load=info:file=" +
    str(out / "class-load.private.log") + ":uptime,level,tags", "--add-opens", "java.base/java.lang=ALL-UNNAMED",
    "-cp", str(out / "classes") + ":" + cp, "forge.evaluation.NativeTargetedDrawAudit", str(out)]
started = time.monotonic()
with (out / "stdout.private.log").open("wb") as stdout, (out / "stderr.private.log").open("wb") as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    save(out / "LAUNCH.private.json", {"pid": process.pid, "argv": argv,
                                       "other_java_processes_at_launch": java_processes})
    code = process.wait()
save(out / "PROCESS-CLOSED.json", {"exit": code, "seconds": time.monotonic()-started})
result = json.loads((out / "summary.private.json").read_text())
assert code in (0, 1, 2)
assert all(sha(Path(p)) == digest for p, digest in {**payloads, **base_pins, **own_pins}.items())
origins = {}
for line in (out / "class-load.private.log").read_text().splitlines():
    match = re.search(r"\] (forge\.[\w.$]+) source: file:(.*)$", line)
    if match:
        origins[match[1]] = match[2].rstrip("/")
assert Path(origins["forge.ai.ability.DrawAi"]) == k / "forge-ai/target/classes"
assert Path(origins["forge.ai.PlayerControllerAi"]) == k / "forge-ai/target/classes"
assert Path(origins["forge.ai.AITest"]) == k / "forge-gui-desktop/target/test-classes"
for name in ("forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana"):
    assert Path(origins[name]) == prefix, (name, origins.get(name))
assert not re.search(r"connect\(.*sa_family=AF_INET6?", (out / "network.private.strace").read_text())
assert not re.search(r"TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired",
                     (out / "stderr.private.log").read_text())
cohorts = {}
for row in result["cases"]:
    counts = cohorts.setdefault(row["cohort"], {"passed": 0, "red": 0})
    counts["passed" if row["passed"] else "red"] += 1
assert sum(cohorts["ai-choice"].values()) == 12
verified = {"exit": code, "seconds": time.monotonic()-started, "cohorts": cohorts, "errors": result["errors"],
    "base_identity_sha256": sha(identity_path), "prefix_content_id": pin["content_id"],
    "DrawAi_class_sha256": base_pins[str(k / "forge-ai/target/classes/forge/ai/ability/DrawAi.class")],
    "pins_unchanged": True, "origins": {name: origins[name] for name in (
        "forge.ai.ability.DrawAi", "forge.ai.PlayerControllerAi", "forge.ai.AITest", "forge.ai.ComputerUtil",
        "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana")},
    "network_inet_connects": 0, "native_timeout_diagnostics": 0, "natural_games": 0,
    "profile_or_app_qualification": False}
save(out / "VERIFIED-CLOSED.json", verified)
print(json.dumps(verified, indent=2), flush=True)
raise SystemExit(code)
