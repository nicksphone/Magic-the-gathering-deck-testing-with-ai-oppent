#!/usr/bin/env python3
"""REVIEW ONLY. Execution requires an explicit parent SQL lease, never idle alone."""
import base64
from contextlib import closing
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
assert json.loads((ROOT / "ACTIVATION.json").read_text())["https"] is True, "Inactive HTTPS candidate"
SOURCE = ROOT / "source"
PRIVATE = ROOT / "private-gate"
RUNTIME = ROOT / "runtime-gate"
EVIDENCE = ROOT / "evidence/runtime-gate"
PYTHON = Path('/home/nick/.local/share/mtg-deck-testing-lab/runtimes/app-py312-certifi20261019-20261021-iMMqrycK/venv/bin/python')
ORIGIN = "https://localhost:48343"
SUPERVISORS = []
PIDS = set()
IDENTITIES = {}
CLOSURE_ISSUES = []
SIGNALS = []
RESULTS = []


def check(condition, label):
    RESULTS.append({"check": label, "passed": bool(condition)})
    if not condition:
        raise AssertionError(label)


def public_ledger():
    path = EVIDENCE / "backend.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def wait_atomic_rejections(required):
    # The actual response precedes the observer's post-response snapshot and append.
    deadline = time.monotonic() + 5
    previous = 0
    while True:
        if time.monotonic() >= deadline:
            raise AssertionError("atomic rejection completion deadline")
        rejected = [row for row in public_ledger() if row.get("event") == "atomic_rejection"]
        for row in rejected:
            if (set(row) != {"event", "status", "observations", "complete_root_controller_sql_equal"}
                    or row["status"] != [403] or type(row["observations"]) is not dict
                    or set(row["observations"]) != {"body", "dependency", "sql", "action", "sync"}
                    or any(type(value) is not int or value != 0 for value in row["observations"].values())
                    or row["complete_root_controller_sql_equal"] is not True):
                raise AssertionError("atomic rejection completion contains invalid record")
        if len(rejected) > required or len(rejected) < previous:
            raise AssertionError("atomic rejection completion has invalid record count")
        if len(rejected) == required:
            return rejected
        previous = len(rejected)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("atomic rejection completion deadline")
        time.sleep(min(0.2, remaining))


def identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"start_ticks": fields[19], "pgid": int(fields[2])}


def capture(pid):
    if CLOSURE_ISSUES:
        raise AssertionError("owned process admission blocked by latched identity fault")
    try:
        captured = identity(pid)
    except FileNotFoundError:
        return
    previous = IDENTITIES.get(pid)
    if previous is not None and previous["start_ticks"] != captured["start_ticks"]:
        CLOSURE_ISSUES.append("capture_epoch_mismatch_not_signalled")
        raise AssertionError("owned process PID epoch changed before admission")
    PIDS.add(pid)
    check(captured["pgid"] == pid, "owned process is its captured group leader")
    IDENTITIES[pid] = captured


def capture_children(supervisor):
    if supervisor.poll() is not None:
        return
    try:
        if identity(supervisor.pid) != IDENTITIES.get(supervisor.pid):
            CLOSURE_ISSUES.append("supervisor_identity_mismatch")
            return
    except (FileNotFoundError, PermissionError):
        CLOSURE_ISSUES.append("supervisor_identity_inaccessible")
        return
    path = Path(f"/proc/{supervisor.pid}/task/{supervisor.pid}/children")
    if path.exists():
        for value in path.read_text().split():
            pid = int(value)
            try:
                captured = identity(pid)
            except FileNotFoundError:
                continue
            previous = IDENTITIES.get(pid)
            if previous is not None and previous["start_ticks"] != captured["start_ticks"]:
                CLOSURE_ISSUES.append("child_epoch_mismatch_not_signalled")
                continue
            if previous is not None and CLOSURE_ISSUES:
                continue
            PIDS.add(pid)
            IDENTITIES[pid] = captured
            # Validation/pre-exec children inherit the supervisor group, not a service group.
            if captured["pgid"] == pid:
                check(captured["pgid"] == pid, "owned process is its captured group leader")
            elif captured["pgid"] != IDENTITIES[supervisor.pid]["pgid"]:
                CLOSURE_ISSUES.append("child_foreign_pgid_not_signalled")


