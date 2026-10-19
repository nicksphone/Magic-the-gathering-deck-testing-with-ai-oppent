# Fresh Runtime HTTPS Qualification

One actual gate completed on immutable
`1c3fbbde348ed5fa6d112264c0b85325fa6c415c` with the exact tested frontend
assets archived by the human-response controller-role increment. No install,
build, product edit or gate retry occurred during execution.

## Actual Coverage

Outer and client exited 0. The terminal contains **205 passing check instances**:
111 stable non-polling instances and 94 process-identity polling instances. The
older terminal contained 181 instances: the same 111 plus 70 identity polls.
Independent parent comparison confirms identical check-name sets and every
non-polling count. Extra polling is not extra test coverage.

- Actual owned-CA TLS and hostname verification, typed unknown-CA rejection and
  native wrong-hostname code 62; no ignored certificates or global trust changes.
- Nine SPA/assets/API/media paths each reject missing, wrong and malformed
  authorization before the backend: 27 rejections. All 42 backend request
  receipts show authorization stripped; prefix and built/media byte checks pass.
- Trusted Origin and native no-Origin compatibility, explicit CORS and mutation
  headers, actual supported starts, discovered legal keep, revision/idempotency
  action and duplicate receipt.
- Twenty-six malicious mutation requests reject before body/dependencies/action/
  sync/SQL with complete root/controller/SQL equality, including an incomplete
  request body.
- Concurrent launch lock rejection, two real application lifecycles and
  persisted match, receipt and media recovery after restart.
- Twenty native denial controls across both backend lifecycles; no unexpected
  native denial. Only the reviewed finite SQL/backup and process roles are allowed.

## Equality And Closure

All 2,665 committed files and three candidate build assets stayed equal. All
1,558 non-pip files and the full restored runtime's 7,718 regular files, 22 links
and one hardlink remained equal, with no extras. The explicit restored Python
interpreter was used, not old-path console wrappers. Fresh-package provenance is
the earlier genuine install, not a new installation at the restored prefix.

Independent physical closure completed at `2026-10-08T20:24:10.322625Z`; the
SQLite lease was released at `20:24:48.117815Z`. All nine captured process
identities/groups ended, both ports were vacant, and the primary DB, two epoch
backups and both locks had empty fuser output. Both original shutdown contexts
succeeded with engines disposed, zero checked-out connections/jobs/native DB FDs.
Their raw one-nonmain-thread boundary observations remain recorded separately
from final process/thread absence.

## Evidence And Limits

NFS project archive:
`diagnostics/operator-packaging/current1c3fbbd-fresh-HTTPS205-qualified-20261008-J9Qjug/sanitized-source-controls-evidence-closedDB.tar.gz`

SHA256: `eb2a0920a34b8bfbf641a9c5e42480089a0020f9d4842fce432543d3350f79e9`.
All 4,557 regular members were read back. Private keys, operator authentication
hashes/configuration and Caddy private storage are excluded. Closed local DBs
are archived only after closure; SQLite was never run on NFS.

An initial parent observer incorrectly expected exactly 181 instances. A worker
read-only phase-schema observer also failed. Both administrative errors are
preserved; neither caused a gate retry or a source/test change. Parent artifact
comparison and verification receipts are archived under
`parent-integration/fresh-https-badblock-evidence-20261008/`.

This qualifies the declared owned-CA loopback single-user topology and immutable
component, not live browser countdown behavior, trusted LAN/global service,
multi-user deployment, arbitrary-child OS isolation or the whole current release.
