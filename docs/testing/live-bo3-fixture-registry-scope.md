# Legacy BO3 Fixture Registry Scope

On immutable `136917284d963c076855d2452f86f8de74fbe9ff`, a genuine three-stage
FIFO reproduction failed at `fixture_state_support.adopt_fixture_state` after
an earlier fixture saved a deterministic Training root and the legacy BO3
test eagerly restored all saved matches. Its cleanup removed only its own
controller. The next fixture preserved the loaded Training controller as
part of its original registry, so adopting that identity collided.

The test-only correction snapshots the original registry before the legacy
test and restores its exact controller objects in an outer `finally`, after
TestClient closure. All original actions, assertions, inner cleanup, seeds,
RNG behavior and SQL rows are retained. No production collision guard,
capture, Factory, training reset, shared fixture or global conftest changes.

Four inert callback controls establish normal, eager-restore-error,
context-entry-error and context-exit-error cleanup: strict RED 4 failures,
then 4 passes. They execute the unchanged original body inside the new
scope, but do not qualify real HTTP or SQL.

The corrected genuine FIFO case, original whole nine-test legacy module
and four new cleanup controls form a planned fourteen-test runtime cohort.
That runtime qualification is pending separate parent issuance; it must not
be inferred from the inert controls or historical component passes.

## Actual Qualification

The planned/pending statement above records the initial PREP stage. The
subsequent parent-issued gate ran all three whole modules: **14 passed**,
74 warnings, 10.68 seconds, exit 0. Collection and JUnit both recorded 14
unique tests with no failures, errors or skips. `MTG_FIFO_PRIVATE_REPORT`
was unset, qualifying the portable public test without a private debug sink.

Historical ledgers remain distinct: the genuine baseline FIFO failed once
in 7.08 seconds at the unchanged identity-collision guard, with no policy
unexpected. An earlier startup backup read-only-URI denial was a finite
harness omission, not that collision; the initial stdout-path preflight
stop reached no tests, project imports, once marker or SQL. Neither is
relabeled as a passing run.

Parent verified all 6,100 source files unchanged during the successful gate,
22 recorded SQLite connections closed, no journals, and empty physical
handle checks for the owned database/backup/lock and runtime paths. The SQL
lease was released after closure. Evidence is retained privately under
`diagnostics/ci/registry-scope14-qualified-parent-20261014T042853Z`.

This qualifies the declared fixture-lifecycle cohort, not the full hosted
backend, every training caller, or whole-project completion. The later
documentation append is separate from the runtime's source-before/end proof.
