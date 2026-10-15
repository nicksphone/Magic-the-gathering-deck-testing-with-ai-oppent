# Knowledge Domain Admission

The original Phase 1 model specifies provenance `scryfall` or `manual`, optional
play value from 0 through 10, and optional integer threat level from 0 through 3.
The previous public repository write accepted other provenance, out-of-range
values, nonfinite scores and fractional threat levels. The new regression's
initial actual run had 24 expected-rejection failures and eight valid controls.

## Correction

`CardKnowledge` now declares the provenance literal and score bounds.
`Repository.upsert_card_knowledge` validates a complete candidate before any
query, insert or existing-row mutation. Valid writes retain existing normalized
lookup, IDs, optional nulls and JSON behavior. No AI weights, scoring coefficients
or canonical card facts were changed.

The provenance field keeps string SQL storage instead of introducing a database
enum. Original and corrected SQLite `CREATE TABLE` output are byte-identical.
No migration or DB CHECK enforcement is claimed. Direct ORM/SQL writes remain
a bypass, and old invalid rows remain readable without being rewritten. The
public repository boundary rejects such values when newly submitted.

## Actual Verification

The corrected 13-whole-module declaration passes **302 ordinary cases** in
36.40 seconds, including all 34 new cases and all 268 preceding Phase 1 cases.
Its earlier run had 301 passes and one new-test comparison failure: the test
had compared an expired ORM object's empty dump before reloading. Only the new
fixture was corrected to refresh its snapshot; product code and all original
assertions stayed unchanged.

The subsequent expanded declaration passes **510 ordinary cases across 27
whole modules** in 431.04 seconds, with no failures, errors or skips. It includes
knowledge consumers, snapshot/trace transport, profiles, import metadata and
the unchanged real seeded head-to-head smoke, which naturally completes a game.
This is non-regression evidence, not a measured AI-strength improvement.

The native pre-import guard permits owned local SQLite, actual memory callers
and the readiness script's literal read-only mount query, while denying physical
network and other child commands. One original ASGI startup/shutdown completes.
No unexpected denial, job or other thread remains; inherited fixture connections
are explicitly closed by the runner. Backend source hashes match before/end.
Independent review reports no actionable P1/P2 and separately checks model
validation and unchanged SQL storage without executing SQL.

## Real Copied-Data Compatibility

A distinct one-attempt follow-up uses the actual qualified legacy copy with
the model/repository overlay, not the earlier clean-95aa receipt. The real gap
CLI exits zero for 158 names, with zero missing or pending. The real sync repeat
reports 158 cached, zero synced/errors and zero HTTP attempts. Schema, every
table digest and the physical working-file hash stay identical; the original
database and sidecars stay unchanged. Four SQL handles close, with no denial.

That private receipt is
`diagnostics/phase1-bounds-copy-followup-20261015-6hIdPzdv/summary.json` under
project NFS, SHA256
`7c29ad5b4e5fc7f8486cd9eb9ebec7c2ed593e6f5f72de4477776d8dccd62403`.
It binds the exact three-path overlay and 1,984 source files. The underlying
[real network qualification](phase1-legacy-copy-readiness.md) remains a separate
source-specific result. Neither result replaces the user's selected deployment
or authorizes a live migration.
