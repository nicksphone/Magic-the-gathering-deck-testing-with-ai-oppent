# Fresh Dependency Runtime Qualification

Immutable `9f50190b597366e12cd1c6975844b7e868525a55` was installed in a new
isolated Python environment and frontend dependency tree. No retained user DB,
shared installer or production service was modified.

## Actual Install And Checks

- Nine declared exact backend requirements resolved to wheels; installation
  reports and wheel hashes preserve all 29 resolved packages including pip.
- Python 3.12.3 and pinned pip 26.2.1 were used; pip check exited 0.
- A real npm ci installed 164 packages from the unchanged frontend lockfile.
- Typecheck, lint, the complete configured npm test and production build exited 0.
- Actual OSV results for the 29 resolved Python packages and full/production npm
  audits reported no findings at query time. This is not universal security proof.
- All 16 recorded pipeline stages exited 0; source and persisted dependency
  manifests remained equal across the checks.

Two resolver-selected transitives differed from the older environment:
iniconfig 2.3.1 and opentelemetry-api 1.45.1. No requirement was changed.
Requirements do not currently provide a transitive hash lock; exact recorded
reconstruction depends on the archived wheelhouse and installation report.

## Fresh Backend Execution

The unchanged original thirteen-whole-module AI/entry cohort executed on the new
runtime: **655 passes in 234.43 seconds**, gate/outer/checker exit 0, no failures,
errors, skips, exclusions or adaptations. The 427 AI and 228 entry cases retain
their original assertions and node identities. The runner is byte-identical to
the earlier qualified runner; only the launcher's Python path changed.

All 2,663 source files and 1,558 non-pip runtime files remained equal. Four native
pre-import controls and six original alias denials passed; no unexpected denial
or foreign application import occurred. RNG/resource census closed equal,
MainThread was the only remaining thread, and the default source DB stayed
absent. External closure confirmed the gate and launcher PIDs had ended.

This is pure backend/runtime qualification, not SQL, ASGI lifespan, backup/restore,
HTTPS, browser, clean-machine OS or final release acceptance. The frontend build
used system Node 22.23.3/npm 11.15.0, not newly installed global tools.

## Archive And Restored Runtime Boundary

The NFS project archive contains:

- `diagnostics/dependency-audit/current9f50190-fresh-install-20261008-dQ5OgZ/full-public-source-dependencies-wheel-proofs.tar.gz`,
  SHA256 `bed4f930c4a0e9be876a52ea7193ddf70d03c0c969e184bbcbef12fd8cbb3330`.
- `diagnostics/dependency-audit/current9f50190-fresh-runtime655-qualified-20261008-dQ5OgZ/full-pure-source-controls-655-evidence.tar.gz`,
  SHA256 `769b96611af9419c56be632f91c12df6fc8e844c1b39337625303b7abb891edb`.

Both archive hashes were rechecked before parent integration. Original member
readback receipts cover 12,803 regular install members with their declared links
and hardlink, and 3,646 regular pure-gate members. A first readback assumption
error about hardlinks remains preserved; no install or game was rerun to hide it.

The completed install root was cleaned after archive verification. Its runtime
bytes were subsequently restored to a distinct local prefix for later gates.
The actual interpreter and imports were verified at that prefix, but installed
console-script shebangs retain the original path. Use the explicit restored
Python interpreter with `-m`, not those wrappers. Byte restoration is not a new
installation or a general environment-portability certificate. Subsequent fresh
SQL/browser/HTTPS qualification must identify that runtime independently.

## Current security patch: OpenTelemetry API 1.45.2 (2026-11-15)

The historical `9f50190` observations above used 1.45.1 and are not rewritten as
new test results. Current installation pins now select **opentelemetry-api
1.45.2** to address CVE-2026-126360 / GHSA-mf5v-w3w3-f6cg. FastAPI 0.142.2 accepts
this patch (`opentelemetry-api>=1.44.0`); its dependency requirements and Python
floor are unchanged. No unrelated package/version/hash is changed.

Verified against the [PyPI 1.45.2 release metadata](https://pypi.org/pypi/opentelemetry-api/1.45.2/json)
and the downloaded artifact bytes:

| Artifact | Size | SHA256 |
| --- | ---: | --- |
| opentelemetry_api-1.45.2-py3-none-any.whl | 60,335 | 2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34 |
| opentelemetry_api-1.45.2.tar.gz | 73,277 | d7b0008e21e5fd61cbe7a7f34ca3b6905a78ab677d9bc395e299359c75cda6b4 |

Wheel METADATA SHA256 is
`aa93f63be0d6d1f662966e67b22a77c0d9966752e3a32ad87c1347f595cea7cb`,
also equal to PyPI's core-metadata digest. The lock continues its existing
wheel-only, one-hash-per-row convention: the sdist is verified provenance, **not**
a newly allowed source installation. The hosted-clean wheel inventory updates
filename, size, wheel hash, metadata hash and version consistently. The closed
lock remains **28 packages**; every row's version and hash agrees with the wheel
inventory, and the other 27 rows remain byte/value-identical to the prior pins.

The CI shard synthetic runtime fixture uses the new patch version. The runtime
package-name lists need no edits because closure membership is unchanged; the
strict runtime/lock equality checks remain intact. A new stdlib regression
checks all 28 lock rows against the wheel inventory and runtime package names,
and rejects a mismatched hash.

Local/host test counts and fresh-install/advisory results must be reported for
this branch separately. This patch does not inherit the earlier 655-pass runtime
qualification as new evidence, and it does not close Gate 3 #4 until CI and the
final composed scans pass.

The hosted-clean inventory intentionally contains **29 rows including its pip
installer**. Only its 28 application rows correspond to the application lock;
the pip installer row and installer lock are preserved unchanged.

### Local verification of this patch

- `python -B -m unittest discover -s .github/scripts/tests -p test_application_wheel_lock.py -v`:
  **3 passed**, including all 28 version/wheel-hash equalities, a bad-hash control
  and runtime package membership. All 28 synthetic shard runtime versions also
  equal the updated lock. The other 27 application rows and pip installer row
  were compared directly with the parent revision and are unchanged.
- Full `python -B -m unittest discover -s .github/scripts/tests -v`:
  **420 run, 417 passed, 3 failed** in 94.089s. The same three tests also fail
  on an unchanged `main-e51` archive (3 run, 3 failed, 3.523s):
  `test_ci_backend_shards_e2e.ShardCliE2ETests.test_real_reference_four_workers_and_failed_worker_cannot_qualify`,
  `test_ci_snapshot_cleanup.SnapshotCleanupTests.test_real_closed_owner_only_passed_snapshot_is_removed`,
  and `test_ci_snapshot_cleanup.SnapshotCleanupTests.test_real_pytest_requires_all_three_passed_phases`.
  They remain unresolved local-environment failures; no assertions were weakened.
- Focused installer/runtime/metadata/shard/hosted-clean checks: **193 run,
  192 passed, 1 failed**, the same shard end-to-end case above.
- Downloaded wheel/sdist bytes and wheel METADATA were independently hashed;
  no application environment was upgraded by this work. The local interpreter
  differs from the locked environment in several unrelated installed transitives;
  these stdlib/protocol results are not fresh locked-runtime acceptance.

A host/CI fresh `--require-hashes --only-binary=:all:` install, `pip check`,
runtime metadata verification and new advisory scan are still required for the
new lock. No successful hosted-install or full application-suite result for this
patch is claimed here.
