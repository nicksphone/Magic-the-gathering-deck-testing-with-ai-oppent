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

## Remaining Work

Review an explicit owned pytest log-file path and other implicit output paths
before a separately authorized warm-only continuation. Preserve the cold result
and failed warm ledger; do not relabel a warmed database as a fresh cold run.
Current-source offline qualification, canonical artwork, browser fallback,
production routing and broader release acceptance remain unproven. No application
fix or deployment resulted from this gate.