def signal_owned(pid, sig):
    outcome = "absent"
    try:
        actual = identity(pid)
        if actual != IDENTITIES.get(pid) or actual["pgid"] != pid:
            outcome = "identity_mismatch_not_signalled"
            CLOSURE_ISSUES.append(outcome)
        else:
            os.killpg(actual["pgid"], sig)
            outcome = "matching_identity_signalled"
    except (FileNotFoundError, ProcessLookupError):
        pass
    except (PermissionError, OSError):
        outcome = "inaccessible_not_signalled"
        CLOSURE_ISSUES.append(outcome)
    SIGNALS.append({"pid": pid, "signal": int(sig), "outcome": outcome})


def timeout_signal(signum, frame):
    raise RuntimeError("Gate time budget interrupted")


def valid_listeners(listening, children):
    rows = [line.split() for line in listening.splitlines() if line.strip()]
    if len(rows) != 2 or any(len(row) < 6 or row[0] != "LISTEN" for row in rows):
        return False
    local = {row[3] for row in rows}
    owners = [set(map(int, re.findall(r"pid=(\d+)", " ".join(row[5:])))) for row in rows]
    return local == {"127.0.0.1:48343", "127.0.0.1:48344"} and all(len(owner) == 1 and owner <= children for owner in owners) and set.union(*owners) == children


