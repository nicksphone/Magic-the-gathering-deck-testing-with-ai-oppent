#!/usr/bin/env python3
"""Offline baseline/build/candidate gates. Build requires the preserved boundary RED."""
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


def check_pins(pins):
    for path, digest in pins.items():
        assert sha(Path(path)) == digest, path


os.umask(0o077)
mode = sys.argv[1]
assert mode in ("baseline", "build", "candidate") and len(sys.argv) == 5
identity_path, prefix, root = [Path(value).resolve() for value in sys.argv[2:]]
here = Path(__file__).resolve().parent
old = here.parent / "targeted-draw-audit"
assert root.is_dir() and root.name.startswith("native-targeted-draw-policy-")
assert sha(identity_path) == "cf27ccd7a08f1a9433f75da8d399b3e9c87b83b95b17f883ffc4812ee2dfb3d0"
identity = json.loads(identity_path.read_text())
k, j, cache = [Path(identity[name]) for name in ("forge", "jdk", "cache")]
actual_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=here, text=True).strip()
subprocess.run(["git", "merge-base", "--is-ancestor",
    "fd0fe1dfc77c5d3a647b57b7211c4098385b48cc", actual_head], cwd=here, check=True)
assert subprocess.check_output(["findmnt", "-T", str(root), "-n", "-o", "FSTYPE"],
                               text=True).strip().splitlines()[-1] not in ("nfs", "nfs4", "cifs")
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
dependency_pins = {}
for line in (here / "dependency.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    dependency_pins[str(old / name)] = digest
assert sha(old / "NativeTargetedDrawAudit.java") == "3a00da40efa48e3ef9c17d3e9aed3929953c5d3a9b0567d85dda338aee2a962b"
check_pins({**payloads, **base_pins, **dependency_pins})
for line in (here / "canonical.sha256").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    p = here / name
    assert sha(p) == digest
    assert p.read_bytes() == (k / "forge-gui/res/cardsfolder" / p.name[0] / p.name).read_bytes()
assert (here / "preimage/DrawAi.java").read_bytes() == (k / "forge-ai/src/main/java/forge/ai/ability/DrawAi.java").read_bytes()
runtime = [str(prefix)] + identity["runtime_classpath"]
candidate = root / "candidate"
relative_source = Path("forge-ai/src/main/java/forge/ai/ability/DrawAi.java")

if mode == "build":
    baseline = json.loads((root / "baseline/VERIFIED-CLOSED.json").read_text())
    assert baseline["exit"] == 1 and baseline["errors"] == 0
    assert baseline["cohorts"] == {"unchanged-audit12": {"passed": 8, "red": 4},
        "new-safety10": {"passed": 4, "red": 6}, "trusted-exact-library4-not-ai": {"passed": 4, "red": 0}}
    rows = json.loads((root / "baseline/summary.private.json").read_text())["cases"]
    boundaries = [r for r in rows if r["cohort"] == "trusted-exact-library4-not-ai"]
    assert len(boundaries) == 4 and all(r["native_targetAI_opponent"] and r["passed"] for r in boundaries)
    assert not candidate.exists()
    staged = candidate / "source" / relative_source
    staged.parent.mkdir(parents=True, mode=0o700)
    shutil.copyfile(here / "preimage/DrawAi.java", staged)
    with (candidate / "patch.private.log").open("wb") as log:
        subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p0", "-i", str(here / "DrawAi.patch")],
                       cwd=candidate / "source", stdout=log, stderr=log, check=True, timeout=20)
    patch_log = (candidate / "patch.private.log").read_text()
    assert not re.search(r"offset|fuzz|FAILED", patch_log, re.I)
    assert staged.read_bytes() == (here / "source" / relative_source).read_bytes()
    shadow = candidate / "shadow"; shadow.mkdir(mode=0o700)
    with (candidate / "compile.private.log").open("wb") as log:
        subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
            "-implicit:none", "-sourcepath", str(candidate / "source"), "-cp", ":".join(runtime),
            "-d", str(shadow), str(staged)], stdout=log, stderr=log, check=True, timeout=60)
    classes = list(shadow.rglob("*.class"))
    assert len(classes) == 1 and classes[0].relative_to(shadow).as_posix() == "forge/ai/ability/DrawAi.class"
    product = {"schema": "native-targeted-draw-one-source-one-class-v1", "base_build_id": identity["build_id"],
        "parent_content_id": pin["content_id"], "preimage_sha256": sha(here / "preimage/DrawAi.java"),
        "sources": [{"path": str(relative_source), "sha256": sha(staged)}],
        "patch_sha256": sha(here / "DrawAi.patch"),
        "payloads": [{"path": "forge/ai/ability/DrawAi.class", "sha256": sha(classes[0]),
                      "class_name": "forge.ai.ability.DrawAi"}]}
    canonical = json.dumps(product, sort_keys=True, separators=(",", ":")).encode()
    save(candidate / "MANIFEST.json", {"content_id": hashlib.sha256(canonical).hexdigest(), "identity": product})
    check_pins({**payloads, **base_pins, **dependency_pins})
    print(json.dumps(json.loads((candidate / "MANIFEST.json").read_text()), indent=2))
    raise SystemExit(0)

