# Private HTTPS Operator Packaging

Status: static configuration qualification only. Actual trusted-CA HTTPS,
authenticated API/media, rejection atomicity and restart recovery must pass an
explicitly leased isolated runtime gate before deployment. Old R9 browser runs
do not qualify this packaging or the fresh frontend. No live activation occurs
by adding these files.

## Files and boundaries

- `Caddyfile`: manual-certificate HTTPS, IPv4 loopback only, native BasicAuth
  before every route, `/api/*` strips `/api`, `/card-images/*` stays unchanged,
  bare `/api` is 404, built static files with SPA fallback. Authorization is
  removed upstream; Origin and API idempotency/revision headers are preserved.
- `run.py`: `settings` validates private operator material and pinned binary;
  `prepare` locks and pins a local writable backend copy; `environment` gives
  credentials only to Caddy; `main` validates and supervises two owned children.
  Backend is `uvicorn main:app --host 127.0.0.1 --workers 1`, no forwarded-header
  trust or access log. No application dependencies or source functions change.
- `verify-config.py`: native adaptation/provisioning and rejected-config checks
  with disposable material. It starts no HTTP server, SQL or TLS client.

Admin endpoint, config persistence, automatic HTTPS and global trust installation
are off. TLS is mandatory, not an HTTP redirect. HTTP/1.1 and HTTP/2 only. Runtime
and access logs are suppressed; failures deliberately contain no config values.
This sacrifices detailed diagnostics to avoid accidentally retaining credentials.
Do not enable tracing, dump subprocess environments or archive operator material.

## Local binary provenance (Linux amd64 only)

Pinned official release: https://github.com/caddyserver/caddy/releases/tag/v2.11.7

- `caddy_2.11.7_linux_amd64.tar.gz` SHA256:
  `727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b`
- Extracted `caddy` SHA256 (enforced by launcher):
  `678ade3bfc088749c81a681adc603333ee0bb023b6a6cfe3c0f58bef8ff854e9`
- Verification tool: official Sigstore cosign v3.1.3 `cosign-linux-amd64`, SHA256
  `4629c757b7618056f8ddd7e2625ae9fdd94c0372a65049520bc7d9df9efc7f71`.
  Bootstrap trust is official HTTPS release/API digest, not an independently
  installed verifier or a claim that cosign was independently code audited.

Download into a private local tools directory, not `/usr/bin`. Fetch the tar,
companion `.sig` and `.pem` from that exact official release. Verify the pinned
SHA256 before extraction and verify the signature before executing Caddy:

```sh
./cosign-linux-amd64 verify-blob \
  --certificate caddy_2.11.7_linux_amd64.pem \
  --signature caddy_2.11.7_linux_amd64.tar.gz.sig \
  --certificate-identity 'https://github.com/caddyserver/caddy/.github/workflows/release.yml@refs/tags/v2.11.7' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  caddy_2.11.7_linux_amd64.tar.gz
```

Failure blocks use: do not bypass log/expiry/issuer/identity checks. The current
verification returned `Verified OK`; flags are deprecated in cosign 3 but still
verify signatures and transparency log. Preserve public provenance separately
from private TLS/auth material. No global installation is necessary.

## Operator configuration and launch

Use an immutable qualified source tree and a built `frontend/dist`. Build using
the retained fresh-install-qualified local dependencies; this later build is
not another clean-install claim. Leave `VITE_API_BASE_URL` unset so existing
frontend routing uses `/api` and unchanged `/card-images`.

Create a private local directory outside source/dist, mode 0700, and an operator
JSON file mode 0600 owned by the invoking user. Exact keys:

```json
{
  "origin": "https://localhost:18443",
  "backend_port": 18444,
  "runtime": "/absolute/private/local/runtime",
  "python": "/absolute/qualified/venv/bin/python",
  "caddy": "/absolute/private/tools/caddy",
  "dist": "/absolute/immutable/source/frontend/dist",
  "cert": "/absolute/private/material/site-chain.pem",
  "key": "/absolute/private/material/site-key.pem",
  "user": "operator",
  "password_hash": "REPLACE_PRIVATELY_WITH_NATIVE_BCRYPT_HASH"
}
```

This is a schema example, not valid credentials or tested TLS material. Origin
must be one canonical explicit HTTPS hostname and unprivileged port; backend
port must differ. Paths cannot contain whitespace/Caddy control syntax. Both
listeners remain 127.0.0.1 regardless of hostname. Runtime cannot be NFS or source,
and must be private. Existing runtime source pins must match; upgrades require
a separately prepared runtime and verified migration/restore, not copying over
old code or deleting data. Private config/key files cannot lie inside served dist.

