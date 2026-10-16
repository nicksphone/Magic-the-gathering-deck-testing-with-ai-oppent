# B720 Hosted Backend Reconciliation

The exact hosted run `38866253264`, attempt 1, succeeds at source
`b7201869f52b4de4fa36f5959718986c02dbf93a`. Backend job `116859657711`
starts at 07:17:18 UTC and finishes at 11:46:38 UTC on 2026-10-16.
This is an older full-source result, not a whole-backend pass for later commits.

Independent reconciliation of the sanitized metadata verifies 29,664 unique
collected identities: 29,582 passing calls and 82 setup skips. Every teardown
passes; each non-skipped identity has one passing setup, call and teardown.
There are no missing, duplicate, failed, deselected or expected-failure phases.
The 111 passing subtest reports are counted separately, not as additional unique
collected tests. Skipped bodies are not passing executions.

The terminal-only intake admits the single expected
`backend-metadata-b7201869f52b4de4fa36f5959718986c02dbf93a-1` artifact.
Its API-bound ZIP digest is
`48d9bcdd94fc99fa2dc5762c627f837c7bc99f65eb42a071bce01c13ef9f014d`;
the sole JSON member has SHA256
`59c61de639f45f4385a245a7b1d5b62192bda7f1665042be27d3e1fa6bdea049`.
Run, job, attempt, source, bounded sizes, member CRC, payload source and individual
phase identities are checked independently. Raw backend logs and the protected
synthetic trace were not fetched. The first local reconciliation exceeded its
120-second bound because it repeatedly rebuilt a membership set; a separate
linear reconciliation of the already verified local JSON succeeds without
another download or hosted test execution. Both administrative ledgers remain.

The knowledge, card-data, decks, persistence and scripts Git trees and backend
requirements are identical between this source and `a75ce7cf`. This supports
continuity for those unchanged paths, not a claim that subsequent rules, AI,
fixtures or frontend changes passed this older run. The remaining canonical
fixture scope and final integrated Phase 1 acceptance remain open.

Private immutable intake, reconciliation and readback evidence is under
`diagnostics/ci/b720-sanitized-terminal-PASS-20261016-Na0lnDJG/` in the project's
NFS archive. No private trace or raw job log is included in this public note.
