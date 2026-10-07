# Locked Frontend Release Checkpoint

Application source: `6f9e29ec2e8ea7f1ebb880a4f553960b887edafb`.
Fresh isolated source and `npm ci` installed the existing lockfile (164 packages,
four seconds); no shared node_modules or application dependencies were changed.
Runtime: Node v22.23.3, npm 11.15.0, existing cached Python environment.

## Actual Results

- Full configured `npm test`: exit 0, 16.02 seconds. All declared script groups
  complete, including real backend-generated mana/mechanic/Suspend render
  contracts. This is not a summed pytest case count or browser certificate.
- `npm run lint`: exit 0, 2.91 seconds.
- `npm run build`: exit 0, 6.24 seconds; built asset hashes retained.
- Full and production-only `npm audit --json`: both exit 0 and zero advisories.
  This is a fresh lockfile registry scan, not a Python/security/reachability gate.
- Original 166 frontend and 1,560 backend source hashes remain unchanged.

The first test attempt stopped at the documented `MTG_TEST_PYTHON` prerequisite
after earlier script groups passed. Its exit-1 ledger is preserved. Supplying
the pinned Python interpreter and exact same-revision backend fixtures allowed
the SAME whole npm chain to complete without changing assertions or defaults.
See the frontend-check commands in `README.md`. Eight Python child startup
receipts record the pre-import audit guard denying SQLite and sockets; source-
local database remains absent. No HTTP server/lifespan or SQL slot was used.
The Python audit guard is not an OS-level sandbox.

Verified source, built assets, logs, dependency tree, versions, manifests and
both test-attempt ledgers are archived at
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/parent-integration/`
with prefix `frontend-locked-release-current-20261007-`. Installed dependencies
and download cache are reproducible from the lockfile and deliberately excluded
from the evidence archive. All remaining source/evidence bytes were independently
verified before completed disposable scratch cleanup.

No live deployment, backend offline-media certification, browser/full game,
BO3/recovery or complete release acceptance is claimed. Those gates remain open.
