"""Read-only verifier for the qualified CPython 3.12/Linux wheel sidecar."""
import argparse
from email.parser import BytesParser
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tarfile
import zipfile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename


ARCHIVE_SHA256 = "bed4f930c4a0e9be876a52ea7193ddf70d03c0c969e184bbcbef12fd8cbb3330"
REQUIREMENTS_SHA256 = "7aa9f2b409551322171d8fdc0fcdde02fc5f38aedacdb9c904d6e47966c95b97"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def supported(environment):
    return (environment["implementation_name"] == "cpython"
            and environment["python_version"] == "3.12"
            and environment["sys_platform"] == "linux"
            and environment["platform_machine"] == "x86_64"
            and platform.libc_ver() == ("glibc", "2.39"))


def parse_lock(text):
    result = {}
    options = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line in ("--require-hashes", "--only-binary=:all:"):
            options.append(line)
            continue
        match = re.fullmatch(r"([a-z0-9]+(?:-[a-z0-9]+)*)==([^\s*;]+) --hash=sha256:([0-9a-f]{64})", line)
        require(match is not None, "Lock needs one canonical exact pin and SHA256 per line")
        name, version, sha256 = match.groups()
        require(name not in result, "Duplicate lock package")
        result[name] = {"version": version, "sha256": sha256}
    require(sorted(options) == ["--only-binary=:all:", "--require-hashes"], "Required lock options missing or duplicate")
    require("pip" not in result, "Installer pip is not an application dependency")
    return result


def verify(archive, provenance, requirements, lock, installed=False):
    environment = default_environment()
    environment["extra"] = ""
    require(supported(environment), "Only CPython 3.12/Linux x86_64/glibc 2.39 is qualified")
    require(digest(archive) == ARCHIVE_SHA256, "Recorded wheel archive SHA256 mismatch")
    require(digest(requirements) == REQUIREMENTS_SHA256, "Declared requirements preimage mismatch")
    proof = json.loads(provenance.read_text())
    require(len(proof) == 29, "Expected 29 archived wheels including installer")
    compatible = set(sys_tags())
    wheels = {}
    filenames = set()
    with tarfile.open(archive) as source:
        for member in source:
            if not member.name.endswith(".whl"):
                continue
            path = PurePosixPath(member.name)
            require(member.isfile() and path.parts == ("wheels", path.name), "Unexpected wheel member path/type")
            filename = path.name
            require(filename in proof and filename not in filenames, "Unrecorded or duplicate wheel")
            filenames.add(filename)
            data = source.extractfile(member).read()
            sha256 = hashlib.sha256(data).hexdigest()
            require(sha256 == proof[filename]["sha256"] and len(data) == proof[filename]["bytes"], "Recorded wheel hash/size mismatch")
            name, version, _, tags = parse_wheel_filename(filename)
            require(name not in wheels and bool(tags & compatible), "Duplicate package or incompatible wheel tags")
            with zipfile.ZipFile(io.BytesIO(data)) as wheel:
                metadata_paths = [p for p in wheel.namelist() if p.endswith(".dist-info/METADATA")]
                require(len(metadata_paths) == 1, "Expected one wheel METADATA file")
                raw = wheel.read(metadata_paths[0])
            info = BytesParser().parsebytes(raw)
            require(canonicalize_name(info["Name"]) == name and info["Version"] == str(version), "Wheel filename/METADATA mismatch")
            require(SpecifierSet(info.get("Requires-Python", "")).contains(environment["python_full_version"]), "Requires-Python mismatch")
            if installed and name != "pip":
                distribution = metadata.distribution(name)
                paths = [distribution.locate_file(p) for p in distribution.files or []
                         if str(p).endswith(".dist-info/METADATA")]
                require(len(paths) == 1 and distribution.version == str(version)
                        and paths[0].read_bytes() == raw, "Installed version/raw METADATA mismatch")
            wheels[name] = {"version": str(version), "sha256": sha256, "bytes": len(data),
                            "filename": filename, "archive_path": member.name,
                            "tags": sorted(map(str, tags)), "requires_python": info.get("Requires-Python"),
                            "requires_dist": info.get_all("Requires-Dist", []),
                            "metadata_sha256": hashlib.sha256(raw).hexdigest()}
    require(filenames == set(proof), "Missing recorded wheel")
    direct = {}
    for line in requirements.read_text().splitlines():
        dependency = Requirement(line)
        pins = list(dependency.specifier)
        name = canonicalize_name(dependency.name)
        require(not dependency.url and not dependency.extras and dependency.marker is None
                and len(pins) == 1 and pins[0].operator == "==" and name not in direct,
                "Unexpected direct requirement")
        require(name in wheels and pins[0].version == wheels[name]["version"], "Direct pin mismatch")
        direct[name] = pins[0].version
    require(len(direct) == 9, "Expected nine declared direct requirements")
    closure = set()
    pending = list(direct)
    active, inactive = [], []
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        closure.add(name)
        for text in wheels[name]["requires_dist"]:
            dependency = Requirement(text)
            edge = {"from": name, "requirement": text}
            if dependency.marker and not dependency.marker.evaluate(environment):
                inactive.append(edge)
                continue
            target = canonicalize_name(dependency.name)
            require(not dependency.url and not dependency.extras and target in wheels,
                    "Missing dependency or unqualified URL/extra")
            require(dependency.specifier.contains(wheels[target]["version"]), "Transitive version mismatch")
            active.append(dict(edge, to=target))
            pending.append(target)
    require(closure == set(wheels) - {"pip"}, "Application dependency closure mismatch")
    locked = parse_lock(lock.read_text())
    require(set(locked) == closure, "Lock missing/extra application packages")
    for name in closure:
        require(locked[name] == {key: wheels[name][key] for key in ("version", "sha256")}, "Lock version/hash mismatch")
    return {"scope": "verifier only; no install, resolver, download, SQL or network",
            "environment": environment, "glibc": platform.libc_ver(), "direct_pins": direct,
            "application_packages": len(closure), "archived_wheels": len(wheels),
            "installer_excluded": "pip==" + wheels["pip"]["version"],
            "installed_app_metadata_checked": installed, "wheels": wheels,
            "active_dependencies": active, "inactive_marked_dependencies": inactive,
            "input_sha256": {"archive": digest(archive), "provenance": digest(provenance),
                             "requirements": digest(requirements), "lock": digest(lock)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "provenance", "requirements", "lock"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--installed", action="store_true", help="Also compare raw installed app METADATA")
    args = parser.parse_args()
    try:
        result = verify(args.archive, args.provenance, args.requirements, args.lock, args.installed)
    except (ValueError, OSError, KeyError, metadata.PackageNotFoundError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, "Hash-lock verification failed: " + type(error).__name__ + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
