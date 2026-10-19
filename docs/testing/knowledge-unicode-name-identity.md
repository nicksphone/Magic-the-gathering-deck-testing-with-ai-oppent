# Unicode Knowledge Name Identity

## Reproduced Defect

On published `4297ed8059f56bc8e8a95379e46ca992bf19853e`, real memory and
file SQLite tests expose 48 failures and 51 passing controls. SQLite's built-in
`lower()` does not implement the Python Unicode casefolding used for requested
knowledge keys. Repeating an identical accented name can raise a unique-name
error; case-equivalent requests can create duplicate knowledge identities or
miss existing knowledge/cache rows.

The new name examples are explicitly manual schema controls, without invented
Oracle text or claims that they represent canonical game cards. Separate
unchanged official seed and DFC controls preserve real card-data behavior.

## Correction

Repository fallback predicates use one deterministic, physical-connection-local
SQLite function backed by Python `strip().casefold()`. Indexed exact-name paths
remain first. Registration is lazy, after public candidate validation; creating
a Repository or rejecting an invalid candidate does not acquire a connection.
Pool-record registration state resets with the physical connection.

Knowledge keys remain casefolded. Cache results preserve the existing requested
lowercase-key contract: both `straße` and `strasse` can point to the same row
when both spellings are requested. Exact card names still precede face aliases;
art-series exclusions and first stored spelling/IDs remain intact. The fallback
scans name expressions, not fully materialized knowledge/profile objects. It
adds no name cache, schema migration, index or duplicate-merging operation.

This correction implements casefold identity, not Unicode normalization of
canonically equivalent composed/decomposed strings. Direct ORM/SQL writes and
pre-existing duplicate rows are not silently rewritten or merged.

## Evidence Boundaries

The original diagnostic is immutable in the private NFS archive at
`diagnostics/phase1-unicode-name-diagnostic-20261015-lxyOkfk8/`.
The frozen new module passes 135 cases. The worker's separate neighbor run
passes 390 cases with three explicitly deselected application-import cases;
that result is not described as whole-ingestion coverage. Its earlier query
count regression, new expired-ORM snapshot mistake and collision regression
remain in the original ledgers. The parent composition retains the complete
ingestion module and its original application-start cases.

A distinct fresh owned copy of the previously qualified legacy database runs
the actual completeness and sync CLIs with the exact repository correction.
The result covers 158 requested names with zero missing/pending entries, then
zero synced, 158 cached, zero errors and zero HTTP attempts. All table rows,
schema and the working file hash remain identical. The original database and
sidecars remain unchanged; all four handles close with zero denials. This is
copied-data compatibility, not selection or migration of a live deployment.
Its immutable summary is
`diagnostics/phase1-unicode-copy-followup-20261015-UueVbfv8/summary.json`,
SHA-256 `74499899cb4fc9be8aaa81a92b2c8b3dd96fabc4b34006d6781e93bcf156a124`.

The parent composition passes **645 ordinary cases in 28 whole modules** in
448.28 seconds, with zero failures, errors, skips or I/O denials. Independent
JUnit accounting verifies all 510 prior case identities plus the 135 new
cases, removing only the explicit current scratch-root classname prefix while
retaining raw XML. The initial raw-prefix comparison error is preserved as a
receipt-builder issue, not a gameplay failure or rerun.

The complete ingestion module, its genuine ASGI startup/shutdown, all recovery
and model-boundary cases, repository/profile consumers and the existing
naturally played seeded game remain in the declaration. The natural-game
test's measured call is 320.901 seconds; it is not an A/B strength or causal
performance comparison. Backend hashes match before and after. The runner
closes inherited fixture connections, leaves no jobs/other threads, and an
external check finds all 221 existing owned SQLite files quiet.

The unchanged pre-import guard permits owned local memory/file SQLite and the
literal owned-path read-only `findmnt` query, denying physical sockets and all
other child commands. This is trusted-cohort isolation, not an adversarial
SQL firewall or proof about invisible unrelated host processes. Frontend
tests, build and lint separately exit zero on the composed working source.
No live operator database, learned profile, gameplay rule, scoring coefficient
or official seed is changed by this correction. It does not by itself sign off
Phase 1 or the full application.
