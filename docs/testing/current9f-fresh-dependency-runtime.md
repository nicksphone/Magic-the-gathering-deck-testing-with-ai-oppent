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