out = root / ("baseline" if mode == "baseline" else "candidate-gate")
assert not out.exists()
out.mkdir(mode=0o700)
for name in ("classes", "test-source", "home", "tmp"):
    (out / name).mkdir(mode=0o700)
for p in [here / "NativeTargetedDrawPolicyGate.java", old / "NativeTargetedDrawAudit.java"]:
    shutil.copyfile(p, out / "test-source" / p.name)
shutil.copyfile(here / "DECLARATION.json", out / "DECLARATION.json")
own_pins = {str(p): sha(p) for p in here.rglob("*") if p.is_file()}
candidate_pins = {}
if mode == "candidate":
    manifest = json.loads((candidate / "MANIFEST.json").read_text())
    assert manifest["identity"]["parent_content_id"] == pin["content_id"]
    for item in manifest["identity"]["payloads"]:
        candidate_pins[str(candidate / "shadow" / item["path"])] = item["sha256"]
    candidate_pins[str(candidate / "source" / relative_source)] = manifest["identity"]["sources"][0]["sha256"]
    check_pins(candidate_pins)
    runtime.insert(0, str(candidate / "shadow"))
cp = ":".join(runtime)
save(out / "BEFORE.json", {"actual_head": actual_head, "base_identity_sha256": sha(identity_path), "prefix": pin,
    "base_pins": base_pins, "dependency_pins": dependency_pins, "test_pins": own_pins,
    "candidate_pins": candidate_pins, "runtime_classpath": runtime, "native_clock": "unchanged"})
with (out / "compile.private.log").open("wb") as log:
    subprocess.run([str(j / "bin/javac"), "-J-Xmx512m", "-J-XX:ActiveProcessorCount=1", "--release", "17",
        "-implicit:none", "-sourcepath", str(out / "test-source"), "-cp", cp, "-d", str(out / "classes")]
        + [str(p) for p in sorted((out / "test-source").glob("*.java"))],
        stdout=log, stderr=log, check=True, timeout=60)
assert len(list((out / "classes").rglob("*.class"))) == 4
other_jvms = subprocess.check_output(["ps", "-eo", "comm="], text=True).splitlines().count("java")
assert other_jvms <= 1, "Would exceed parent maximum two native audit JVMs"
argv = ["timeout", "-k", "5s", "180", "strace", "--seccomp-bpf", "-f", "-qq", "-e", "trace=network",
    "-o", str(out / "network.private.strace"), "bwrap", "--unshare-user", "--unshare-net", "--unshare-pid",
    "--unshare-ipc", "--unshare-uts", "--die-with-parent", "--new-session"]
