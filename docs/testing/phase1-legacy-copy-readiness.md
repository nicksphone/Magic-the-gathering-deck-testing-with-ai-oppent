# Phase 1 Real Legacy-Copy Readiness

## Actual Commands And Results

On exact source `95aa731e5df4365e465058e8c3ee438d2ea5a973`, a consistent
read-only backup of the known legacy database was verified and privately
archived before a separate owned working copy was changed. This is actual
legacy-copy qualification, not a claim that the operator selected this file
for the new deployment.

The unmodified completeness CLI with `--require-rulings` initially exits one:
158 requested names, 69 pending rulings. The real sync CLI then exits zero:
68 synced names and 90 cache hits, with 136 actual Scryfall HTTP responses,
all status 200. The separate neutral API preflight also returned 200. No mock
transport, fixture response injection, forced refresh or profile recomputation
was used.

The actual post-sync completeness command exits zero. All 158 requested names
are cached, have canonical knowledge and verified rulings, and have nonblank
available Oracle text. No missing name or pending ruling remains. Empty verified
ruling lists are valid official data, not fabricated nonempty lists.

Repeating the real sync makes **zero HTTP requests**, reports 158 cache hits,
and leaves every full-table digest identical. Aliases are retained as requested
names; the number of synced names need not equal the number of canonical rows.

## Preservation And Execution Boundary

The original database and its sidecars are unchanged. Existing knowledge IDs,
learned values and opaque profile fields, existing cache IDs, decks and unrelated
tables are preserved. The pristine and qualified working copies pass integrity
checks and NFS byte readback. Source backend files remain unchanged during the
qualification; all CLI SQL handles close and no unexpected denial is recorded.

Only the owned local working database was mutated. SQLite never executed on NFS.
The commands did not start the application, HTTP listeners, browser, daemon or
simulation, and did not download images. Request/response provenance and full
public canonical API bodies are privately archived, along with the database
backups; private deck contents and game data are not public fixtures.

Independent review checked the runner, sanitized results and local/NFS receipt
equality. The original prepare/preflight scripts are single-use and must not be
rerun over their completed paths. Additional verification needs a distinct
declared follow-up, not archive replacement.

The immutable private evidence is
`diagnostics/phase1-legacy-copy-20261015-g9b5xMhF/` under the project NFS archive.
Its final summary binds the source, actual HTTP counts, source preservation,
backups, zero-request repeat and table equality.

## Limits

There are no local images in this copied dataset; image availability remains
reported separately from the Phase 1 canonical/rulings exit predicate. This
does not prove image/offline deployment readiness, engine support, AI strength,
current hosted CI or a live-database migration. Later model-domain validation
is a separate code change; its distinct zero-request compatibility follow-up is
recorded in [domain admission](knowledge-domain-admission.md).
The selected deployment and the remaining original Phase 1 scope questions are
still open. The original database has not been replaced or silently migrated.
