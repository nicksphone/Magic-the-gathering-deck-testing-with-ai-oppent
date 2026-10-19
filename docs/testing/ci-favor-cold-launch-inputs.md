# Favor Cold Test Inputs

The test caller now supplies explicit source and separate owned data paths.
The cold ASGI test worker checks its marker, parent PID, worker/source origin,
input hash and canonical database/input/output paths before backend imports.
Only its declared database or memory SQLite is permitted; default startup and
network behavior are unchanged. This changes test infrastructure, not gameplay,
storage, public API or production permissions.

All 18 original caller assertions and the worker ASGI body remain unchanged.
Four new paid both-seat cases use temporary data outside source with no inherited
audit-root environment. Four actual worker negatives reject bad markers, source,
paths or input before backend import/SQL under the owned diagnostic instrumentation.

## Actual Qualification

- Original16 with explicit old environment: 16 passed, 33.02s.
- Controlled removal of only the old child environment field: 8 passed,
  8 failed before backend import, 14.72s. Not hosted exception proof.
- New8 before repair: 8 strict failures, 5.89s; after repair: 8 passed, 15.51s.
- Agent original16 plus new8: 24 passed, 52.28s.
- Independent parent same whole24 on `6847a5f1`: 24 passed, 47.36s.

All 3000 parent pre-existing file bytes remain identical. Two genuine runtime
cache SVGs were added: the entire file set is not unchanged. The initial metadata
file-set assertion failure and subsequent classification are archived, not game
reruns. Neither SVG enters this patch. Selected agent source manifests use their
separate declared whitelist. Audit enforcement is cooperative, not a kernel
sandbox. Private NFS evidence remains under `diagnostics/ci/current-8fff-favor`
and `diagnostics/ci/favor-explicit-launch-parent24` dated 2026-10-12.

No protected CI raw logs were read or published. This resolves a locally proved
test-launch dependency; it does not establish the hosted exception, close the
separate startup-capacity failures, or certify full CI/release/AI quality.
