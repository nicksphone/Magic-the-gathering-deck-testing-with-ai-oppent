# Current Standalone Storage Acceptance

Application baseline: `29e86e4d17381ff09b40d252f649224deaf48f66`.
Three unchanged whole modules (`release_agent/test_retention.py`,
`test_restore.py`, `test_safety.py`) passed all **43 cases**, with 45 warnings,
in 6.79 seconds. No filters, skips, expected failures or original-test edits.

The checks cover conservative age/newest retention, active and linked record
protection, locks and transactional rollback, dry-run CLI behavior, consistent
WAL backup, destination collisions, failed-write cleanup, integrity/content
fingerprints and actual saved match/controller/idempotency reconstruction.

The external guard was installed before collection. SQLite was limited to
canonical owned scratch files; memory, default, foreign and network databases
were denied. Native sockets and arbitrary child processes were denied. Seven
actual maintenance CLI children have installed-guard and import-hash receipts.
All eight gate/CLI processes ended; pool disposal, empty database descriptors,
MainThread-only closure and an actual empty `fuser` result on 48 fixture databases
were independently checked. All 2,389 tracked inputs and the owned marker stayed
byte-identical. One existing generic token SVG was generated separately.

Verified evidence, exact harness, JUnit, raw logs and closed fixture archives:
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/storage-acceptance-current-29e86-20261007/`.
Preparation policy checks, administrative cwd/output-classifier errors and their
corrections are retained without rewriting a gameplay run. Intentionally corrupt
test inputs are not claimed to be healthy production databases. SQLite evidence
is archived closed; never execute it directly on NFS.

This qualifies the existing standalone maintenance/recovery tools on the pinned
source, not live maintenance, API retry tombstones, job quotas/cancellation,
multi-worker coordination, clean-machine installation or browser soak. Native
Python audit receipts are not an arbitrary-process OS sandbox certificate.
Overall release Gates 1/2/3 remain open.
