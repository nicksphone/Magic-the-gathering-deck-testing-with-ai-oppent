# SPDX-License-Identifier: GPL-3.0-or-later
# Artifact integrity for the Forge Team/Card-Forge-derived source delta.
"""Read-only package check; does not compile, play, install or promote an AI."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTENT = "f4c8d41f6de9016c194551b2bfcedad9f61ddf2fdf556eb88e16a6618d40dfb5"
FILES = {
    "README.md", "NOTICE", "LICENSE", "PAYLOAD.json", "SOURCE-PINS.json",
    "CANONICAL-PINS.json", "gain-denial.patch", "selfcheck.py",
    "NativeSkullcrackResponse6.java", "NativeSkullcrackPreservation10.java",
    *{"canonical/" + name + ".txt" for name in (
        "skullcrack", "sheoldred_the_apocalypse", "mountain",
        "leyline_of_sanctity", "sulfuric_vortex", "tainted_remedy")},
}


def check(root=ROOT):
    pins = json.loads((root / "PINS.json").read_text())
    if set(pins) != FILES:
        raise ValueError("Unexpected package input path")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise ValueError("Package symlinks are not supported")
    if {p.relative_to(root).as_posix() for p in entries if p.is_file()} != FILES | {"PINS.json"}:
        raise ValueError("Package has missing or extra files")
    for name, digest in pins.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Package byte mismatch: " + name)
    payload = json.loads((root / "PAYLOAD.json").read_text())
    if hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != CONTENT:
        raise ValueError("Wrong qualified payload")
    source = json.loads((root / "SOURCE-PINS.json").read_text())
    if source["candidate_content_id"] != CONTENT or len(source["changed"]) != 2:
        raise ValueError("Wrong source delta")
    for name, spec in source["changed"].items():
        if payload["sources"][name] != spec["postimage"] or payload["classes"][spec["class"]] != spec["class_postimage"]:
            raise ValueError("Source/class declaration mismatch")
    for name, spec in json.loads((root / "CANONICAL-PINS.json").read_text())["files"].items():
        if name not in FILES or pins[name] != spec["sha256"]:
            raise ValueError("Canonical declaration mismatch")
    return {"artifact_integrity": "PASS", "files": len(pins), "native_execution": False,
            "installation_or_promotion": False, "candidate_content_id": CONTENT}


if __name__ == "__main__":
    print(json.dumps(check()))
