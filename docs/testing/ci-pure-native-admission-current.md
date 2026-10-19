# Pure Diagnostics And Native Admission Fixtures

## Scope

This test-only increment is qualified on published `9f7c7c13`. It changes seven
existing test modules and adds three test/support modules. Production ownership,
capacity, repository, application, API and private-input policies are unchanged.
All 291 original assertions and their parameter decorators remain intact.

Pure diagnostic repositories now use an explicit in-memory driver under the
actual repository encoding, reservation and capacity-transaction contracts.
Fixture adapters recognize only that driver; unrelated sessions retain native
owner checks. This is not SQLite durability or native in-memory ownership proof.

Native admission tests acquire a fresh file owner, initialize capacity with an
owned backup, and retain ownership through the complete test lifetime. Module,
function, nested replay and genuine application-lifespan scopes preserve ambient
engine aliases, simulation maps, shutdown state and work-slot objects. Both an
absent source default and an existing unopened text sentinel are supported.
The production prohibition on explicitly configuring a different database while
a legacy source database exists is preserved and independently observed.

Cleanup fences native admission before stopping workers. A controlled shutdown
failure retains the owned engine, worker references and owner lock until the
waiting test thread stops. It rejects a new native producer. This is a teardown
protocol test, not a simulated production workload or general crash-recovery
certificate.

## Actual Qualification

- Nine declared whole modules: 163 passed, 20 warnings, 31.60s, exit zero.
- Seven whole pure modules: 147 passed with SQL and sockets denied before
  collection and in actual fixed restart children; terminal evidence is archived.
- Two native whole modules with a preserved source sentinel, distinct ambient
  engine aliases and populated simulation caches: 16 passed in 1.62s.
- Original assertions and decorators are preserved; all other 2,065 tracked
  Python/JSON/JSONL inputs match the immutable base.

Native terminal owners, database/owner handles, new threads and denied attempts
are zero. The mixed runner's Python audit applies to its parent only; it does
not claim restart-child audit inheritance. The separate pure runner explicitly
installs its fence in the actual restart children.

Archived histories include the worker's superseded SQL fixture, a missing
basetemp-parent setup failure, two absent-default failures, two ambient-state
failures, and a controlled failed-shutdown regression. Each correction follows
observed failure; no case is skipped, deselected or xfailed. Immutable worker
archives are not rewritten.

Logs, JUnit, source manifests, postimages, read-only reviews and closed synthetic
SQL evidence are retained on NFS. No private game trace is opened or published.
The remaining Oracle, restart, private compatibility and complete remote CI
requirements remain separate; full release qualification is unfinished.

The preceding browser job reaches ordinary passing episodes before its
15-minute job deadline cancels execution. Its job-only budget is now thirty
minutes; original episodes, assertions and per-episode deadlines are unchanged.
This scheduling correction is not a completed browser qualification.
