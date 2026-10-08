#!/usr/bin/env python3
"""Foreground private-loopback packaging; no services or global trust changes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit

CADDY_SHA256 = "678ade3bfc088749c81a681adc603333ee0bb023b6a6cfe3c0f58bef8ff854e9"
SOURCE = Path(__file__).resolve().parents[2]


def require(condition):
    if not condition:
        raise ValueError("operator precheck failed")


def private_file(path):
    path = Path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid())
    require(info.st_mode & 0o077 == 0 and info.st_nlink == 1)
    return path.resolve()


MUTABLE_DIRS = {"card_data/image_cache", "diagnostics", "training_runs"}
SQL_FILES = {"mtg_lab.db", "mtg_lab.db-wal", "mtg_lab.db-shm", "mtg_lab.db-journal"}


def inventory(root, *, runtime=False):
    require(root.is_dir() and not root.is_symlink())
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            require(not path.is_symlink() and info.st_uid == os.getuid())
            require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
            if path.is_file():
                require(info.st_nlink == 1)
            relative = path.relative_to(root).as_posix()
            owner_artifact = path.is_file() and (relative == "mtg_lab.db.capacity-owner.lock" or
                re.fullmatch(r"mtg_lab\.db\.before-capacity-[0-9a-f]{32}\.db", relative) is not None)
            mutable = relative in SQL_FILES or owner_artifact or any(relative == p or relative.startswith(p + "/") for p in MUTABLE_DIRS)
            if runtime and mutable:
                continue
            if not runtime and (name in {"__pycache__", ".pytest_cache", "image_cache"} or name.endswith(".pyc")):
                if name in dirs:
                    dirs.remove(name)
                continue
            require(runtime or relative not in SQL_FILES)
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
    return result


def source_pin():
    return hashlib.sha256(json.dumps(inventory(SOURCE / "backend"), sort_keys=True).encode()).hexdigest()


def settings():
    config = json.loads(private_file(os.environ["MTG_OPERATOR_CONFIG"]).read_text())
    require(set(config) == {"origin", "backend_port", "runtime", "python", "caddy", "dist", "cert", "key", "user", "password_hash"})
    origin = config["origin"]
    sys.path.insert(0, str(SOURCE / "backend"))
    from browser_origin import trusted_origins
    require(trusted_origins(origin) == (origin,) and origin.startswith("https://"))
    site = urlsplit(origin)
    require(site.port is not None and 1024 <= site.port <= 65535)
    port = config["backend_port"]
    require(type(port) is int and 1024 <= port <= 65535 and port != site.port)
    require(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", config["user"]) is not None)
    require(re.fullmatch(r"\$2[aby]\$(?:1[0-6])\$[./A-Za-z0-9]{53}", config["password_hash"]) is not None)
    for name in ("runtime", "python", "caddy", "dist", "cert", "key"):
        path = Path(config[name])
        require(path.is_absolute() and not any(c.isspace() or c in '"{}#\\' for c in str(path)))
        if name in {"runtime", "key"}:
            require(not path.is_symlink())
        if name == "runtime":
            require(path.resolve() == path)
        # Resolving a venv's interpreter symlink would silently select system Python.
        config[name] = path if name == "python" else path.resolve()
    runtime = config["runtime"]
    require(not runtime.is_relative_to(SOURCE) and runtime != Path("/") and runtime != Path.home())
    require(not SOURCE.is_relative_to(runtime) and not config["dist"].is_relative_to(runtime))
    require(not config["key"].is_relative_to(config["dist"]) and not private_file(os.environ["MTG_OPERATOR_CONFIG"]).is_relative_to(config["dist"]))
    require(config["dist"].is_dir() and (config["dist"] / "index.html").is_file())
    require(config["python"].is_file() and os.access(config["python"], os.X_OK))
    require(hashlib.sha256(config["caddy"].read_bytes()).hexdigest() == CADDY_SHA256)
    config["key"] = private_file(config["key"])
    require(config["cert"].is_file())
    # Reject NFS/other remote runtime storage; Linux mountinfo lists the effective mount.
    probe = runtime
    while not probe.exists():
        probe = probe.parent
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = Path(left.split()[4].replace("\\040", " "))
        if probe.is_relative_to(mount):
            mounts.append((len(str(mount)), right.split()[0]))
    require(max(mounts)[1] in {"ext4", "xfs", "btrfs", "tmpfs", "overlay"})
    return config


def prepare(config):
    runtime = config["runtime"]
    require(not runtime.is_symlink() and runtime.resolve() == runtime)
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = runtime.stat()
    require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0)
    lock = os.fdopen(os.open(runtime / "operator.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "a")
    try:
        info = os.fstat(lock.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_mode & 0o077 == 0)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pin = source_pin()
        receipt = runtime / "source.sha256"
        require(not receipt.is_symlink() and not (runtime / "backend").is_symlink())
        if receipt.exists():
            require(private_file(receipt).read_text().strip() == pin)
        else:
            require(not (runtime / "backend").exists())
            shutil.copytree(SOURCE / "backend", runtime / "backend", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.db*", "*.sqlite*", "image_cache"))
            receipt.write_text(pin + "\n")
        require(inventory(runtime / "backend", runtime=True) == inventory(SOURCE / "backend"))
        return lock
    except BaseException:
        lock.close()
        raise


def environment(config):
    base = {"PATH": "/usr/bin:/bin", "HOME": str(config["runtime"]), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    backend = dict(base, MTG_TRUSTED_ORIGINS=config["origin"])
    caddy = dict(base, XDG_DATA_HOME=str(config["runtime"] / "caddy-data"), XDG_CONFIG_HOME=str(config["runtime"] / "caddy-config"),
                 MTG_SITE_ORIGIN=config["origin"], MTG_BACKEND_PORT=str(config["backend_port"]), MTG_FRONTEND_DIST=str(config["dist"]),
                 MTG_TLS_CERT=str(config["cert"]), MTG_TLS_KEY=str(config["key"]), MTG_AUTH_USER=config["user"], MTG_AUTH_HASH=config["password_hash"])
    return backend, caddy


def main():
    os.umask(0o077)
    require(sys.argv[1:] in ([], ["--check"]))
    config = settings()
    _, caddy_env = environment(config)
    # Provisioning validates the supplied certificate but never runs a listener.
    checked = subprocess.run([str(config["caddy"]), "validate", "--config", str(Path(__file__).with_name("Caddyfile")), "--adapter", "caddyfile"], env=caddy_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    require(checked.returncode == 0)
    if sys.argv[1:] == ["--check"]:
        print("Operator configuration valid; no server started.")
        return 0
    lock = prepare(config)
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    backend_env, caddy_env = environment(config)
    result = 1
    try:
        children.append(subprocess.Popen([str(config["python"]), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(config["backend_port"]), "--workers", "1", "--no-access-log", "--no-proxy-headers", "--log-level", "critical"], cwd=config["runtime"] / "backend", env=backend_env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        children.append(subprocess.Popen([str(config["caddy"]), "run", "--config", str(Path(__file__).with_name("Caddyfile")), "--adapter", "caddyfile"], cwd=config["runtime"], env=caddy_env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        print("Private loopback supervisor running; readiness is not yet established.", flush=True)
        while not stopping and all(child.poll() is None for child in children):
            time.sleep(0.1)
        result = 0 if stopping else 1
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for child in children:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
                result = 1
                print("Child exceeded shutdown timeout; recovery inspection required.", file=sys.stderr)
        lock.close()
    return result


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never print config values, subprocess diagnostics, credentials or key paths.
        print("Operator launch/check failed; inspect private configuration locally.", file=sys.stderr)
        sys.exit(1)
