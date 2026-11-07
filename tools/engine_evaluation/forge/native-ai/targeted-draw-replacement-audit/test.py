#!/usr/bin/env python3
"""NEW tests only, one offline JVM; preserve actual selected targets and RED results."""
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


def check(pins):
    for name, digest in pins.items():
        assert sha(Path(name)) == digest, name


os.umask(0o077)
assert len(sys.argv) == 5
identity_path, draw, eight, out = [Path(value).resolve() for value in sys.argv[1:]]
here = Path(__file__).resolve().parent
assert sha(identity_path) == "cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0"
identity = json.loads(identity_path.read_text())
k, j, cache = [Path(identity[name]) for name in ("forge", "jdk", "cache")]
actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=here, text=True).strip()
subprocess.run(["git", "merge-base", "--is-ancestor", "fd0fe1dfc77c5d3a647b57b7211c4098385b48cc", actual_head], cwd=here, check=True)
eight_pin = json.loads((here / "EIGHT-PIN.json").read_text())
draw_pin = json.loads((here / "DRAW-PIN.json").read_text())
assert eight_pin == json.loads((eight.parent / "MANIFEST.json").read_text())
assert draw_pin == json.loads((draw.parent / "MANIFEST.json").read_text())
assert eight_pin["content_id"] == "3f595b71da5b339b2c9f5f6bced98fb25291db7d55c6427835d52b6d532e38ee"
assert draw_pin["content_id"] == "9763dbe0a798c962bed5421a9f1eec7ba5b8b960edacfbd4655721d8c0f05311"
assert draw_pin["identity"]["parent_content_id"] == eight_pin["content_id"]
assert eight_pin["identity"]["base_build_id"] == draw_pin["identity"]["base_build_id"] == identity["build_id"]
payloads = {}
for prefix, pin, count in [(draw, draw_pin, 1), (eight, eight_pin, 8)]:
    assert len(pin["identity"]["payloads"]) == count
    assert {str(p.relative_to(prefix)) for p in prefix.rglob("*.class")} == {p["path"] for p in pin["identity"]["payloads"]}
    for item in pin["identity"]["payloads"]:
        payloads[str(prefix / item["path"])] = item["sha256"]
dependencies = json.loads((here / "DEPENDENCIES-PIN.json").read_text())
base_pins = {
    str(k / "forge-ai/target/classes/forge/ai/ability/DrawAi.class"):
        "5ca377a3c844add6b7655b3f1c7515378699221c1cf44b60d9bb7717d0bb097c",
    str(k / "forge-ai/src/main/java/forge/ai/ability/DrawAi.java"):
        "e1180554abd656c86e9081fbe1ab2ecc292dffa21231b3ca4337eece275dc6c4",
    str(k / "forge-gui-desktop/target/test-classes/forge/ai/AITest.class"):
        "f9fef0ece6f0b384d7646096ddfa0d1ab58c11408f1b490f952e1902ccd0ac53"}
check({**payloads, **dependencies, **base_pins})
for line in (here / "canonical.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1); p = here / name
    assert sha(p) == digest
    assert p.read_bytes() == (k / "forge-gui/res/cardsfolder" / p.name[0] / p.name).read_bytes()
assert not out.exists()
assert subprocess.check_output(["findmnt", "-T", str(out.parent), "-n", "-o", "FSTYPE"], text=True).strip().splitlines()[-1] not in ("nfs", "nfs4", "cifs")
out.mkdir(mode=0o700)
for name in ["classes", "test-source", "home", "tmp"]:
    (out / name).mkdir(mode=0o700)
shutil.copyfile(here / "NativeTargetedDrawReplacementAudit.java", out / "test-source/NativeTargetedDrawReplacementAudit.java")
shutil.copyfile(here / "DECLARATION.json", out / "DECLARATION.json")
test_pins = {str(p): sha(p) for p in here.rglob("*") if p.is_file()}
runtime = [str(draw), str(eight)] + identity["runtime_classpath"]
cp = ":".join(runtime)
save(out / "BEFORE.json", {"actual_head": actual_head, "base_identity_sha256": sha(identity_path),
    "one_draw_manifest": draw_pin, "eight_manifest": eight_pin, "runtime_classpath": runtime,
    "runtime_payload_pins": payloads, "base_pins": base_pins, "dependency_pins": dependencies,
    "test_pins": test_pins, "allowed_runtime_form": "original one DrawAi layer plus exact old eight",
    "parent8526_manifest_verified": False, "native_clock": "unchanged"})
with (out / "compile.private.log").open("wb") as log:
    subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
        "-implicit:none", "-sourcepath", str(out / "test-source"), "-cp", cp, "-d", str(out / "classes"),
        str(out / "test-source/NativeTargetedDrawReplacementAudit.java")], stdout=log, stderr=log, check=True, timeout=60)
