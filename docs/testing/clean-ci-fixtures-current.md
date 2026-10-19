# Clean CI Fixture Portability

Base: immutable `22971a2e3828a93091f98440d2b891a180a298d5`. This is
test-harness acceptance, not full gameplay or live deployment certification.

## Backend And Browser Setup

Five committed backend modules reused an audit fixture that required
`ADMISSION_PHASE` during import. The same five collection errors were reproduced
locally. Canonical hashes, IDs and every existing gameplay assertion are retained;
only optional audit receipt writes are omitted when no phase was requested.
An explicit audit phase still writes exclusive canonical and observed receipts.

Eight whole modules pass all 231 checks in 33.11 seconds. A precollection native
audit hook denies SQLite connections, sockets and subprocesses; both SQLite
aliases were checked and no test attempted forbidden I/O. A new receipt check's
initial JSON-versus-snapshot comparison failure is archived separately.

Full default backend collection succeeds: 23,431 tests collected in 42.18
seconds, with no collection errors. This is collection, not a full-suite pass.
The first local filtered intake omitted two committed raw-fixture directories;
its nine missing-file errors are preserved. Restoring their immutable Git bytes
required no project code change. CI already archives those tracked directories.

The browser CI child now explicitly trusts only `http://127.0.0.1:15173`, its
declared frontend origin. The real ASGI middleware rejected that nondefault
origin before configuration and accepts both reads and writes after configuration.
Application default origins and security policy are unchanged. Actual browser
execution is separate acceptance; these direct ASGI checks do not certify it.

## Frontend Fixture

The bounded-target producer now uses the committed full canonical raw records
and provenance rather than an NFS-only bulk corpus. Both file SHA256 pins and
their original bulk provenance remain checked, and all five used card rows must
match the hydrated seed Oracle. The existing paid setup, submitted-action and
resolution assertions are unchanged. The complete configured frontend tests,
lint and build pass in the agent's immutable source with NFS reads denied.

## Remaining Gates

Run the remote full backend/browser/frontend workflow on the
published composition. Preserve all subsequent failures without exclusions or
expected-failure conversions. Local mounted-browser execution remains held for
the externally changed libpng dependency until explicit disposition.

Evidence: `diagnostics/ci/22971-37904856052-20261009` and the separate qualified
portability packet under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`.
