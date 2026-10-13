# Private HTTPS Operator Qualification

## CF1 Loopback Requalification: 2026-10-13

One actual parent-issued invocation on immutable
`cf1c3bf063bab18ceb4ca9fb1ce7337da1bfd18f` passes the complete original native
H1/H2 cohort: **547 observed check instances, all PASS**, client/outer exit 0,
55.64 seconds, no resource stop or retry. These are repeated assertions, not
547 independent tests. The original client/backend helpers, certificate and
authentication rules, request deadlines, restart checks and 800/900-second
limits remain unchanged. Only runner root literals are rebound. The operator
production delta from the historical eb8d source is one settings predicate
rejecting runtime storage below the served dist.

All 3,209 original CF1 source files plus three newly built frontend assets
remain byte/file-set equal before/end. The retained-dependency build exits 0;
225 frontend inputs and 5,682 dependency files/18 links remain equal in donor
and owned copies. This is not another clean install. The native runtime also
retains all 2,852 Python package files/four links and system binary pins; Caddy
is the exact custom `e8d6545c...` executable documented in the operator README.

All 46 positive native H2 requests verify CA and hostname. Unknown CA and
wrong hostname each produce curl 60 with HTTP/version zero and respective
verification results 20/1. Authentication, built SPA/API/media routing,
incomplete hostile body rejection, full atomic root/controller/SQL equality,
supported legal human action and actual saved-match/idempotency/media restart
checks all pass. Both production-first shutdowns verify exact pool disposal,
owner FD/registry closure and empty jobs/workers before observer assistance.
Their raw closure observations contain one non-main thread each, not zero;
external closure later verifies all 139 known process/task identities absent,
both ports empty, no owned runtime/private FDs or journals, and all four actual
database/backup/lock files unused with fuser exit 1 and empty output.
SQL is released at `2026-10-13T22:39:55.292216+00:00`.

Verified private archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/current-cf1-caddy-native547-qualified-20261013-65DlkP1r/`.
Archive SHA256:
`f47e8db3a0d12769cc4b985aa8a8ddab8f9536144919eb596234792df3eff5aa`.
All 5,526 regular members read back byte-equal with strict hashes and no links.
Keys, authentication material, operator JSON, Caddy storage and environment
values are excluded. Closed SQLite/raw evidence remains private on NFS and
is never executed there. Later HEAD is not relabelled as this source epoch.

This qualifies only the Linux private-loopback single-user/one-worker operator
component. LAN binding/deployment, Chrome/Brave/Firefox trust and gameplay,
clean-machine installation, Windows/macOS and all broader release/AI gates
remain separate requirements. No global trust or firewall change is made.

## Historical Combined Source: 2026-10-10

One complete invocation on isolated published
`eb8d8805f6ce74711508db0c7346ae3ca0921cab` passes the original H1 corpus and
strict native H2/media/authentication/restart checks. All 547 observed check
instances pass in 49.680s; these include repeated route and transport assertions,
not 547 independent cases. No scenario, gameplay check or deadline was removed.

All 2,819 captured public source files, including 1,982 backend/frontend files,
match that commit. The served three retained build assets and declared cached
dependencies are byte-pinned and unchanged; this was not a separate rebuild of
the parent frontend output. The Caddy binary and operator product files remain
unchanged. The harness leaf uses CN `wrong.invalid` and sole DNS SAN `localhost`
to exercise the actual certificate-verification boundary without CertMagic's
hostname certificate-selection ambiguity. The strict native rejection is not
relaxed to accept a generic TLS handshake failure.

- All 46 positive H2 requests use HTTP/2, native exit zero and successful CA and
  hostname verification, with no insecure transport or H1 fallback.
- Unknown CA and wrong hostname both return native curl 60, HTTP status zero
  and version zero; their verification results are respectively 20 and 1.
- The 26 original H1 and two additional H2 hostile-Origin requests preserve
  complete root/controller/SQL state. The incomplete-upload/full Origin matrix
  remains H1-only, not an exhaustive H2 claim.
- Three real H2 restart requests recover the match, duplicate action receipt
  and unchanged media bytes. Authentication, SPA/assets/API routing and the
  original H1 persistence/restart checks also pass.
- Both real backend epochs dispose the exact live pool and close native owner
  descriptors before observer assistance. Subsequent external closure verifies
  all 134 traced process/thread identities absent, both ports empty and all
  four actual SQL/backup/owner-lock files unused.

The observer saw one non-main thread during each lifespan observation; this is
not reported as zero. Those process/thread identities are covered by the later
external closure. Lease release is actual `2026-10-10T11:59:28.906517963Z`.
There are no unexpected native guard denials. The parent separately verifies
the outer 267 payloads and all nested 2,819 source bytes against current source.

Immutable current packet:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/ci/caddy-eb8d-full-H1-H2-native-PASS-20261010-1NIB2o/`.
`REPORT.md` SHA256:
`0d18860dc70c6fe878cdad37d94c2ed00c3c203cffc207ba712f75595d97ab5a`;
`OUTER_SHA256SUMS`:
`fdf1888588c8e12fc309707ee5a9d28f9674a2539fd0b55dd2582314aae31813`.
Public proof excludes keys, auth headers, request bodies, SQLite databases and
the protected CI trace. NFS is archive-only.

