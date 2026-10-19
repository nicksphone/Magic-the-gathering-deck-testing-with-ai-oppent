# Hosted Cache-Recovery Checkpoint

Exact source `95aa731e5df4365e465058e8c3ee438d2ea5a973` completes CI run
`38694331355`, attempt 1, including backend job `116287256387`, successfully.
This is the cache-recovery source, not the subsequent model-domain, Unicode
repository or decoded-JSON validator corrections.

## Independently Reconciled Backend Results

The allowlisted `backend-metadata.json` accounts for 28,710 unique collected
nodes and 86,048 setup/call/teardown records. There are 28,628 passed calls and
82 setup skips; skipped bodies are not passes. The 111 passed subtest reports
belong to 21 parent nodes and are not additional collected tests. All teardowns
pass. There are no failed bodies, collection errors, missing/duplicate phases,
deselections, unexpected nodes or expected-failure markers.

A separate parent cross-check reconciles the raw sanitized rows without using
the reporter's aggregate as proof. It also matches all 92 cache-recovery case
identities to passed setup, call and teardown records. Their test source is
byte-identical to the reviewed cache-recovery module, SHA-256
`a9eb0e9e2c65fa6d1bf021550b433347bf7a29574e2686c727353254c2687c60`.
This closes the absence of hosted evidence for that correction on this source.
It does not certify changed later repository/model behavior.

## Access And Provenance

Only the exact run/job/artifact identity metadata and named backend-metadata
artifact were retrieved. Its ZIP contains only `backend-metadata.json`; the
archive SHA matches the GitHub artifact digest. No raw backend log, protected
private game trace, other artifact payload, application, SQL or test execution
was used by this audit.

- Artifact: `11961343714`, `backend-metadata-95aa731e5df4365e465058e8c3ee438d2ea5a973-1`.
- ZIP SHA-256: `1c37770948604333cea05f6c58206348b83f64a9ba23e93c774954903abf2fd6`.
- JSON SHA-256: `87f174a9aa00a8e0ac58dbd8d398cdac1c575ef57a288fdc811d23de43e4eefb`.
- Private receipt: `diagnostics/ci/backend-95aa-metadata-independent-20261015-4EHbNX9K/receipt.json`.
- Receipt SHA-256: `0e63826684c72d1bbfef6feac0e1c95f4d9d5fc0b25d7e055c1c8b445ba4b37a`.

Metadata-builder corrections remain in their ledgers; none required a test or
gameplay rerun. Full manifest and archive readback verification passed.
Live deployment, later source, Firefox/LAN, measured AI strength and full
release acceptance remain separate. Phase 1 is not signed off by this result.
