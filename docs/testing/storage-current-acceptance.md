# Current Standalone Storage Acceptance

## October 13 Current-Source Requalification

An isolated archive of `a9431b12ad4b98777e1421a91746af193beca582` runs
the same three complete maintenance modules, now containing 45 cases. The
first run has 44 passes and one strict controller round-trip failure: the
synthetic fixture omits `auto_sideboard`, while current restoration correctly
supplies the default `True`. A one-line fixture-producer correction preserves
the original exact snapshot assertion. The unchanged whole cohort then passes
all **45 cases**, with 45 warnings, in **7.27 seconds**, exit 0.

All non-graph source and external harness bytes remain equal before/after the
passing gate. The historical external guard is reused byte-for-byte: only
owned local scratch database files and the existing maintenance CLI children
are admitted. Eight installed parent/child receipts report no unexpected
denials; closure records no database descriptors and only MainThread. All
eight Python processes and their timeout owner end. Direct `fuser` on the 50
actual fixture databases exits 1 with empty output. The earlier unsupported
`fuser --` invocation is preserved as an administrative error, not proof.

The failed and passing ledgers, source, unchanged tests, harness and closed
synthetic databases are archived and byte-verified under
`diagnostics/ci/a943-storage-current-20261013-lMMGBxQr/` on RCHFiles.
No live/default/NFS database is opened. Source equality is an observed check,
not a physical write-sandbox claim; this remains component evidence, not a
quota/exhaustion, soak, deployment or complete RC1 certificate.

## Historical Qualification

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