This qualifies the pinned loopback operator component, not browser gameplay,
protected backend CI, LAN trust/deployment, clean-machine installation or the
complete release. Earlier failed hostname/harness results remain immutable.

## Historical Operator Qualification

The Caddyfile, launcher and configuration verifier retain the exact postimages
from isolated `0e57baf1f3d48526d3a85e7a0eea45da0b3dee93` qualification.
The operator README now records that scoped result; its original tested bytes
remain archived. Later application, storage lifecycle, frontend and rules changes
are not certified by this operator run. Final combined-source/browser acceptance
remains required.

One actual invocation passed the complete native loopback corpus:

- Verified private-CA TLS, positive hostname verification, unknown-CA rejection
  and an independent incorrect-hostname validation failure (error 62).
- All 27 missing/wrong/malformed authentication checks returned 401 before
  backend access; built SPA/assets, API prefix and media routing passed.
- Authorization stripping, trusted-origin/native access, legal human setup,
  revision/idempotency handling and concurrent-launch locking passed.
- All 26 hostile-origin requests returned 403 with no body/dependency/action/
  sync/SQL processing and identical complete root/controller/database state.
- The unchanged incomplete-upload request sent zero body bytes: headers arrived
  in 0.091128s and its complete 403 body in 0.091358s, within the original 5s limit.
- Saved match, idempotency receipt and media recovered after a real restart.
  Both original lifespan shutdowns completed, engines disposed, DB descriptors
  and jobs closed; all six owned PIDs/listeners ended and `fuser` was empty.

The actual fix is Caddy's `enable_full_duplex` server option. It allows HTTP/1
responses before consuming the unread request body; native adapted JSON verifies
the option. No authentication/origin check, request body or deadline was weakened.
The four prior failed attempts and the phase-specific header timeout are retained.
The option is experimental; compatibility is proved only for this native corpus,
not every legacy HTTP client.

Verified source/evidence/closed fixture archive:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/operator-packaging/caddy-0e57-full-duplex-qualified-20261007-wVfKHc/`.
Read `evidence/ACTUAL-QUALIFICATION.md`, `INDEPENDENT-CLOSURE.json`, and
`SURGICAL-INTEGRATION-HANDOFF.md` for exact source, binary and postimage pins.
Private keys, operator configuration, password hashes and Caddy storage were
excluded and removed locally only after verified archival and resource closure.

Scope: Linux private loopback, one user/one backend worker, supplied verified
Caddy 2.11.7 binary, manual certificate and explicit trusted origin. No binary,
global trust, system service or live deployment is installed by this integration.
LAN/public exposure, multi-user authorization, clean-machine/current-browser
acceptance and arbitrary-process OS sandboxing remain unqualified. The original
README's pending-gate wording remains in the immutable tested archive; updating
current guidance does not rewrite or extend that historical qualification.