Runtime reuse fails closed if any copied immutable file (including non-Python
fixtures) changes, disappears or becomes a symlink, or an unexpected immutable
file appears. The receipt, lock and backend directory also reject symlinks;
regular files reject hardlinks. Only the named SQLite DB/WAL/SHM/journal and
`card_data/image_cache`, `diagnostics`, `training_runs` outputs are mutable;
their entire trees still reject symlinks and nonregular entries. Updating copied
`ai/data/log_priors.json` deliberately blocks reuse pending reviewed migration.
The source, runtime parent, credentials and interpreter remain trusted same-user
local resources. These prechecks are not a race-proof sandbox against a hostile
same-user process changing files after validation; no broader local/LAN claim.

Create a bcrypt hash with native `caddy hash-password --algorithm bcrypt` using
its hidden interactive stdin, never `--plaintext`, command arguments, shell
history, logs or archived output. Enter the resulting hash directly into the
private file. Only Caddy receives it. The password itself is not stored by this
launcher. Use strong unique credentials. Supply a certificate chain with SAN
matching the exact chosen hostname and its private key (mode 0600). Client trust
is explicit; neither this launcher nor Caddy installs a root globally.

```sh
MTG_OPERATOR_CONFIG=/absolute/private/operator.json python3 ops/caddy/run.py --check
MTG_OPERATOR_CONFIG=/absolute/private/operator.json python3 ops/caddy/run.py
```

`--check` provisions configuration without listeners or SQL. Start only after
the reviewed gate receives its execution lease. Normal start prints a supervisor
receipt, NOT a health/readiness certificate. Runtime code, DB, media and Caddy
storage live outside immutable source; only one supervisor holds its file lock.
Processes are foreground, not installed as services. Startup briefly permits
authenticated 502 until backend readiness; readiness must be observed by client.

## Stop and recovery

Send Ctrl-C/SIGTERM to the foreground supervisor. It signals only child process
groups it created, waits for each, and releases the runtime lock. After 30 seconds
a stuck child is killed, exit is nonzero, and recovery inspection is required;
this is not a graceful SQL closure claim. Never kill unrelated workers/PIDs.
Confirm both listener ports/PIDs are gone and runtime DB `fuser` is empty before
backup/restore or a new exclusive SQL gate. Restart the same immutable source and
private config to reuse DB/media and restore saved application records through
existing startup code. No stale PID-file kill or automatic database replacement.

Use existing `backend/scripts/verify_storage_restore.py` for closed/consistent
backup and local restore verification; do not replace a live DB. Preserve source,
uncommitted changes and closed user data explicitly. Archive only verified closed
data/evidence to mounted NFS, excluding all credentials, keys, operator JSON,
Caddy storage and process environments. Never run SQLite directly on NFS.

## Exposure limits and pending runtime gate

HTTP/1 early rejection requires `servers { enable_full_duplex }`. The default
Go HTTP server consumes unread request body before publishing a response; an
authenticated hostile Origin with an incomplete upload can therefore reach the
backend's atomic 403 guard while the client waits for response headers. This
flag permits concurrent request reads and response writes, without changing
authentication ordering, trusted Origins, body validation or backend handlers.
The pinned Caddy 2.11.7 binary reports Go 1.26.8 (feature requires Go 1.21+);
native adaptation must contain `enable_full_duplex: true`.

Caddy marks this option experimental. Older HTTP/1 clients may deadlock and
require explicit compatibility qualification; HTTP/2 already permits concurrent
reads/writes. This is not blanket client or exposure support. The actual
incomplete-upload early-403 client gate remains required and is pending with
this delta; no timeout extension, upload completion or rejection bypass.
https://caddyserver.com/docs/caddyfile/options#enable-full-duplex
https://github.com/caddyserver/caddy/blob/v2.11.7/modules/caddyhttp/server.go
https://github.com/golang/go/blob/go1.26.8/src/net/http/responsecontroller.go

No LAN/public binding is implemented. User-selected hostname, user-approved
certificate trust, firewall and authenticated TLS exposure require future explicit
configuration and qualification; do not replace loopback with blanket LAN binds.
The backend is intentionally unauthenticated on loopback. Native requests without
Origin are compatible, NOT authenticated. Local processes remain trusted. This
single-user/one-worker service shares game/job state; BasicAuth is not per-user
authorization, isolation, quotas or a public-service security certificate.

Queued gate: fresh local runtime, ephemeral private CA/leaf SAN and credentials;
real trusted-CA client (no `-k`/ignore-cert), real built HTML/assets, native 401 for
missing/wrong credentials, authenticated API and unchanged media, supported start
and legal action/recovery, trusted/denied CORS headers, malicious mutation 403
with complete controller/root/SQL equality before body/dependencies, rejected
direct exposure, restart recovery and complete child/socket/DB closure. Secret
material stays local/private and is destroyed only after closure; evidence is
sanitized assertions/statuses, not headers or key/auth dumps. This gate is pending.

Authoritative references:
https://caddyserver.com/docs/signature-verification
https://caddyserver.com/docs/caddyfile/directives/basic_auth
https://caddyserver.com/docs/caddyfile/directives/handle_path
https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
https://caddyserver.com/docs/caddyfile/options
https://caddyserver.com/docs/command-line
