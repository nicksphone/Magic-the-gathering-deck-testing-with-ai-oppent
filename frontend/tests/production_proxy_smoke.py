#!/usr/bin/env python3
"""Smoke the built frontend and real API through a temporary HTTPS reverse proxy.

Run with --backend-dir pointing to a disposable tracked-source copy, never the
developer backend directory. Certificate and SQLite writes stay in that copy.
"""

import argparse
import http.client
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, data=None, context=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, context=context, timeout=25) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        raise AssertionError(f"{url}: HTTP {error.code}: {error.read()[:500]!r}") from error


def seed_island(python, backend_dir):
    code = (
        "from card_data.fallback_cards import fallback_card_payload; "
        "from persistence.db import init_db, engine; "
        "from persistence.repository import Repository; "
        "from sqlmodel import Session; "
        "init_db(); "
        "card=fallback_card_payload('Island'); "
        "session=Session(engine); "
        "Repository(session).upsert_card(dict(card, scryfall_id='routing-smoke-island', name='Island', "
        "image_uri='/card-images/generic-token-creature.svg')); "
        "session.close()"
    )
    subprocess.run([python, "-c", code], cwd=backend_dir, check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-dir", type=Path, required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--browser", action="store_true", help="also load the HTTPS page with headless Chromium")
    parser.add_argument("--cross-origin", action="store_true", help="also build and smoke an explicit HTTPS backend origin")
    args = parser.parse_args()
    backend_dir = args.backend_dir.resolve()
    dist_dir = args.dist_dir.resolve()
    live_backend = Path(__file__).resolve().parents[2] / "backend"
    if backend_dir == live_backend.resolve():
        parser.error("backend-dir must be a disposable copy, not the live backend")
    if not (backend_dir / "main.py").is_file() or not (dist_dir / "index.html").is_file():
        parser.error("backend main.py and built dist/index.html are required")

    seed_island(args.python, backend_dir)
    backend_port = free_port()
    with tempfile.TemporaryDirectory(prefix="mtg-https-smoke-") as temp:
        temp_path = Path(temp)
        cert, key = temp_path / "cert.pem", temp_path / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with (temp_path / "backend.log").open("wb") as log:
            backend = subprocess.Popen([
                args.python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(backend_port),
            ], cwd=backend_dir, stdout=log, stderr=subprocess.STDOUT)
            server = None
            cross_server = None
            cross_built = False
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if backend.poll() is not None:
                        raise RuntimeError("Backend exited during startup")
                    try:
                        if request(f"http://127.0.0.1:{backend_port}/health")[0] == 200:
                            break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Backend health did not become ready")

                class Proxy(SimpleHTTPRequestHandler):
                    backend_only = False

                    def __init__(self, *handler_args, **handler_kwargs):
                        super().__init__(*handler_args, directory=str(dist_dir), **handler_kwargs)

                    def log_message(self, *_args):
                        pass

                    def do_POST(self):
                        self.proxy()

                    def do_GET(self):
                        if self.backend_only or self.path.startswith("/api/") or self.path.startswith("/card-images/"):
                            self.proxy()
                        else:
                            super().do_GET()

                    def do_OPTIONS(self):
                        self.proxy()

                    def proxy(self):
                        if not (self.backend_only or self.path.startswith("/api/") or self.path.startswith("/card-images/")):
                            self.send_error(404)
                            return
                        path = self.path[4:] if self.path.startswith("/api/") else self.path
                        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                        conn = http.client.HTTPConnection("127.0.0.1", backend_port, timeout=25)
                        try:
                            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
                            for name in ("Origin", "Access-Control-Request-Method", "Access-Control-Request-Headers"):
                                if self.headers.get(name):
                                    headers[name] = self.headers[name]
                            conn.request(self.command, path, body=body, headers=headers)
                            upstream = conn.getresponse()
                            payload = upstream.read()
                            self.send_response(upstream.status)
                            self.send_header("Content-Type", upstream.getheader("Content-Type", "application/octet-stream"))
                            self.send_header("Content-Length", str(len(payload)))
                            for name in ("Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers", "Access-Control-Allow-Credentials", "Vary"):
                                if upstream.getheader(name):
                                    self.send_header(name, upstream.getheader(name))
                            self.end_headers()
                            self.wfile.write(payload)
                        finally:
                            conn.close()

                class BackendProxy(Proxy):
                    backend_only = True

                server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert, key)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                base = f"https://127.0.0.1:{server.server_port}"
                client_context = ssl._create_unverified_context()  # Temporary self-signed test certificate.

                status, index, _ = request(base + "/", context=client_context)
                assert status == 200 and b"/assets/" in index
                asset = re.search(rb'src="([^"]+\.js)"', index)
                assert asset, "Built JS asset was not referenced by index.html"
                assert request(base + asset.group(1).decode(), context=client_context)[0] == 200
                assert json.loads(request(base + "/api/health", context=client_context)[1])["ok"]
                status, image, media_type = request(base + "/card-images/generic-token-creature.svg", context=client_context)
                assert status == 200 and b"<svg" in image and "svg" in media_type

                imported = json.loads(request(base + "/api/decks/import", {
                    "name": "HTTPS routing smoke", "deck_text": "60 Island", "source": "smoke",
                }, context=client_context)[1])
                assert imported["deck_id"] and not imported["errors"], imported
                deck = [{"quantity": 60, "card_name": "Island"}]
                started = json.loads(request(base + "/api/matches/start", {
                    "deck_a": deck, "deck_b": deck, "controller_a": "human", "controller_b": "ai",
                    "mode": "player_vs_ai", "best_of": 3, "seed": 17,
                }, context=client_context)[1])
                assert started["players"]["2"]["hand"] == []
                acted = json.loads(request(base + f"/api/matches/{started['id']}/action", {
                    "player_id": 1, "action": {"type": "keep_hand", "bottom_card_ids": []},
                }, context=client_context)[1])
                assert 1 in acted["kept_hands"]

                def browser_check(url, profile):
                    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
                    if not chromium:
                        raise RuntimeError("Chromium is required for --browser")
                    page = subprocess.run([
                        chromium, "--headless", "--no-sandbox", "--disable-gpu", "--ignore-certificate-errors",
                        "--disable-dev-shm-usage", "--virtual-time-budget=5000", "--dump-dom",
                        f"--user-data-dir={temp_path / profile}", url,
                    ], capture_output=True, text=True, timeout=35)
                    assert page.returncode == 0 and "Backend online" in page.stdout, page.stderr[-1000:]
                    assert "Deck load failed" not in page.stdout

                if args.browser:
                    browser_check(base + "/", "chromium-same-origin")
                print("PASS same-origin HTTPS built frontend, API health/import/start/action, card media" + (", Chromium page" if args.browser else ""))

                if args.cross_origin:
                    cross_server = ThreadingHTTPServer(("127.0.0.1", 0), BackendProxy)
                    cross_server.socket = context.wrap_socket(cross_server.socket, server_side=True)
                    threading.Thread(target=cross_server.serve_forever, daemon=True).start()
                    origin = f"https://127.0.0.1:{cross_server.server_port}"
                    env = os.environ.copy()
                    env["VITE_API_BASE_URL"] = origin
                    cross_built = True
                    subprocess.run(["npm", "run", "build"], cwd=dist_dir.parent, env=env, check=True, capture_output=True)
                    cross_index = request(base + "/", context=client_context)[1]
                    cross_asset = re.search(rb'src="([^"]+\.js)"', cross_index)
                    assert cross_asset
                    bundle = request(base + cross_asset.group(1).decode(), context=client_context)[1]
                    assert origin.encode() in bundle, "Configured API origin was not included in the built artifact"
                    assert json.loads(request(origin + "/health", context=client_context)[1])["ok"]
                    assert b"<svg" in request(origin + "/card-images/generic-token-creature.svg", context=client_context)[1]
                    imported_cross = json.loads(request(origin + "/decks/import", {
                        "name": "HTTPS cross-origin smoke", "deck_text": "60 Island", "source": "smoke",
                    }, context=client_context)[1])
                    assert imported_cross["deck_id"] and not imported_cross["errors"]
                    started_cross = json.loads(request(origin + "/matches/start", {
                        "deck_a": deck, "deck_b": deck, "controller_a": "human", "controller_b": "ai",
                        "mode": "player_vs_ai", "best_of": 3, "seed": 19,
                    }, context=client_context)[1])
                    acted_cross = json.loads(request(origin + f"/matches/{started_cross['id']}/action", {
                        "player_id": 1, "action": {"type": "keep_hand", "bottom_card_ids": []},
                    }, context=client_context)[1])
                    assert 1 in acted_cross["kept_hands"]
                    if args.browser:
                        browser_check(base + "/?cross-origin=1", "chromium-cross-origin")
                    print("PASS configured HTTPS cross-origin API health/import/start/action, card media" + (", Chromium page" if args.browser else ""))
            except Exception:
                print((temp_path / "backend.log").read_text(errors="replace")[-2000:])
                raise
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                if cross_server:
                    cross_server.shutdown()
                    cross_server.server_close()
                backend.terminate()
                try:
                    backend.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    backend.kill()
                    backend.wait()
                if cross_built:
                    subprocess.run(["npm", "run", "build"], cwd=dist_dir.parent, check=True, capture_output=True)


if __name__ == "__main__":
    main()
