# Explicit Browser-Origin Boundary

Scope: local single-user/single-worker API. This is not authentication, user
authorization, distributed coordination, a LAN certificate or CSRF protection
for a future multi-account credential system. Do not expose dev servers publicly.

## Configuration

`MTG_TRUSTED_ORIGINS` is read once at application startup. Comma-separated exact
canonical origins replace defaults; schemes/hosts/ports must match the page.
Use lowercase HTTP(S) origins without credentials, paths, trailing slash,
query/fragment or explicit default ports. Wildcards, suffix patterns and regex
origins are not supported. Invalid configuration fails startup with a fixed
message that never echoes credentials. An explicitly empty string trusts no
browser origins but still allows Origin-absent nonbrowser requests.

Absent configuration permits only HTTP localhost, 127.0.0.1 and [::1] on fixed
ports 5173 (Vite), 4173 (preview) and 9999 (API/docs). There is no arbitrary
loopback-port, subnet, `.localhost` suffix or Host/forwarded-header trust rule.

For a private LAN dev page, set its exact page origin BEFORE backend startup:

```sh
export MTG_TRUSTED_ORIGINS='http://192.168.8.10:5173'
# Start the existing single-worker backend using the documented setup.
```

For production same-origin `/api` reverse proxy, explicitly configure the
PUBLIC frontend origin, e.g. `https://lab.example`. Do not configure only the
internal upstream URL. A separate API origin still trusts the frontend page
origin, not just its own backend origin. HTTPS routing/certificates and broader
exposure authorization remain independent release gates. Frontend API requests
already use standard Content-Type/Idempotency-Key/X-Match-Revision headers;
there is no client-side Origin spoofing or game protocol change.

An intended private HTTPS deployment can use this explicit backend setup, with
a separately qualified TLS reverse proxy serving the frontend and forwarding
`/api` (prefix stripped) and `/card-images` to this loopback upstream:

```sh
cd backend
export MTG_TRUSTED_ORIGINS='https://lab.example'
# Use the already qualified interpreter; this does not install dependencies.
uvicorn main:app --host 127.0.0.1 --port 9999 --workers 1
```

The example is not a deployed-certificate/LAN acceptance claim. Keep external
access restricted; public/multi-user exposure is unsupported until separate
authentication, authorization, proxy/certificate and resource-limit gates pass.

The existing README LAN setup now requires explicit origin configuration for
non-loopback page addresses; this new restriction is intentional. Operators
must configure the actual trusted page rather than restoring permissive CORS.

## Request Behavior

- Exact trusted Origin: mutations pass to normal validation/handlers.
- Missing Origin: CLI, server-to-server and existing local tests stay compatible.
  This is NOT proof a request is authenticated or trustworthy; other network
  clients can omit/spoof headers. This boundary targets untrusted browser pages.
- Any unsafe HTTP method with untrusted, empty, null, malformed or duplicate
  Origin: fixed JSON 403 `untrusted_browser_origin`, no body consumption or
  router/dependency/SQL entry. No Origin, credentials or body is logged/reflected.
- GET/HEAD/OPTIONS: passed to the inner standard CORS layer. Read requests are
  not authenticated by this change. Trusted preflight succeeds; untrusted
  preflight is handled by CORS and cannot grant mutation permission.

Pure ASGI middleware is added after CORSMiddleware so it is outside routes and
dependencies. CORS uses the same exact config, credentials enabled, explicit
HTTP methods and Content-Type/Authorization/Idempotency-Key/X-Match-Revision
headers. It does not use wildcard origins/methods/headers with credentials.

## Harness And Evidence

Future browser harness startup MUST set
`MTG_TRUSTED_ORIGINS=http://127.0.0.1:<actual-frontend-port>` (or its actual
localhost/HTTPS page origin) in the backend child environment before import.
Use the frontend port, not merely the backend API port. Preserve existing
environment overrides and do not disable the guard or substitute a wildcard.
Dynamic origin injection is queued to the browser harness owner, not edited here.

The pure module `backend/tests/test_browser_origin_policy.py` can run under
pre-import native Python sqlite/socket audit denial without main import, SQL,
network or asyncio socketpair creation. It covers exact config/fail-closed
parsing, all fixed loopback defaults, configured production/dynamic dev origins,
Host spoofing, duplicates/null/malformed Origins, body-read/handler exclusion,
nonbrowser compatibility and static main middleware wiring.

Full actual application ASGI/DB witnesses and complete relevant API modules are
queued for a separate lease. No actual browser/server/SQL execution or whole
release certification is implied by the pure gate.

## Isolated Current-Source Acceptance

Exclusive leased fresh-root qualification on 2026-10-07 passed all 235 tests
across nine COMPLETE modules in 96.63 seconds: final pure policy/wiring 101,
new actual app security 33, original API smoke 7, input contracts 46, recovery
14, persistence 2, simulation admission 12, quota 16 and session lifecycle 4.
The initial pure99 log/XML and reconstructed cohort remain a distinct stage,
not a second added count. No original tests/assertions or game handlers changed.

Actual supported Island starts precede malicious start/action/card-sync/bulk/
preflight rejection. Receive/dependency/action/sync/SQL traps remain untouched
and complete root/controller/all SQL dump equality holds. Allowed production,
dynamic dev, loopback and no-Origin calls perform preflight, start, legal keep,
saved controller restoration and duplicate receipt reconciliation. Required
write headers and allowed/denied CORS preflights are exercised.

Native pre-import SQL-path/network guard canaries pass; no unexpected denial
occurs during the actual gate. Captured source hashes remain identical, exact
235 collected node IDs match JUnit, 21 tracked engines are disposed, applicable
pools have zero checkouts, no non-main thread survives and actual process/default
DB fuser checks are quiet. An original dormant-worker test leaves one cancel
event; the runner records it BEFORE own process cleanup, not as a hidden green
resource observation. No active jobs remain. There are 233 existing deprecation
warnings, not errors. No browser/listening server, installer upgrade or parent
product integration occurred in this gate.

Full report, owned patch, original preimage, stage sources, guarded runner,
source/closed-fixture snapshot, raw outputs and independent closure evidence:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/api-security/retained2331-origin-20261007-ExTz1I/`.
This scoped gate does not qualify a running HTTPS/LAN deployment or make the
older R9 browser run a qualification of this new security middleware. A future
browser gate must inject its exact dynamic frontend origin and run on the
composed security source.

## Primary Guidance

Reviewed before implementation on 2026-10-07:
- https://fastapi.tiangolo.com/tutorial/cors/
- https://fastapi.tiangolo.com/advanced/middleware/
- https://github.com/Kludex/starlette/blob/main/docs/middleware.md

CORS controls response access and preflight, not by itself handler execution:
Starlette passes simple Origin requests through. Therefore explicit mutation
rejection is separate and occurs before dependency/handler execution.
