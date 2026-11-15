#!/usr/bin/env python3
"""Bounded baseline/build/candidate safety gates; immutable predecessor checks."""
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
assert len(sys.argv) == 6
mode = sys.argv[1]
assert mode in ("baseline", "build", "candidate")
identity_path, draw, eight, root = [Path(value).resolve() for value in sys.argv[2:]]
assert root.is_dir() and root.name.startswith("native-targeted-draw-safety-policy-")
out = root / ("baseline" if mode == "baseline" else "candidate-gate")
candidate = root / "candidate"
here = Path(__file__).resolve().parent
assert sha(identity_path) == "cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0"
identity = json.loads(identity_path.read_text())
k, j, cache = [Path(identity[name]) for name in ("forge", "jdk", "cache")]
actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=here, text=True).strip()
subprocess.run(["git", "merge-base", "--is-ancestor", "fd0fe1dfc77c5d3a647b57b7211c4098385b48cc", actual_head], cwd=here, check=True)
eight_pin = json.loads((here / "EIGHT-PIN.json").read_text())
draw_pin = json.loads((here / "FIRST-DRAW-PIN.json").read_text())
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
relative_source = Path("forge-ai/src/main/java/forge/ai/ability/DrawAi.java")
assert sha(here / "preimage/DrawAi.java") == "d18e7a443e01df1e6e4cefc3550a488114193d245d65d755c2b3bea4341f6304"
if mode == "build":
    baseline = json.loads((root / "baseline/VERIFIED-CLOSED.json").read_text())
    assert baseline["exit"] == 1 and baseline["errors"] == 0
    assert baseline["cohorts"] == {
        "unchanged-original12": {"passed": 12, "red": 0}, "unchanged-policy10": {"passed": 10, "red": 0},
        "unchanged-replacement8": {"passed": 4, "red": 4}, "new-positive4": {"passed": 4, "red": 0},
        "trusted-replacement4-not-ai": {"passed": 4, "red": 0}}
    assert json.loads((root / "report/ABI-VERIFIED.json").read_text())["query_signatures_verified"]
    assert not candidate.exists()
    staged = candidate / "source" / relative_source; staged.parent.mkdir(parents=True, mode=0o700)
    shutil.copyfile(here / "preimage/DrawAi.java", staged)
    with (candidate / "patch.private.log").open("wb") as log:
        subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p0", "-i", str(here / "DrawAi.patch")],
                       cwd=candidate / "source", stdout=log, stderr=log, check=True, timeout=20)
    assert not re.search(r"offset|fuzz|FAILED", (candidate / "patch.private.log").read_text(), re.I)
    assert staged.read_bytes() == (here / "source" / relative_source).read_bytes()
    shadow = candidate / "shadow"; shadow.mkdir(mode=0o700)
    with (candidate / "compile.private.log").open("wb") as log:
        subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
            "-implicit:none", "-sourcepath", str(candidate / "source"), "-cp", ":".join([str(draw), str(eight)] + identity["runtime_classpath"]),
            "-d", str(shadow), str(staged)], stdout=log, stderr=log, check=True, timeout=60)
    classes = list(shadow.rglob("*.class")); assert len(classes) == 1
    assert str(classes[0].relative_to(shadow)) == "forge/ai/ability/DrawAi.class"
    product = {"schema": "native-targeted-draw-safety-one-source-one-class-v1", "base_build_id": identity["build_id"],
        "parent_content_id": draw_pin["content_id"], "eight_content_id": eight_pin["content_id"],
        "preimage_sha256": sha(here / "preimage/DrawAi.java"), "patch_sha256": sha(here / "DrawAi.patch"),
        "sources": [{"path": str(relative_source), "sha256": sha(staged)}],
        "payloads": [{"path": "forge/ai/ability/DrawAi.class", "class_name": "forge.ai.ability.DrawAi", "sha256": sha(classes[0])}]}
    content_id = hashlib.sha256(json.dumps(product, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    save(candidate / "MANIFEST.json", {"content_id": content_id, "identity": product})
    check({**payloads, **dependencies, **base_pins})
    print(json.dumps(json.loads((candidate / "MANIFEST.json").read_text()), indent=2)); raise SystemExit(0)
candidate_pins = {}
if mode == "candidate":
    candidate_manifest = json.loads((candidate / "MANIFEST.json").read_text())
    assert candidate_manifest["identity"]["parent_content_id"] == draw_pin["content_id"]
    assert candidate_manifest["identity"]["eight_content_id"] == eight_pin["content_id"]
    assert candidate_manifest["content_id"] == hashlib.sha256(json.dumps(candidate_manifest["identity"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert len(candidate_manifest["identity"]["payloads"]) == len(list((candidate / "shadow").rglob("*.class"))) == 1
    for item in candidate_manifest["identity"]["payloads"]: candidate_pins[str(candidate / "shadow" / item["path"])] = item["sha256"]
    candidate_pins[str(candidate / "source" / relative_source)] = candidate_manifest["identity"]["sources"][0]["sha256"]
    check(candidate_pins)
assert not out.exists()
assert subprocess.check_output(["findmnt", "-T", str(out.parent), "-n", "-o", "FSTYPE"], text=True).strip().splitlines()[-1] not in ("nfs", "nfs4", "cifs")
out.mkdir(mode=0o700)
for name in ["classes", "test-source", "home", "tmp"]:
    (out / name).mkdir(mode=0o700)
for folder, name in [(here, "NativeTargetedDrawSafetyGate.java"),
    (here.parent / "targeted-draw-audit", "NativeTargetedDrawAudit.java"),
    (here.parent / "targeted-draw-policy", "NativeTargetedDrawPolicyGate.java"),
    (here.parent / "targeted-draw-replacement-audit", "NativeTargetedDrawReplacementAudit.java")]:
    shutil.copyfile(folder / name, out / "test-source" / name)
shutil.copyfile(here / "DECLARATION.json", out / "DECLARATION.json")
test_pins = {str(p): sha(p) for p in here.rglob("*") if p.is_file()}
runtime = ([str(candidate / "shadow")] if mode == "candidate" else []) + [str(draw), str(eight)] + identity["runtime_classpath"]
cp = ":".join(runtime)
save(out / "BEFORE.json", {"actual_head": actual_head, "base_identity_sha256": sha(identity_path),
    "one_draw_manifest": draw_pin, "eight_manifest": eight_pin, "runtime_classpath": runtime,
    "runtime_payload_pins": payloads, "base_pins": base_pins, "dependency_pins": dependencies,
    "test_pins": test_pins, "allowed_runtime_form": "original one DrawAi layer plus exact old eight",
    "native_clock": "unchanged", "mode": mode, "candidate_pins": candidate_pins})
with (out / "compile.private.log").open("wb") as log:
    subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
        "-implicit:none", "-sourcepath", str(out / "test-source"), "-cp", cp, "-d", str(out / "classes"),
        *[str(p) for p in sorted((out / "test-source").glob("*.java"))]], stdout=log, stderr=log, check=True, timeout=60)
assert len(list((out / "classes").rglob("*.class"))) == 7
other_jvms = subprocess.check_output(["ps", "-eo", "comm="], text=True).splitlines().count("java")
assert other_jvms <= 1, "Would exceed max two native audit JVMs"
argv = ["timeout", "-k", "5s", "180", "strace", "--seccomp-bpf", "-f", "-qq", "-e", "trace=network",
    "-o", str(out / "network.private.strace"), "bwrap", "--unshare-user", "--unshare-net", "--unshare-pid",
    "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session"]
for p in ["/usr", "/lib", "/lib64", "/bin", "/etc", str(cache), str(identity_path.parent), str(draw), str(eight)] + ([str(candidate / "shadow")] if mode == "candidate" else []):
    argv += ["--ro-bind", p, p]
argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(out), str(out),
    "--chdir", str(k / "forge-gui-desktop"), "--clearenv", "--setenv", "PATH", str(j / "bin") + ":/usr/bin:/bin",
    "--setenv", "HOME", str(out / "home"), "--setenv", "LANG", "C.UTF-8", str(j / "bin/java"),
    "-Xmx1500m", "-XX:ActiveProcessorCount=1", "-Djava.awt.headless=true", "-Duser.home=" + str(out / "home"),
    "-Djava.io.tmpdir=" + str(out / "tmp"), "-Dsentry.dsn=", "-Xlog:class+load=info:file=" +
    str(out / "class-load.private.log") + ":uptime,level,tags", "--add-opens", "java.base/java.lang=ALL-UNNAMED",
    "-cp", str(out / "classes") + ":" + cp, "forge.evaluation.NativeTargetedDrawSafetyGate", str(out)]
started = time.monotonic()
with (out / "stdout.private.log").open("wb") as stdout, (out / "stderr.private.log").open("wb") as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    save(out / "LAUNCH.private.json", {"pid": process.pid, "argv": argv, "other_java_processes": other_jvms})
    code = process.wait()
save(out / "PROCESS-CLOSED.json", {"exit": code, "seconds": time.monotonic()-started})
result = json.loads((out / "summary.private.json").read_text())
check({**payloads, **dependencies, **base_pins, **test_pins, **candidate_pins})
origins = {}
for line in (out / "class-load.private.log").read_text().splitlines():
    m = re.search(r"\] (forge\.[\w.$]+) source: file:(.*)$", line)
    if m: origins[m[1]] = m[2].rstrip("/")
assert Path(origins["forge.ai.ability.DrawAi"]) == (candidate / "shadow" if mode == "candidate" else draw)
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
    "candidate_content_id": candidate_manifest["content_id"] if mode == "candidate" else None,
    "eight_content_id": eight_pin["content_id"], "all_pins_unchanged": True,
    "origins": {name: origins[name] for name in ["forge.ai.ability.DrawAi", "forge.ai.PlayerControllerAi", "forge.ai.AITest",
        "forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana"]},
    "native_clock": "unchanged", "network_inet_connects": 0, "natural_games": 0}
save(out / "VERIFIED-CLOSED.json", verified); print(json.dumps(verified, indent=2), flush=True)
assert result["errors"] == 0, "STOP: fixture/engine error; preserve ledger"
assert len(result["cases"]) == 38 and code in (0, 1)
raise SystemExit(code)
