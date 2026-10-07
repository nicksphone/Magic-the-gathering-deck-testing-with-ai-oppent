# Native Job Shutdown And App Pool Closure

Parent application preimage: `dbd466f9211b5b180863e67a0f42313430baf9fb`.
The exact tested main-file change is `4f303d3` to `2109f88`; no rules engine,
cost, API schema, dependency or live-service change is included.

The application fences new background-job admission during shutdown, signals
all registered workers and joins their real threads outside admission/job
locks. The registry retains threads until actual exit. One shared 20-second
shutdown deadline covers fencing and joining; timeout remains an explicit
failure, not a claim that a live worker stopped. Existing-key replay/conflict
semantics remain intact. After successful joins, the application disposes its
global database engine; a failed join does not dispose an engine used by a
live worker.

Observed gates are separate, not a summed suite:

- Original 31-case native baseline: 30 passes, one real active-worker shutdown
  failure, preserved before the fix.
- Worker-only fix: 40 passes. Worker cancellation/join and slot release passed,
  but two idle pool descriptors remained until external disposal.
- Worker plus application-engine closure: 44 passes. Real midgame cancellation
  persists; actual lifespan exit joins the worker, empties cancellation and
  worker registries, releases the slot and closes application database handles
  before external cleanup. A new real lifespan reads persisted canceled jobs,
  admits another real worker and closes cleanly again.

The latter cohort contains the unchanged original 30 tests, nine ownership
checks, the unchanged native baseline, three lifespan-order checks and one
native cold-restart check. The old tests' exact source-pinned no-op thread
fixtures receive an external harness adapter, never a production type filter.
Those fixture cases are not presented as real worker lifecycle proof.

Native pre-import guards deny foreign/URI database paths, network bind/connect,
DNS and subprocess creation. Framework event-loop socketpairs are permitted;
this is not an all-socket or OS sandbox claim. Actual resource closure, source
equality and closed local-database archive readback passed. No SQLite database
was executed on NFS.

Verified evidence under
`/mnt/rchfiles/codex-storage/mtg-deck-testing-lab/diagnostics/job-resource-contract/`:
`becc866-actual-baseline-failed-20261007-QooDUt/`,
`becc866-shutdown40-qualified-20261007-ywYvnF/`, and
`becc866-engine44-qualified-20261007-L6DFnr/`.
The frozen preparation document remains historical; this observed gate record
does not rewrite its pre-execution wording.

Remaining acceptance includes synchronous/inflight request draining, wall-clock
simulation limits, byte retention, quota/load coordination, concurrent
maintenance, crash recovery and final composed-source/server qualification.
This component does not close the complete operations gate.