def execute():
    os.umask(0o077)
    os.environ.pop("SSLKEYLOGFILE", None)
    check(sys.argv[1:] == ["--execute-reviewed-gate"] and os.environ.get("MTG_CADDY_SQL_LEASE") == "parent-explicit", "explicit lease invocation")
    check(not PRIVATE.exists() and not RUNTIME.exists() and not EVIDENCE.exists(), "fresh runtime/private/evidence absence")
    check(not (SOURCE / "backend/mtg_lab.db").exists(), "source DB absent")
    PRIVATE.mkdir(mode=0o700)
    EVIDENCE.mkdir(mode=0o700)
    started = time.monotonic()
    signal.signal(signal.SIGTERM, timeout_signal)
    signal.signal(signal.SIGALRM, timeout_signal)
    signal.alarm(800)

    def audit(event, args):
        if event == "sqlite3.connect" and Path(str(args[0])) != RUNTIME / "backend/mtg_lab.db":
            raise RuntimeError("Client SQL path denied")
        if event == "socket.bind" or event == "socket.connect" and args[1] not in {("127.0.0.1", 48343), ("127.0.0.1", 48344)}:
            raise RuntimeError("Client socket denied")
        if event == "socket.getaddrinfo" and args[0] != "127.0.0.1":
            raise RuntimeError("Client DNS denied")
    sys.addaudithook(audit)
    listener_state = subprocess.run(["ss", "-ltnH", "( sport = :48343 or sport = :48344 )"], capture_output=True, check=True).stdout
    check(not listener_state.strip(), "fresh topology ports vacant")
    before_core = {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (SOURCE / "backend").rglob("*") if path.is_file()}

    def openssl(*args, data=None):
        subprocess.run(["openssl", *args], input=data, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=MTG disposable gate CA", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-keyout", str(PRIVATE / "ca-key.pem"), "-out", str(PRIVATE / "ca.pem"))
    openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=wrong.invalid", "-keyout", str(PRIVATE / "site-key.pem"), "-out", str(PRIVATE / "site.csr"))
    (PRIVATE / "leaf.ext").write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n")
    openssl("x509", "-req", "-in", str(PRIVATE / "site.csr"), "-CA", str(PRIVATE / "ca.pem"), "-CAkey", str(PRIVATE / "ca-key.pem"), "-CAcreateserial", "-days", "1", "-extfile", str(PRIVATE / "leaf.ext"), "-out", str(PRIVATE / "site.pem"))
    password = secrets.token_urlsafe(32)
    password_hash = subprocess.run(['/home/nick/.local/share/mtg-deck-testing-lab/runtimes/caddy2117-e8d654-restored-20261021-xq0syqfu/bin/caddy', "hash-password", "--algorithm", "bcrypt", "--bcrypt-cost", "10"], input=password + "\n", text=True, capture_output=True, check=True).stdout.strip()
    authorization = "Basic " + base64.b64encode(("operator:" + password).encode()).decode()
    wrong_authorization = "Basic " + base64.b64encode(("operator:" + secrets.token_urlsafe(32)).encode()).decode()
    config = dict(origin=ORIGIN, backend_port=48344, runtime=str(RUNTIME), python=str(ROOT / "gate-review/backend-python.py"), caddy='/home/nick/.local/share/mtg-deck-testing-lab/runtimes/caddy2117-e8d654-restored-20261021-xq0syqfu/bin/caddy', dist=str(SOURCE / "frontend/dist"), cert=str(PRIVATE / "site.pem"), key=str(PRIVATE / "site-key.pem"), user="operator", password_hash=password_hash)
    (PRIVATE / "operator.json").write_text(json.dumps(config))
    context = ssl.create_default_context(cafile=str(PRIVATE / "ca.pem"))
    check(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED, "client requires CA and hostname verification")

    def connection(ctx=context, name="localhost", direct=False):
        conn = http.client.HTTPConnection("127.0.0.1", 48344, timeout=5) if direct else http.client.HTTPSConnection(name, 48343, context=ctx, timeout=5)
        if not direct:
            # Keep verified SNI/hostname while using exact IPv4 loopback transport.
            conn._create_connection = lambda address, timeout, source_address=None: socket.create_connection(("127.0.0.1", 48343), timeout)
        return conn

    def request(path, method="GET", payload=None, headers=(), auth=authorization, ctx=context, name="localhost", direct=False, incomplete=False):
        conn = connection(ctx, name, direct)
        body = json.dumps(payload).encode() if payload is not None else b""
        started = time.monotonic()
        phase = "prepare_headers"

        def receipt(event, **details):
            # Never use HTTP debuglevel: it prints Authorization and request bodies.
            row = dict(method=method, path=path, direct=direct, incomplete=incomplete,
                       phase=phase, event=event, elapsed=round(time.monotonic() - started, 6))
            row.update(details)
            with (EVIDENCE / "request-phases.jsonl").open("a") as stream:
                stream.write(json.dumps(row, sort_keys=True) + "\n")

        try:
            receipt("enter")
            conn.putrequest(method, path, skip_accept_encoding=True)
            if auth is not None:
                conn.putheader("Authorization", auth)
            if payload is not None or incomplete:
                conn.putheader("Content-Type", "application/json")
                conn.putheader("Content-Length", str(1000000 if incomplete else len(body)))
            for key, value in headers:
                conn.putheader(key, value)
            phase = "send_headers"
            receipt("enter")
            conn.endheaders()
            if body and not incomplete:
                phase = "send_body"
                receipt("enter", body_bytes=len(body))
                conn.send(body)
            phase = "wait_response_headers"
            receipt("enter", sent_body_bytes=len(body) if body and not incomplete else 0)
            response = conn.getresponse()
            response_headers = response.getheaders()
            framing = [(key, value) for key, value in response_headers
                       if key.lower() in {"content-length", "transfer-encoding", "connection", "content-type"}]
            receipt("headers_received", status=response.status, version=response.version,
                    framing_headers=framing, remaining_length=response.length,
                    chunked=response.chunked, will_close=response.will_close)
            phase = "read_response_body"
            receipt("enter")
            response_body = response.read()
            receipt("complete", received_body_bytes=len(response_body))
            return response.status, {key.lower(): value for key, value in response_headers}, response_body
        except BaseException as exc:
            receipt("exception", exception_class=type(exc).__name__)
            raise
        finally:
            conn.close()

    def h2_request(case, path, method="GET", payload=None, headers=(), auth=authorization,
                   name="localhost", cafile=None, tls_error=None):
        # Private stdin/files only; native summaries never contain headers or bodies.
        check(name in {"localhost", "wrong.invalid"} and path.startswith("/")
              and not any(character in path for character in "\r\n"), "H2 fixed local URL boundary")
        directory = PRIVATE / ("h2-" + secrets.token_hex(8))
        directory.mkdir(mode=0o700)
        response_path, headers_path = directory / "response", directory / "headers"
        command = ["/usr/bin/curl", "--disable", "--config", "-", "--silent", "--show-error",
                   "--http2", "--proto", "=https", "--proxy", "", "--noproxy", "*",
                   "--resolve", name + ":48343:127.0.0.1", "--cacert", str(cafile or PRIVATE / "ca.pem"),
                   "--connect-timeout", "5", "--max-time", "5", "--max-redirs", "0",
                   "--request", method, "--output", str(response_path), "--dump-header", str(headers_path),
                   "--write-out", "%{http_version}\t%{response_code}\t%{remote_ip}\t%{remote_port}\t%{ssl_verify_result}\n",
                   "https://" + name + ":48343" + path]
        entries = list(headers)
        if auth is not None:
            entries.append(("Authorization", auth))
        if payload is not None:
            (directory / "request").write_bytes(json.dumps(payload).encode())
            entries.append(("Content-Type", "application/json"))
            command += ["--data-binary", "@" + str(directory / "request")]
        configuration = []
        for key, value in entries:
            check(not any(character in key + value for character in "\r\n"), "H2 private header input boundary")
            operand = (key + ": " + value).replace("\\", "\\\\").replace('"', '\\"')
            configuration.append('header = "' + operand + '"')
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(PRIVATE), "LANG": "C.UTF-8"}
        process = None
        began = time.monotonic()
        try:
            process = subprocess.Popen(command, env=environment, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            capture(process.pid)
            try:
                stdout, stderr = process.communicate(input=("\n".join(configuration) + "\n").encode(), timeout=7)
            except subprocess.TimeoutExpired:
                signal_owned(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    signal_owned(process.pid, signal.SIGKILL)
                    process.communicate(timeout=2)
                raise AssertionError("H2 bounded native client timeout")
            fields = stdout.decode("ascii").strip("\n").split("\t")
            check(len(fields) == 5, "H2 sanitized native summary shape")
            version, status, remote_ip, remote_port, verified = fields
            status, verified = int(status), int(verified)
            row = dict(case=case, method=method, route=path, native_exit=process.returncode, http_version=version, status=status,
                       loopback=remote_ip == "127.0.0.1", remote_port=remote_port,
                       ssl_verify_result=verified, elapsed=round(time.monotonic() - began, 6))
            with (EVIDENCE / "h2-native.jsonl").open("a") as stream:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
            if tls_error is not None:
                diagnostic = stderr.lower()
                if tls_error == "unknown_ca":
                    typed_failure = b"unable to get local issuer certificate" in diagnostic or b"self-signed certificate in certificate chain" in diagnostic
                else:
                    typed_failure = b"no alternative certificate subject name matches" in diagnostic
                check(process.returncode == 60 and status == 0 and version == "0"
                      and verified != 0 and typed_failure, case)
                return None
            check(process.returncode == 0 and version == "2" and verified == 0
                  and remote_ip == "127.0.0.1" and remote_port == "48343",
                  "H2 native CA hostname ALPN/version2 exact loopback no fallback")
            body = response_path.read_bytes()
            response_headers = {}
            for line in headers_path.read_bytes().splitlines():
                if b":" in line:
                    key, value = line.split(b":", 1)
                    response_headers[key.decode("ascii").lower()] = value.decode("latin-1").strip()
            return status, response_headers, body
        finally:
            # A client that survived bounded termination is a closure failure, not cleanup success.
            if process is None or process.poll() is not None:
                for operand in directory.iterdir():
                    operand.unlink()
                directory.rmdir()

    def h2_initial_cases():
        check(hashlib.sha256(Path("/usr/bin/curl").read_bytes()).hexdigest()
              == "1ccbd3dae948374ba8eef1ebda26c64b783ede50b463196e53666e0880bdac60",
              "H2 native curl exact reviewed binary")
        native = subprocess.run(["/usr/bin/curl", "--disable", "--version"],
                                env={"PATH": "/usr/bin:/bin", "HOME": str(PRIVATE), "LANG": "C.UTF-8"},
                                capture_output=True, timeout=5)
        feature_lines = [line.split() for line in native.stdout.splitlines() if line.startswith(b"Features:")]
        check(native.returncode == 0 and len(feature_lines) == 1 and b"HTTP2" in feature_lines[0],
              "H2 native curl installed HTTP2 capability")
        check(h2_request("H2 verified native transport positive", "/api/cards")[0] == 200,
              "H2 genuine verified native transport before TLS negatives")
        openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-subj", "/CN=MTG unrelated disposable H2 CA", "-addext", "basicConstraints=critical,CA:TRUE",
                "-keyout", str(PRIVATE / "h2-unrelated-ca-key.pem"), "-out", str(PRIVATE / "h2-unrelated-ca.pem"))
        h2_request("H2 TLS unknownCA typed rejection", "/", auth=None,
                   cafile=PRIVATE / "h2-unrelated-ca.pem", tls_error="unknown_ca")
        h2_request("H2 TLS wronghostname typed rejection", "/", auth=None,
                   name="wrong.invalid", tls_error="hostname")
        for path in routes:
            for label, auth in [("missing", None), ("wrong", wrong_authorization), ("malformed", "Basic invalid")]:
                before = len(public_ledger())
                status, _, _ = h2_request("H2 auth " + label + " route401 " + path, path,
                                          method="POST" if path.endswith("/start") else "GET",
                                          payload={} if path.endswith("/start") else None, auth=auth)
                check(status == 401 and len(public_ledger()) == before, "H2 auth route401 before backend")
        for path in ["/", "/route/refresh", "/apiish/cards"]:
            check(h2_request("H2 SPA byte identity", path)[2] == html, "H2 authenticated built SPA bytes")
        for asset in assets:
            check(h2_request("H2 asset byte identity", asset.decode())[2]
                  == (SOURCE / "frontend/dist" / asset.decode().lstrip("/")).read_bytes(), "H2 authenticated built asset bytes")
        check(h2_request("H2 bare API boundary", "/api")[0] == 404, "H2 bare API not SPA")
        check(h2_request("H2 API prefix routing", "/api/cards")[0] == 200, "H2 actual authenticated API prefix")
        check(h2_request("H2 media byte identity", "/card-images/generic-token-creature.svg")[2]
              == (RUNTIME / "backend/card_data/image_cache/generic-token-creature.svg").read_bytes(), "H2 real unchanged backend media bytes")
        for origin, expected in [(ORIGIN, 200), ("https://evil.example", 400), ("null", 400)]:
            category = "trusted" if origin == ORIGIN else "null" if origin == "null" else "denied"
            status, response_headers, _ = h2_request("H2 CORS " + category + " preflight", "/api/matches/start", "OPTIONS",
                                                     headers=[("Origin", origin), ("Access-Control-Request-Method", "POST"),
                                                              ("Access-Control-Request-Headers", "content-type,idempotency-key,x-match-revision")])
            check(status == expected and (response_headers.get("access-control-allow-origin") == ORIGIN
                  if expected == 200 else "access-control-allow-origin" not in response_headers), "H2 allowed denied null CORS preflight")
            if expected == 200:
                check(response_headers.get("access-control-allow-credentials") == "true"
                      and all(name in response_headers.get("access-control-allow-headers", "").lower()
                              for name in ["content-type", "idempotency-key", "x-match-revision"]), "H2 required authenticated preflight headers")
        for origin_headers in [[("Origin", ORIGIN)], []]:
            headers = origin_headers + [(key, value) for key, value in mutation_headers if key != "Origin"]
            category = "trusted" if origin_headers else "native"
            status, response_headers, body = h2_request("H2 " + category + " duplicate action", f"/api/matches/{mid}/action",
                                                       "POST", action, headers)
            check(status == 200 and json.loads(body) == saved, "H2 trusted native actual duplicate receipt")
            check(response_headers.get("access-control-allow-origin") == ORIGIN if origin_headers
                  else "access-control-allow-origin" not in response_headers, "H2 exact dynamic Origin compatibility")
        rejected_before = len([row for row in public_ledger() if row.get("event") == "atomic_rejection"])
        for origin in ["https://evil.example", "null"]:
            category = "null" if origin == "null" else "hostile"
            status, _, body = h2_request("H2 " + category + " mutation", "/api/cards/sync", "POST", {}, [("Origin", origin)])
            check(status == 403 and json.loads(body)["detail"]["code"] == "untrusted_browser_origin", "H2 hostile null mutation403")
        rejected_after = wait_atomic_rejections(rejected_before + 2)[rejected_before:]
        check(len(rejected_after) == 2 and all(row["status"] == [403] and not any(row["observations"].values())
              and row["complete_root_controller_sql_equal"] for row in rejected_after), "H2 two additional atomic root controller SQL rejections")

    def h2_restart_cases():
        status, _, body = h2_request("H2 restart saved match", f"/api/matches/{mid}")
        check(status == 200 and json.loads(body) == saved, "H2 actual persisted match recovered after restart")
        status, _, body = h2_request("H2 restart duplicate action receipt", f"/api/matches/{mid}/action", "POST", action, mutation_headers)
        check(status == 200 and json.loads(body) == saved, "H2 idempotency receipt recovered after restart")
        check(h2_request("H2 restart media", "/card-images/generic-token-creature.svg")[2]
              == (RUNTIME / "backend/card_data/image_cache/generic-token-creature.svg").read_bytes(), "H2 media byte identity after restart")


    def start():
        env = {"PATH": "/usr/bin:/bin", "HOME": str(PRIVATE), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "MTG_OPERATOR_CONFIG": str(PRIVATE / "operator.json")}
        supervisor = subprocess.Popen([str(PYTHON), str(SOURCE / "ops/caddy/run.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        SUPERVISORS.append(supervisor)
        capture(supervisor.pid)
        deadline = time.monotonic() + 120
        ready = False
        while time.monotonic() < deadline and supervisor.poll() is None:
            capture_children(supervisor)
            try:
                ready = request("/api/cards")[0] == 200
                if ready:
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.2)
        check(ready, "real authenticated API readiness")
        child_path = Path(f"/proc/{supervisor.pid}/task/{supervisor.pid}/children")
        children = {int(value) for value in child_path.read_text().split()}
        for pid in children:
            capture(pid)
        check(len(children) == 2, "supervisor owns exactly two children")
        listening = subprocess.run(["ss", "-ltnpH", "( sport = :48343 or sport = :48344 )"], capture_output=True, check=True).stdout.decode()
        (EVIDENCE / ("listeners-" + str(len(SUPERVISORS)) + ".txt")).write_text(listening)
        check(valid_listeners(listening, children), "both LOCAL listener columns exact loopback ports and ownedPIDs")
        return supervisor

    def stop(supervisor):
        if supervisor.poll() is None:
            signal_owned(supervisor.pid, signal.SIGTERM)
        out, err = supervisor.communicate(timeout=70)
        # Launcher output contains fixed messages only, never child output.
        (EVIDENCE / ("supervisor-" + str(supervisor.pid) + ".log")).write_bytes(out + err)
        check(supervisor.returncode == 0, "supervisor graceful exit0")
        rows = public_ledger()
        closures = [row for row in rows if row.get("event") == "closure"]
        check(bool(closures) and closures[-1]["phase"] == "lifespan_after_original_shutdown" and closures[-1]["original_shutdown_succeeded"] and closures[-1]["engines_disposed"] >= 1 and not any(closures[-1]["checkedout"]) and closures[-1]["jobs"] == 0 and not closures[-1]["unexpected_native_denials"] and not closures[-1]["native_database_fds"], "real lifespan shutdown/engine/job/native DBFD closure")
        live = [row for row in rows if row.get("event") == "production_owner_live"]
        production = [row for row in rows if row.get("event") == "production_first_shutdown"]
        pairs = {(row["backend_pid"], row["epoch"]) for row in live}
        check(len(live) == len(production) == len(pairs) == len(SUPERVISORS)
              and {(row.get("backend_pid"), row.get("epoch")) for row in production} == pairs
              and len({row["backend_pid"] for row in live}) == len(SUPERVISORS)
              and all(row["backend_pid"] in PIDS and row["verified"] is True
                      and row["before_observer_cleanup"]
                      and row["status"] == "verified_before_observer_assist" for row in production),
              "production-first native disposal owner FD registry closure per backend PID epoch before observer assist")
        check(all(not Path(f"/proc/{pid}/task").exists() for pid in PIDS), "native all owned process threads gone after stop")
        check(not subprocess.run(["ss", "-ltnH", "( sport = :48343 or sport = :48344 )"], capture_output=True, check=True).stdout.strip(), "listener closure")

    supervisor = start()
    try:
        request("/", auth=None, ctx=ssl.create_default_context())
    except ssl.SSLCertVerificationError:
        check(True, "unknown CA rejected")
    else:
        check(False, "unknown CA rejected")
    # Correct SNI selects the real certificate; expected hostname is independently wrong.
    for expected_name, label in [("localhost", "valid"), ("wrong.invalid", "wrong")]:
        probe = subprocess.run(["openssl", "s_client", "-connect", "127.0.0.1:48343", "-servername", "localhost", "-verifyCAfile", str(PRIVATE / "ca.pem"), "-verify_hostname", expected_name, "-verify_return_error", "-brief"], input=b"GET / HTTP/1.1\r\nHost: localhost:48343\r\nConnection: close\r\n\r\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        (EVIDENCE / ("hostname-native-" + label + ".stdout")).write_text("Native HTTP stdout omitted; no headers or body archived.\n")
        (EVIDENCE / ("hostname-native-" + label + ".stderr")).write_text(json.dumps(dict(native_exit=probe.returncode, verification_ok=b"Verification: OK" in probe.stderr, hostname_mismatch62=b"verify error:num=62:hostname mismatch" in probe.stderr), sort_keys=True) + "\n")
        (EVIDENCE / ("hostname-native-" + label + ".exit")).write_text(str(probe.returncode) + "\n")
        if label == "valid":
            check(probe.returncode == 0 and b"Verification: OK" in probe.stderr, "native trustedCA/correctSNI/correcthostname positive")
        else:
            check(probe.returncode != 0 and b"verify error:num=62:hostname mismatch" in probe.stderr, "native specific hostname mismatch62 rejected with correctSNI")
    html = (SOURCE / "frontend/dist/index.html").read_bytes()
    assets = re.findall(rb'(?:src|href)="(/assets/[^\"]+)"', html)
    check(bool(assets), "actual built assets discovered")
    routes = ["/", "/route/refresh", "/api", "/api/cards", "/api/matches/start", "/card-images/generic-token-creature.svg", "/apiish/cards", *[asset.decode() for asset in assets]]
    for path in routes:
        for auth in (None, wrong_authorization, "Basic invalid"):
            before = len(public_ledger())
            status, _, _ = request(path, method="POST" if path.endswith("/start") else "GET", payload={} if path.endswith("/start") else None, auth=auth)
            check(status == 401 and len(public_ledger()) == before, "unauth/wrong/malformed route401 before backend")
    for path in ["/", "/route/refresh", "/apiish/cards"]:
        check(request(path)[2] == html, "authenticated real built SPA bytes")
    for asset in assets:
        check(request(asset.decode())[2] == (SOURCE / "frontend/dist" / asset.decode().lstrip("/")).read_bytes(), "authenticated real built asset bytes")
    check(request("/api")[0] == 404, "bare API not SPA")
    check(request("/card-images/generic-token-creature.svg")[2] == (RUNTIME / "backend/card_data/image_cache/generic-token-creature.svg").read_bytes(), "real unchanged backend media bytes")
    check(request("/matches", direct=True, auth=None)[0] == 200, "native loopback noOrigin compatibility not authentication")

    deck = [{"quantity": 60, "card_name": "Island"}]
    payload = dict(deck_a=deck, deck_b=deck, controller_a="human", controller_b="human", mode="human_vs_human", seed=8128)
    check(request("/api/simulate/batch/preflight", "POST", dict(deck_a=deck, deck_b=deck), headers=[("Origin", ORIGIN)])[0] == 200, "trusted real preflight")
    for origin, expected in [(ORIGIN, 200), ("https://evil.example", 400), ("null", 400)]:
        status, headers, _ = request("/api/matches/start", "OPTIONS", headers=[("Origin", origin), ("Access-Control-Request-Method", "POST"), ("Access-Control-Request-Headers", "content-type,idempotency-key,x-match-revision")])
        check(status == expected and (headers.get("access-control-allow-origin") == ORIGIN if expected == 200 else "access-control-allow-origin" not in headers), "real allowed/denied/null CORS preflight")
        if expected == 200:
            check(headers.get("access-control-allow-credentials") == "true" and all(name in headers.get("access-control-allow-headers", "").lower() for name in ["content-type", "idempotency-key", "x-match-revision"]), "required authenticated preflight headers")
    match = None
    for origin_headers in [[("Origin", ORIGIN)], []]:
        status, headers, body = request("/api/matches/start", "POST", payload, headers=origin_headers + [("Idempotency-Key", secrets.token_hex(16))])
        check(status == 200, "trusted/native actual supported start")
        check(headers.get("access-control-allow-origin") == ORIGIN if origin_headers else "access-control-allow-origin" not in headers, "exact dynamic Origin CORS on actual start")
        match = json.loads(body)
    mid = match["id"]
    move = None
    actor = None
    for player in [match["active_player"], 3 - match["active_player"]]:
        status, _, body = request(f"/api/matches/{mid}/legal-moves?player_id={player}")
        check(status == 200, "actual legal-move query")
        available = json.loads(body)
        move = next((candidate for candidate in available["moves"] if candidate.get("type") == "keep_hand"), None)
        if move:
            actor = player
            break
    check(move is not None, "supported legal keep discovered not forced")
    action = dict(player_id=actor, action=move)
    mutation_headers = [("Origin", ORIGIN), ("Idempotency-Key", secrets.token_hex(16)), ("X-Match-Revision", str(match["revision"]))]
    status, _, body = request(f"/api/matches/{mid}/action", "POST", action, mutation_headers)
    check(status == 200, "trusted real revision/idempotency action")
    saved = json.loads(body)
    check(request(f"/api/matches/{mid}/action", "POST", action, mutation_headers)[0] == 200, "real duplicate receipt accepted")
    targets = ["/api/matches/start", f"/api/matches/{mid}/action", "/api/cards/sync", "/api/cards/sync-bulk", "/api/simulate/batch/preflight"]
    variants = [[("Origin", "https://evil.example")], [("Origin", "null")], [("Origin", "")], [("Origin", ORIGIN), ("Origin", ORIGIN)], [("Origin", ORIGIN), ("Origin", "https://evil.example")]]
    for target in targets:
        for origins in variants:
            status, _, body = request(target, "POST", {}, origins)
            check(status == 403 and json.loads(body)["detail"]["code"] == "untrusted_browser_origin", "real malicious mutation403")
    status, _, _ = request("/api/cards/sync", "POST", headers=[("Origin", "https://evil.example")], incomplete=True)
    check(status == 403, "incomplete malicious body rejected without sending body")
    rejected = wait_atomic_rejections(26)
    check(len(rejected) == 26 and all(row["status"] == [403] and not any(row["observations"].values()) and row["complete_root_controller_sql_equal"] for row in rejected), "all26 complete root/controller/SQL atomic body/dependency guards")
    check(any(row.get("media_prefix_preserved") for row in public_ledger()), "upstream media prefix observed unchanged")
    second = subprocess.run([str(PYTHON), str(SOURCE / "ops/caddy/run.py")], env={"PATH": "/usr/bin:/bin", "MTG_OPERATOR_CONFIG": str(PRIVATE / "operator.json"), "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    check(second.returncode == 1 and supervisor.poll() is None, "concurrent launch blocked without disturbing owned server")
    h2_initial_cases()
    stop(supervisor)
    supervisor = start()
    status, _, body = request(f"/api/matches/{mid}")
    check(status == 200 and json.loads(body) == saved, "actual persisted match recovered after restart")
    check(request(f"/api/matches/{mid}/action", "POST", action, mutation_headers)[0] == 200, "idempotency receipt recovered after restart")
    check(request("/card-images/generic-token-creature.svg")[0] == 200, "media recovered after restart")
    h2_restart_cases()
    stop(supervisor)
    check(all(not Path(f"/proc/{pid}").exists() for pid in PIDS), "all actual owned PIDs absent")
    closed_files = []
    for path in sorted((RUNTIME / "backend").glob("mtg_lab.db*")):
        result = subprocess.run(["fuser", str(path)], capture_output=True)
        closed_files.append({"path": str(path.relative_to(ROOT)), "exit": result.returncode, "empty": not result.stdout.strip() and not result.stderr.strip()})
        check(result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip(), "closed DB/sidecar native fuser empty")
    (EVIDENCE / "native-closure.json").write_text(json.dumps(dict(identities=IDENTITIES, signals=SIGNALS, files=closed_files), indent=2))
    with closing(sqlite3.connect(str(RUNTIME / "backend/mtg_lab.db"))) as database:
        check(database.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "closed local DB integrity")
    check(before_core == {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (SOURCE / "backend").rglob("*") if path.is_file()}, "immutable backend source after equality")
    check(time.monotonic() - started < 900, "serial gate under900")


if __name__ == "__main__":
    if sys.argv[1:] != ["--execute-reviewed-gate"] or os.environ.get("MTG_CADDY_SQL_LEASE") != "parent-explicit":
        print("Not executed: explicit reviewed SQL lease required.")
        sys.exit(2)
    status = 1
    failure = None
    try:
        execute()
        status = 0
    except Exception as exc:
        failure = type(exc).__name__
    finally:
        signal.alarm(0)
        for supervisor in SUPERVISORS:
            capture_children(supervisor)
            if supervisor.poll() is None:
                signal_owned(supervisor.pid, signal.SIGTERM)
                try:
                    supervisor.communicate(timeout=70)
                except subprocess.TimeoutExpired:
                    # Kill only captured owned process groups; failed output/data stays local.
                    for pid in PIDS:
                        signal_owned(pid, signal.SIGKILL)
                    try:
                        supervisor.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        CLOSURE_ISSUES.append("supervisor_unclosed_after_bounded_cleanup")
        pid_closed = all(not Path(f"/proc/{pid}").exists() for pid in PIDS)
        if not pid_closed or CLOSURE_ISSUES:
            status = 1
        if EVIDENCE.exists():
            (EVIDENCE / "terminal.json").write_text(json.dumps(dict(exit=status, failure_type=failure, checks=RESULTS, identities=IDENTITIES, signals=SIGNALS, closure_issues=CLOSURE_ISSUES, pid_closure=pid_closed), indent=2))
        print("Gate terminal exit=" + str(status) + "; review sanitized terminal and closure ledgers.")
    sys.exit(status)
