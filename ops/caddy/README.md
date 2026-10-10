# Private HTTPS Operator Packaging

Historical status: the `0e57baf` native loopback runtime with the former official
binary passed trusted-CA HTTPS, authenticated API/media, rejection atomicity and
restart recovery. That acceptance does not transfer to the custom binary below. See
`../../docs/testing/caddy-operator-current-acceptance.md` for exact evidence and
scope. Final combined-source/browser and user-selected LAN topology still need
qualification before deployment, including native runtime integration of this
custom build. No live activation occurs by adding these files.

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

Pinned **custom source build**, not an official signed Caddy distribution:

- Caddy `v2.11.7`, tag commit `72dd0fb067f6d7826c7f79907670ba4a713bfe37`;
  authenticated module sum `h1:yj0Y4fYZGPkSvibBJ1sTWE33xC0fxztVyXEW5iIdUT4=`.
- Official Go `1.26.9` SDK, `go1.26.9.linux-amd64.tar.gz`, 66,935,201 bytes;
  SHA256 `42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d`.
  Exact download: https://go.dev/dl/go1.26.9.linux-amd64.tar.gz
  Metadata: https://go.dev/dl/?mode=json&include=all
- `golang.org/x/net v0.60.0`, tag commit
  `18ece0ce30bc35fa81fe72028bf309bb3ff3f4a5`;
  authenticated module sum `h1:79p50tfZlm0J9YfoDsSi639qSXNGVwEzOPLCxM2FsYU=`.
- Actual static stripped Linux-amd64 binary, 51,974,306 bytes; SHA256 enforced
  by the unchanged launcher checksum check:
  `e8d6545c8485f7bd723fc3a6a2fb5662e89a235ae0d32ccde3f43d81577b0db0`.

The previous official binary hash
`678ade3bfc088749c81a681adc603333ee0bb023b6a6cfe3c0f58bef8ff854e9`
is historical and is no longer accepted by this pin. Its release signatures,
certificates, transparency proofs and earlier runtime acceptance **do not cover
this custom executable**. A `v2.11.7` CLI version string is not official-binary
authentication. Verify the exact candidate hash before executing it; keep it in
an owned local tools directory, not `/usr/bin`. This documentation does not
install, deploy, change global trust or qualify a live proxy.

### Reproduce the verified source build

Use the completed public build packet at:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/caddy2117-security-build-20261010-bwDTVP/`.
Its `caddy2117-go1269-xnet060-build-only.tar.gz` SHA256 is
`f57a91816b4aee1217128eeca9e97d6a934782eb7061d47f9e2581f7ef80e201`.
Read `BUILD_RECIPE.md` and `REPORT.md`; verify `OUTER_SHA256SUMS` and the
`PAYLOAD_SHA256SUMS` identities **inside the tar**, not nonexistent expanded NFS
paths. Extract only into fresh owned local source/cache directories. The packet
retains the exact SDK archive, public module zip/mod/info and signed sumdb cache,
unchanged official wrapper main, exact wrapper module files, graphs and build log.

Follow that existing recipe, not a new installer: verify SDK size/hash before
execution; authenticate Caddy source through public `proxy.golang.org` and
`sum.golang.org`; copy only unchanged `cmd/caddy/main.go` into the release-style
module named `caddy`, requiring `v2.11.7`. Baseline/postfix selected graphs have
597 identities and must differ **only** by x/net `v0.59.0` to `v0.60.0`, without
added/removed modules or replacements. Preserve the exact final wrapper files:
`go.mod` SHA256 `d173eceee6ce678584bf2f5d2e219aade323ccfb93e578c0b48bc83295e8a59a`,
`go.sum` SHA256 `6af3a164233778b8a67386362356bfb312d26888ccee645b7180f07fc27e8574`.
No Caddy source or other selected dependency version is changed.

Use clean `env -i` with owned HOME/GOPATH/GOMODCACHE/GOCACHE/TMPDIR/GOTMPDIR,
explicit verified Go1.26.9 GOROOT/PATH, `GOENV=off`, `GOWORK=off`,
`GOTOOLCHAIN=local`, `GOTELEMETRY=off`, `GOVCS=*:off`, canonical public proxy and
sumdb with no private/direct fallback. After native `go mod verify` and exact
graph comparison, build offline (`GOPROXY=off`) with `CGO_ENABLED=0`,
`GOOS=linux`, `GOARCH=amd64`, `GOMAXPROCS=2`:

```sh
go build -p 2 -trimpath -mod=readonly -tags nobadger,nomysql,nopgx \
  -ldflags '-s -w' -o OWN/output/caddy-security-candidate .
