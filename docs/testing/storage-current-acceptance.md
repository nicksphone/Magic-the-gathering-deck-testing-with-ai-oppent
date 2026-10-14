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

## October 14 Published-Source Requalification

Immutable source `127830606cd3930b4649a8df464331c00ee98add` ran the same
three complete `release_agent` modules once: **45 passed**, 45 warnings,
**14.54 seconds**, exit 0. JUnit has 45 unique ordinary cases, zero failures,
errors or skips: retention 27, restore 11, safety 7. The bounded parent-authorized
run started at 08:30:39.721428181 UTC and ended at 08:30:55.621829640 UTC.
No production/test code, original assertions or module selection changed.

All **3,239 source files**, **3,678 cached dependency entries** and fixed inputs
were byte-equal before/end. The archived runner, guard and child bootstrap are
unchanged (runner SHA256 `5f873176c02d2c2e6f22870dc1e0202ac551397d8024f9d6ae69744bcb8e83d3`).
A separate external bootstrap bound real media globals to owned evidence before
app import; its one genuine SVG was outside SOURCE. No producer was stubbed.
The original finite guard admitted only owned scratch SQLite and the two existing
maintenance CLI modules; all **seven actual CLI children** retained that guard.
Four native negative canaries passed, with no unexpected denials. No default,
live, memory, network or NFS database was admitted.

The original runner disposed the default engine and reported no database FDs
and only MainThread; all eight recorded Python processes and both owners ended.
The exact existing-path check used **53 paths**, including one symlink alias:
52 distinct targets, of which 50 were database targets. `fuser` returned 1
with empty output. The original sidecar-collision sentinel remains intact; it is
not a live WAL. An initial post-checker misclassification is retained separately,
without a test rerun or deletion. The independent parent header-only SQLite and
sidecar scan is separately recorded, not represented as the same path count.
SQL was released at **08:34:50.272412359 UTC** after physical closure.

Closed private source, harness, ledgers, intentional negative fixtures and the
parent closure receipt are archived under
`diagnostics/ci/current-127830-storage45-qualified-20261014-lxXxEJ0E/`.
No archived SQLite was executed on NFS. Native connection-object/pool inventory
was not measured; deliberately corrupt fixtures are not claimed healthy. This
requalifies only standalone storage on the stated source, not clean-machine
install, current offline/browser acceptance, soak or overall Gates 1--3.
