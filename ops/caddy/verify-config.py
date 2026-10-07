#!/usr/bin/env python3
"""Native adaptation and operator prechecks only: no TLS client or SQL gate."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("operator_run", HERE / "run.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


def guard(event, args):
    if event.startswith("sqlite3.") or event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        raise RuntimeError("SQL/socket forbidden in configuration check")


sys.addaudithook(guard)
os.umask(0o077)
caddy = Path(os.environ["MTG_CADDY_BINARY"]).resolve()
with tempfile.TemporaryDirectory(prefix="mtg-caddy-config-") as directory:
    root = Path(directory)
    (root / "dist").mkdir()
    (root / "dist/index.html").write_text("<html>configuration-check only</html>")
    hashed = subprocess.run([str(caddy), "hash-password", "--algorithm", "bcrypt", "--bcrypt-cost", "10"], input=secrets.token_urlsafe(32) + "\n", text=True, capture_output=True, check=True).stdout.strip()
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost", "-keyout", str(root / "key.pem"), "-out", str(root / "cert.pem")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    config = dict(origin="https://localhost:18443", backend_port=18444, runtime=str(root / "runtime"), python=sys.executable, caddy=str(caddy), dist=str(root / "dist"), cert=str(root / "cert.pem"), key=str(root / "key.pem"), user="operator", password_hash=hashed)
    config_path = root / "operator.json"
    config_path.write_text(json.dumps(config))
    os.environ["MTG_OPERATOR_CONFIG"] = str(config_path)
    checked = operator.settings()
    assert str(checked["python"]) == sys.executable
    backend_env, caddy_env = operator.environment(checked)
    assert backend_env["MTG_TRUSTED_ORIGINS"] == config["origin"]
    assert not any("AUTH" in key or "TLS" in key for key in backend_env)
    adapted = subprocess.run([str(caddy), "adapt", "--config", str(HERE / "Caddyfile"), "--adapter", "caddyfile"], env=caddy_env, capture_output=True, check=True)
    tree = json.loads(adapted.stdout)
    assert tree["admin"]["disabled"] is True
    assert tree["admin"]["config"]["persist"] is False
    assert not tree["apps"]["tls"].get("automation", {}).get("policies")
    servers = tree["apps"]["http"]["servers"]
    assert len(servers) == 1
    server = next(iter(servers.values()))
    assert server["listen"] == ["127.0.0.1:18443"]
    assert server["automatic_https"]["disable"] is True
    assert server["protocols"] == ["h1", "h2"]
    assert server["enable_full_duplex"] is True
    # Parse the native route tree, not string guesses about Caddyfile ordering.
    handlers = server["routes"][0]["handle"][0]["routes"][0]["handle"][0]["routes"][0]["handle"]
    assert handlers[0]["handler"] == "authentication"
    serialized = json.dumps(tree)
    assert '"strip_path_prefix": "/api"' in serialized
    assert '"/api/*"' in serialized and '"/card-images/*"' in serialized
    assert '"strip_path_prefix": "/card-images"' not in serialized
    assert serialized.count('"delete": ["Authorization"]') == 2
    assert '"root":' in serialized and '"file_server"' in serialized
    native = subprocess.run([str(caddy), "validate", "--config", str(HERE / "Caddyfile"), "--adapter", "caddyfile"], env=caddy_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert native.returncode == 0
    lock = operator.prepare(checked)
    assert not (checked["runtime"] / "backend/mtg_lab.db").exists()
    try:
        operator.prepare(checked)
    except BlockingIOError:
        pass
    else:
        raise AssertionError("Concurrent supervisor lock accepted")
    lock.close()
    restarted = operator.prepare(checked)
    restarted.close()

    def rejected_reuse(label):
        try:
            acquired = operator.prepare(checked)
        except (ValueError, OSError):
            print("PASS rejected runtime reuse: " + label)
        else:
            acquired.close()
            raise AssertionError("Unsafe runtime reuse accepted")

    runtime = checked["runtime"]
    for name in ("source.sha256", "operator.lock", "backend"):
        path = runtime / name
        saved = runtime / (name + ".saved")
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=name == "backend")
        rejected_reuse(name + " symlink")
        path.unlink()
        saved.rename(path)
    receipt = runtime / "source.sha256"
    original = receipt.read_bytes()
    receipt.write_text("modified\n")
    rejected_reuse("modified receipt")
    receipt.write_bytes(original)
    fixture = runtime / "backend/ai/data/log_priors.json"
    original = fixture.read_bytes()
    fixture.write_bytes(original + b"\n")
    rejected_reuse("modified non-Python fixture")
    fixture.write_bytes(original)
    fixture.unlink()
    fixture.symlink_to(operator.SOURCE / "backend/ai/data/log_priors.json")
    rejected_reuse("non-Python fixture symlink")
    fixture.unlink()
    fixture.write_bytes(original)
    extra = runtime / "backend/unexpected-fixture.json"
    extra.write_text("{}")
    rejected_reuse("unexpected non-Python file")
    extra.unlink()
    image = runtime / "backend/card_data/image_cache"
    image.symlink_to(root / "dist", target_is_directory=True)
    rejected_reuse("mutable media directory symlink")
    image.unlink()
    database = runtime / "backend/mtg_lab.db"
    database.symlink_to(root / "cert.pem")
    rejected_reuse("mutable database symlink")
    database.unlink()
    image.mkdir()
    (image / "owned.svg").write_text("<svg/>")
    (runtime / "backend/diagnostics").mkdir()
    (runtime / "backend/diagnostics/owned.json").write_text("{}")
    acquired = operator.prepare(checked)
    acquired.close()
    print("PASS accepted explicitly mutable regular media/diagnostic outputs")
    for name, value in [("origin", "http://localhost:18443"), ("origin", "https://localhost:18443,https://evil.example"), ("backend_port", 18443), ("backend_port", 0), ("user", "bad user"), ("password_hash", "plaintext"), ("runtime", str(operator.SOURCE)), ("caddy", str(root / "cert.pem"))]:
        bad = dict(config, **{name: value})
        config_path.write_text(json.dumps(bad))
        try:
            operator.settings()
        except (ValueError, OSError):
            pass
        else:
            raise AssertionError("Invalid operator configuration accepted")
    config_path.write_text(json.dumps(config))
    config_path.chmod(0o644)
    try:
        operator.settings()
    except ValueError:
        pass
    else:
        raise AssertionError("Public secret file accepted")
print("PASS native adaptation/validation, private runtime pin/restart/lock and operator prechecks; no listeners, SQL or client TLS/auth qualification.")