assert len(list((out / "classes").rglob("*.class"))) == 2
other_jvms = subprocess.check_output(["ps", "-eo", "comm="], text=True).splitlines().count("java")
assert other_jvms <= 1, "Would exceed max two native audit JVMs"
argv = ["timeout", "-k", "5s", "180", "strace", "--seccomp-bpf", "-f", "-qq", "-e", "trace=network",
    "-o", str(out / "network.private.strace"), "bwrap", "--unshare-user", "--unshare-net", "--unshare-pid",
    "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session"]
for p in ["/usr", "/lib", "/lib64", "/bin", "/etc", str(cache), str(identity_path.parent), str(draw), str(eight)]:
    argv += ["--ro-bind", p, p]
argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(out), str(out),
    "--chdir", str(k / "forge-gui-desktop"), "--clearenv", "--setenv", "PATH", str(j / "bin") + ":/usr/bin:/bin",
    "--setenv", "HOME", str(out / "home"), "--setenv", "LANG", "C.UTF-8", str(j / "bin/java"),
    "-Xmx1500m", "-XX:ActiveProcessorCount=1", "-Djava.awt.headless=true", "-Duser.home=" + str(out / "home"),
    "-Djava.io.tmpdir=" + str(out / "tmp"), "-Dsentry.dsn=", "-Xlog:class+load=info:file=" +
    str(out / "class-load.private.log") + ":uptime,level,tags", "--add-opens", "java.base/java.lang=ALL-UNNAMED",
    "-cp", str(out / "classes") + ":" + cp, "forge.evaluation.NativeTargetedDrawReplacementAudit", str(out)]
started = time.monotonic()
with (out / "stdout.private.log").open("wb") as stdout, (out / "stderr.private.log").open("wb") as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    save(out / "LAUNCH.private.json", {"pid": process.pid, "argv": argv, "other_java_processes": other_jvms})
    code = process.wait()
save(out / "PROCESS-CLOSED.json", {"exit": code, "seconds": time.monotonic()-started})
result = json.loads((out / "summary.private.json").read_text())
check({**payloads, **dependencies, **base_pins, **test_pins})
origins = {}
for line in (out / "class-load.private.log").read_text().splitlines():
    m = re.search(r"\] (forge\.[\w.$]+) source: file:(.*)$", line)
    if m: origins[m[1]] = m[2].rstrip("/")
assert Path(origins["forge.ai.ability.DrawAi"]) == draw
assert Path(origins["forge.ai.PlayerControllerAi"]) == k / "forge-ai/target/classes"
assert Path(origins["forge.ai.AITest"]) == k / "forge-gui-desktop/target/test-classes"
for name in ["forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana"]:
    assert Path(origins[name]) == eight
assert not re.search(r"connect\(.*sa_family=AF_INET6?", (out / "network.private.strace").read_text())
assert not re.search(r"TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired", (out / "stderr.private.log").read_text())
cohorts = {}
for row in result["cases"]:
    c = cohorts.setdefault(row["cohort"], {"passed": 0, "red": 0}); c["passed" if row["passed"] else "red"] += 1
verified = {"exit": code, "seconds": time.monotonic()-started, "cohorts": cohorts, "errors": result["errors"],
    "actual_head": actual_head, "base_identity_sha256": sha(identity_path), "one_draw_content_id": draw_pin["content_id"],
    "eight_content_id": eight_pin["content_id"], "all_pins_unchanged": True,
    "origins": {name: origins[name] for name in ["forge.ai.ability.DrawAi", "forge.ai.PlayerControllerAi", "forge.ai.AITest",
        "forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana"]},
    "native_clock": "unchanged", "network_inet_connects": 0, "natural_games": 0}
save(out / "VERIFIED-CLOSED.json", verified); print(json.dumps(verified, indent=2), flush=True)
assert result["errors"] == 0, "STOP: fixture/engine error; preserve ledger"
assert len(result["cases"]) == 12 and code in (0, 1)
raise SystemExit(code)
