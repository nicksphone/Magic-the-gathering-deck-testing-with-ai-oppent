# Officer Browser Fixture Lifecycle

## Observed Failure

The browser job on `daa644c7` executes three natural BO3 component checks and
all 12 original interactive-preflight checks, then rejects the first Officer
action with HTTP 503, `simulation_shutting_down`. This is not a full browser pass.
No protected backend trace or backend raw CI log was read.

The Officer fixture disables FastAPI's production lifespan. Its eager table
setup does not register a database owner. The real repository dependency rejects
the request before the action handler because application ownership is absent.
The initial `SIM_SHUTTING_DOWN` value is false; resetting it is not the repair.

## Scoped Correction

The fixture now sets its exact owned `MTG_DATABASE_PATH` before persistence
imports and runs the native lifespan. The real application acquires ownership,
bootstraps capacity and opens admission before accepting requests. Only the
live owner's exact bootstrap backup and read-only URI are authorized during the
native initializer call, with the allowance revoked in `finally`.

Premature schema setup and eager controller restore are removed. Existing native
lazy match loading remains responsible for restart restoration. Both fixture
route bodies, the browser driver, original action/selection assertions, full
cohort and deadlines remain unchanged. No backend production code changed.

A separate test-helper correction adds the actual `_retired_job_response` to
the existing shutdown module's source-extraction whitelist. All original test
assertions and bodies remain. A new control verifies retired jobs reject with
410 before worker publication, including while admission is closed.

## Evidence And Limits

The worker's two whole source-protocol modules pass 42 checks in 0.76s. An
independent parent reconstruction passes the same 42 checks in 0.74s. Source
24 and cached dependency 2021 regular-file hashes match before/after; the
preimport fence admits no actual SQL, sockets or child processes. Earlier
failing ledgers and the parent's precollection capacity stop remain archived.

These checks extract real functions but substitute SQL/server/owner/FD bindings.
They do not certify real ASGI startup, SQLite locking/backup/epoch recovery,
Officer gameplay, cold process restart, graceful drain or full browser closure.
Current native/browser acceptance and all original release gates remain open.

Verified private evidence under RCHFiles:

- `diagnostics/ci/officer-lifecycle-daa-pure-qualified-20261010-4sDScGIm`
- `diagnostics/parent-integration/officer-fixture-daa-pure-parent-20261010-bCymJczr`
