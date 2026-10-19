# Stage1 Native Job Durability

The corrected, unchanged 12-whole-module cohort executed all 103 cases on the
isolated frozen Stage1 source: 103 passed, 68 warnings, 913.49 seconds, driver
and launcher exit 0. The prior 102-pass/1-fail run remains immutable. Only two
new-test waits changed from 180 to 630 seconds; product deadlines, canonical
decks, original assertions and runtime packages did not change.

Evidence: `diagnostics/job-resource-contract/stage1-deadline630-actual-qualified-20261008-HxSKm1/`
under `/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/`. The full manifest is
`1e5d850545a9e3ca6293a2c24471551184f6c92fd455b577af5cafa66aee54fd`.

The gate verifies durable bounded request/result/error/snapshot writes,
idempotent replay and conflict behavior, quota/slot rejection, real cancellation
and lifespan shutdown, and cold read/replay of actual worker outcomes. The
successful background job contained one 500-tick game: zero resolved games
and one timeout. Its completed status means batch processing completed, not
that a natural game winner or seasoned-player AI was demonstrated.

Independent checks verified all 103 ordered nodes and 309 passing phases, eight
completed lifespans, six observed workers stopped, all 25 engines disposed with
zero checked-out connections, no final database descriptors or extra threads,
and unchanged source, controls and non-pip runtime bytes. The parent separately
verified the archived manifest and ran direct `fuser` against all 22 existing
local database files: exit 1 with empty output. The exclusive SQL lease was
released at 2026-10-08T02:23:22Z after closure and archive readback.

This closes the pinned Stage1 native durability component. Aggregate byte/row
escrow, exclusive process ownership, pre-migration backup, terminal retention,
crash/soak, synchronous drain, hard peak RAM and the final current-source release
union remain separate requirements. Synthetic SessionSpy measurements in the
same cohort are not durable native-write evidence.
