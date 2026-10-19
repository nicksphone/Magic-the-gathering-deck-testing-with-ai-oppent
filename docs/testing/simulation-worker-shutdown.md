# Local Background Simulation Worker Shutdown

Scope: single process, one simulation work slot. This closes ownership of the
background `/simulate/batch/start` worker, not distributed queues or byte quotas.

Startup refuses to reopen admission while a tracked worker is alive. Admission
stays fenced until existing database initialization/restoration succeeds. During
shutdown, new starts return 503 `simulation_shutting_down`; existing keyed replay
and conflict still use their original durable semantics, and polling/cancellation
remain available. Authentication, Origin policy and the row quota are unchanged.

Every constructor-returned worker is registered with its cancellation Event
BEFORE `Thread.start`, under the same `SIM_START_LOCK` used for admission. Failed
start removes that record through the existing failure path. Runner completion
does not prematurely remove its Thread: admission/shutdown reap it only after
`is_alive()` is false. The worker itself retains responsibility for persisting
canceled/completed/failed status and releasing the slot; shutdown never invents
terminal status before the actual worker finishes.

Lifespan shutdown sets all tracked cancellation Events, then joins outside the
admission/job locks so workers can persist and finish. One monotonic 20-second
budget includes fencing, all joins and final registry cleanup. A blocked fence,
live worker at the deadline, failed finalization or self-join raises an explicit
RuntimeError. No unsafe thread termination, automatic retry, registry erasure or
graceful-closure certificate is produced on failure. Preserve records/resources
and qualify restart recovery before reopening. A stuck AI action cannot be
preempted by this cooperative mechanism.

Synchronous `/simulate/batch` remains unchanged and has no cancellation callback.
The ASGI server must drain its in-flight requests before lifespan shutdown;
the background-worker gate does NOT certify synchronous in-flight draining.
Native uvicorn/server shutdown, wider exposure, multiworker behavior, bounded
bytes/result sizes, backlog scheduling and retention/retry tombstones remain
separate requirements. Engine-pool disposal/FD closure must be observed after
workers stop; process death alone is not graceful worker closure proof.

Evidence before this delta: unchanged admission/quota/cache whole30 passed;
the real canonical Island simulator entered its original tick cancellation loop
and explicit cancel persisted correctly. Its second worker survived original
lifespan shutdown with event unset and slot held (strict baseline failed). The
failed ledger remains archived; later cooperative TEST cleanup is not credited
as product shutdown. This delta's actual same31 plus pure9 combined gate is
pending exact review/execution lease, not inferred from the pure tests.

`tests/test_simulation_shutdown.py` contains nine pure, AST-extracted ownership
protocol cases (including controlled start/shutdown race and timeout), without
importing main or executing SQL. Controlled protocol fixtures are not gameplay
proof. The original real-worker baseline and three original modules remain
unchanged; any legacy dormant-thread fixture compatibility is external harness
only, exact type/module/source pinned and recorded before removal. Product code
does not weaken its Thread protocol for mocks.

Primary references:
https://fastapi.tiangolo.com/advanced/events/
https://docs.python.org/3.12/library/threading.html#threading.Thread.join
