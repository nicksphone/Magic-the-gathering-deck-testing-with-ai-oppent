# Offline Assets: Cold Component Evidence

This is qualification of application source `6f9e29ec2e8ea7f1ebb880a4f553960b887edafb`,
not the newer current composition or completion of Gate 1.7.

## Actual Results

One authorized execution began on 2026-10-07 at 06:57:58 UTC using the sealed
v3 harness and a source-only checkout with no initial database or image cache.
The original offline probe exited zero with isolation checks passing:

- All 155 shipped card names hydrated and their fallback assets were served.
- The generic fallback and 155 placeholders produced 156 runtime media files.
- Network attempts were zero; one startup and one shutdown completed.
- An idempotent human/human Island match and repository restoration passed.
- All 1,560 original source hashes remained equal; jobs and resource lists were empty.

The requested eight-module warm suite then exited three before collection.
Pytest's logging plugin tried to write its default `/dev/null` log file, which
the unchanged runtime guard denied. Zero tests, lifespans and HTTP endpoints
executed in that phase; no JUnit was produced. This is a harness compatibility
failure, not eight application test failures. The supervisor exited one.

## Evidence And Closure

The immutable archive is under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/release-gate-1-7-gate-v3/6f9e29/`.
Its complete manifest was independently checked by the parent.

- `REPORT.md`: `89fb3b0c994070fdfcd3999c2322a229ac73c2b7ac745afb6858fc89e7473f1a`
- `SHA256SUMS`: `f7e73fd3c8bba12bdcd1cb5d0df9c481dd617f1bff04d10734f010e853dfefed`

Both workers and the supervisor ended. External checks of the actual closed
database and owned directories found no handles; journals were absent. Process
visibility limits remain recorded in the archive. The SQL slot was released at
06:58:54 UTC. Closed database bytes were archived only after closure; no SQLite
database was executed on NFS. Source, harness and prior evidence were not reset.

## Warm-Only Continuation

The separately authorized sealed v5 warm-only run began at 07:28:49 UTC. It
collected all 73 tests across the eight whole modules: 71 passed and two failed
in 27.31 seconds, with 42 warnings, zero errors and zero skips. All 23 startup
and shutdown pairs completed. Both failures were the False/True explicit-refresh
sync-route tests: the endpoint guard rejected `POST /cards/sync` before the
application handler. Isolation failed on those two denied requests; this does
not prove two application regressions or a passing complete warm gate.

The guard's test-stub namespace assumption is a source-grounded candidate cause.
Runtime function identity operands were not recorded, so the exact failed
predicate is not proven. No retry, application edit or permission widening was
performed. All 1,560 source hashes and original phase ledgers remained equal.

The immutable continuation archive is
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/release-gate-1-7-warm-terminal/6f9e29-v5/`.
Its complete manifest was independently checked by the parent:

- `REPORT.md`: `85b70f50e05447b9328198fa02029894d12e4666e7d9e98af057f13d4a70187b`
- `SHA256SUMS`: `8aeaf88e6b78f8ebc087686e4428d0078f2cb753134a07857ac604d83a7a0fd1`

The supervisor and worker ended; owned resource lists and jobs were empty.
External checks of the actual default and migration databases found no handles;
journals were absent. The SQL slot was released at 07:31:37 UTC. The new closed
default database SHA is
`ce070441fd365f6a5423f235085a61249e79f8c44de3522973dac96557a2ee05`;
runtime media increased to 169 files. Any future continuation must pin these
actual warm-end bytes, not reuse the earlier database hash or 156-file inventory.

## Remaining Work

Review the narrow exact-stub provenance guard correction and complete runtime
path contract before any separately authorized continuation. Preserve the cold
result and both failed warm ledgers; do not reset the database or relabel warmed
state as a fresh cold run.
Current-source offline qualification, canonical artwork, browser fallback,
production routing and broader release acceptance remain unproven. No application
fix or deployment resulted from this gate.