```

Inspect actual `go version -m` for Go1.26.9/Caddy2.11.7/x/net0.60.0 and all
147 embedded dependencies against the frozen graph/go.sum. Reject unexpected
churn or output hash mismatch; never refresh the launcher pin to unknown bytes.
Native operator runtime remains a separately leased Main-owned gate.

Primary constraints and authentication:
https://github.com/caddyserver/caddy/blob/v2.11.7/.goreleaser.yml
https://github.com/caddyserver/caddy/blob/v2.11.7/go.mod
https://proxy.golang.org/golang.org/x/net/@v/v0.60.0.mod
https://go.dev/ref/mod#authenticating
https://go.dev/doc/devel/release#go1.26.9

Go alone does not patch Caddy's selected x/net HTTP/2 implementation; both pins
are required. The public report records primary advisory matches and reachability
limits, including the retained OpenPGP advisory whose affected packages are absent
from this build. Integrity checks and absent indexed advisory matches are not
proof of complete security, runtime behavior, exposure or deployability.

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

## Exposure Limits And Runtime Qualification

HTTP/1 early rejection requires `servers { enable_full_duplex }`. The default
Go HTTP server consumes unread request body before publishing a response; an
authenticated hostile Origin with an incomplete upload can therefore reach the
backend's atomic 403 guard while the client waits for response headers. This
flag permits concurrent request reads and response writes, without changing
authentication ordering, trusted Origins, body validation or backend handlers.
The custom Caddy 2.11.7 binary reports Go 1.26.9 (feature requires Go 1.21+);
native adaptation must contain `enable_full_duplex: true`.

Caddy marks this option experimental. Older HTTP/1 clients may deadlock and
require explicit compatibility qualification; HTTP/2 already permits concurrent
reads/writes. This is not blanket client or exposure support. The historical native
incomplete-upload early-403 gate with the former official binary passed without a
timeout extension, upload completion or rejection bypass. A later exact
`eb8d8805` combined-source invocation qualifies the custom binary with all 547
observed H1/strict-H2 check instances, including authentication, media, restart,
certificate rejection and verified native closure. These are repeated check
instances, not 547 independent tests. See
[exact current component evidence](../../docs/testing/caddy-operator-current-acceptance.md).
This loopback result does not certify later source, LAN exposure, a clean
machine installation or complete browser/release acceptance.
https://caddyserver.com/docs/caddyfile/options#enable-full-duplex
https://github.com/caddyserver/caddy/blob/v2.11.7/modules/caddyhttp/server.go
https://github.com/golang/go/blob/go1.26.9/src/net/http/responsecontroller.go

No LAN/public binding is implemented. User-selected hostname, user-approved
certificate trust, firewall and authenticated TLS exposure require future explicit
configuration and qualification; do not replace loopback with blanket LAN binds.
The backend is intentionally unauthenticated on loopback. Native requests without
Origin are compatible, NOT authenticated. Local processes remain trusted. This
single-user/one-worker service shares game/job state; BasicAuth is not per-user
authorization, isolation, quotas or a public-service security certificate.

Any later source/runtime or approved exposure configuration needs its own gate:
fresh local runtime, ephemeral private CA/leaf SAN and credentials;
real trusted-CA client (no `-k`/ignore-cert), real built HTML/assets, native 401 for
missing/wrong credentials, authenticated API and unchanged media, supported start
and legal action/recovery, trusted/denied CORS headers, malicious mutation 403
with complete controller/root/SQL equality before body/dependencies, rejected
direct exposure, restart recovery and complete child/socket/DB closure. Secret
material stays local/private and is destroyed only after closure; evidence is
sanitized assertions/statuses, not headers or key/auth dumps. The historical
official-binary and current custom-binary component results retain their exact
source/dependency bounds; neither substitutes for full deployment acceptance.

Authoritative references:
https://caddyserver.com/docs/signature-verification
https://caddyserver.com/docs/caddyfile/directives/basic_auth
https://caddyserver.com/docs/caddyfile/directives/handle_path
https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
https://caddyserver.com/docs/caddyfile/options
https://caddyserver.com/docs/command-line