mounts = ["/usr", "/lib", "/lib64", "/bin", "/etc", str(cache), str(identity_path.parent), str(prefix)]
if mode == "candidate": mounts.append(str(candidate / "shadow"))
for p in mounts: argv += ["--ro-bind", p, p]
argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(out), str(out),
    "--chdir", str(k / "forge-gui-desktop"), "--clearenv", "--setenv", "PATH", str(j / "bin") + ":/usr/bin:/bin",
    "--setenv", "HOME", str(out / "home"), "--setenv", "LANG", "C.UTF-8", str(j / "bin/java"),
    "-Xmx1500m", "-XX:ActiveProcessorCount=1", "-Djava.awt.headless=true", "-Duser.home=" + str(out / "home"),
    "-Djava.io.tmpdir=" + str(out / "tmp"), "-Dsentry.dsn=", "-Xlog:class+load=info:file=" +
    str(out / "class-load.private.log") + ":uptime,level,tags", "--add-opens", "java.base/java.lang=ALL-UNNAMED",
    "-cp", str(out / "classes") + ":" + cp, "forge.evaluation.NativeTargetedDrawPolicyGate", str(out)]
started = time.monotonic()
with (out / "stdout.private.log").open("wb") as stdout, (out / "stderr.private.log").open("wb") as stderr:
    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
    save(out / "LAUNCH.private.json", {"pid": process.pid, "argv": argv, "other_java_processes": other_jvms})
    code = process.wait()
save(out / "PROCESS-CLOSED.json", {"exit": code, "seconds": time.monotonic()-started})
result = json.loads((out / "summary.private.json").read_text())
check_pins({**payloads, **base_pins, **dependency_pins, **own_pins, **candidate_pins})
origins = {}
for line in (out / "class-load.private.log").read_text().splitlines():
    match = re.search(r"\] (forge\.[\w.$]+) source: file:(.*)$", line)
    if match: origins[match[1]] = match[2].rstrip("/")
assert Path(origins["forge.ai.ability.DrawAi"]) == (candidate / "shadow" if mode == "candidate" else k / "forge-ai/target/classes")
assert Path(origins["forge.ai.PlayerControllerAi"]) == k / "forge-ai/target/classes"
assert Path(origins["forge.ai.AITest"]) == k / "forge-gui-desktop/target/test-classes"
for name in ("forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana"):
    assert Path(origins[name]) == prefix, (name, origins.get(name))
assert not re.search(r"connect\(.*sa_family=AF_INET6?", (out / "network.private.strace").read_text())
assert not re.search(r"TimeoutException|AI eval thread at timeout|AITimeoutTracker\$Expired",
                     (out / "stderr.private.log").read_text())
cohorts = {}
for row in result["cases"]:
    count = cohorts.setdefault(row["cohort"], {"passed": 0, "red": 0})
    count["passed" if row["passed"] else "red"] += 1
verified = {"exit": code, "seconds": time.monotonic()-started, "cohorts": cohorts, "errors": result["errors"],
    "base_identity_sha256": sha(identity_path), "prefix_content_id": pin["content_id"],
    "candidate_content_id": manifest["content_id"] if mode == "candidate" else None,
    "pins_unchanged": True, "native_clock": "unchanged", "network_inet_connects": 0, "natural_games": 0,
    "origins": {name: origins[name] for name in ("forge.ai.ability.DrawAi", "forge.ai.PlayerControllerAi", "forge.ai.AITest",
        "forge.ai.ComputerUtil", "forge.ai.ComputerUtilCost", "forge.ai.ComputerUtilMana")}}
save(out / "VERIFIED-CLOSED.json", verified)
print(json.dumps(verified, indent=2), flush=True)
assert result["errors"] == 0, "STOP: fixture/engine error; preserve initial ledger"
assert len(result["cases"]) == 26 and code in (0, 1)
raise SystemExit(code)
