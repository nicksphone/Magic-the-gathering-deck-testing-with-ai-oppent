# Reject Runtime Artifacts Before Source Inventory Reads

**Goal:** Preserve the launcher's immutable-source boundary without reading owner
lock or capacity-backup contents from a contaminated source tree.

**Requirements:** Source trees containing root database, owner-lock or recognized
capacity-backup artifacts must fail preparation. An inventory must never read a
file whose name ends in `capacity-owner.lock`, including unexpected nested names.
Encountered lock entries outside the existing inventory exemptions reject;
the existing mutable runtime subtrees remain exempt without content reads.
Recognized root artifacts in an existing private runtime remain admitted after
the existing ownership/type/link checks, without reading their contents.
Unknown runtime files, changed code and linked artifacts remain rejected.

**Approach:** Keep the current exact runtime exemptions. Reject protected lock
names outside those exemptions and reject source capacity backups before content
hashing. Do not broaden ignored paths or change source pins for clean trees.
No configuration, dependency, database, server or native-runtime changes.

**Compatibility ruling:** Keep the existing diagnostics, training-runs and image
cache runtime exemptions, even when an opaque data file has an owner-lock suffix.
Those contents were already excluded; rejecting them would add a new runtime
startup restriction unrelated to preventing source/lock content reads.

**Files:** `ops/caddy/run.py`, `ops/caddy/test_runtime_inventory.py`,
`ops/caddy/test_runtime_source_artifacts.py`, `.github/workflows/ci.yml`,
operator/readiness documentation.

- [x] Add file-only regressions exercising real inventory and preparation, with
  forbidden-content reads raising a distinct assertion. Observe baseline failures.
- [x] Implement early source-artifact rejection; preserve runtime exemptions.
- [x] Adapt the existing source-artifact check to require rejection rather than
  merely recording the artifact's digest. Keep its other restart/link/code cases.
- [x] Run all operator file-only/configuration/supervisor regressions. Ensure the
  hosted file-only stage invokes the new module.
- [x] Review the full change, retain failure/pass evidence, update release status
  and commit. These checks do not establish native HTTPS or full RC acceptance.

**Execution:** New module5 passes; original inventory13 cases; dist boundary8;
read-only runtime5; supervisor20; hosted-clean contracts38, in separate runs.
The initial broader neighbor invocation recorded21 passes/40 setup errors for
missing `MTG_CADDY_BINARY`; that config/LAN qualification remains open.
Independent read-only review found no remaining issues and rechecked the new
module5 and inventory13. Its verdict covers this correction only.
