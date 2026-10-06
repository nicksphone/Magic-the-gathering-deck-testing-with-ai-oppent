# Aura Departure And Offline Import Metadata

Qualified isolated composition on published graveyard milestone `a0e7dc8`.
Main checkout and running services are not replaced by this milestone.

## Changes

- Both illegal noncreature Aura departure branches capture replacement plans,
  static causes and last-known battlefield information before movement, then
  use the shared graveyard executor. Already correct zero-loyalty handling is
  not rewritten. Simultaneous multi-Aura batching remains separate.
- Imports project available local seed/knowledge metadata without implicit
  card-cache writes or fabricated SQL IDs. Cached identifiers remain genuine.
  Explicit synchronization and cache inventory remain separate operations.
- Import labels distinguish local metadata, cached/knowledge Oracle records
  and offline seed data. Readiness does not certify all rules, art or rulings.
- Required Scryfall IDs remain unchanged. New backend contract regressions
  exercise actual projections and API responses; no speculative nullable-ID fix.

## Executed Acceptance

| Check | Actual result |
| --- | --- |
| 68 declared whole backend modules | 1,483 PASS, 6575 warnings, 1047.52s, exit0 |
| JUnit coverage | 1483 cases / 68 modules, zero failure/error/skip |
| Source preservation | All pre-gate backend/frontend source hashes match |
| Real current-source HTTP | 35 requests across five terminated server lifetimes |
| Frontend | Lint, configured tests including metadata rendering, build PASS |
| Current DTO / frozen real response literals | 267 strict assignments PASS, no casts |
| Owned cold HTTP fixture | Three stopped subprocesses, installed guards verified |

The backend gate forbids external sockets/DNS and foreign SQLite writes.
Only registered loopback traffic is allowed for the actual private HTTP fixture.
Its three process ledgers show the exact listener and no blocked outbound
attempts. Existing dependencies were reused read-only; no fresh-install claim.
SQLite runs only in owned local scratch, never on NFS.

The first 67-module run passed 1471 tests with two loopback harness setup errors.
The corrected cold module separately passed four tests. The final expanded
68-module result above is one complete fresh run, not a sum of partial gates.
All earlier logs remain preserved; warnings are not hidden or called failures.
The worker response census is frozen evidence; its current DTO assignment
does not imply new remote validation of all canonical printing IDs.

## Evidence And Remaining Work

Private verified archives are under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/aura-catalog-current-20261006/`.
Source, original harness ledger, final JUnit/isolation proofs, HTTP receipts and
closed synthetic database evidence are separate from public Git contents.

Simultaneous mill/sacrifice/SBA/destruction publication, deliberate human legend
choices, full stack-face lifecycle, canonical self-cast trigger gaps, paid
optional integration and measured tactical latency improvements remain open.
Full-suite, clean install, long-session browser/LAN/HTTPS, broad supported-corpus
correctness and professional AI strength are not established by this milestone.
