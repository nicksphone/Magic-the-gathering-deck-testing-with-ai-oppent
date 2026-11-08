# Current-source ASGI qualification with a test-loop timer

The sandbox blocks sends on asyncio's self-pipe. An isolated Python 3.12.3
socket-pair probe creates the pair but `send` raises `PermissionError(1)`.
Local stdlib code queues cross-thread callbacks before trying that send and
catches its `OSError`, leaving a waiting selector without the intended wakeup.
The unchanged tiny sync/async FastAPI TestClient probe stalls at the portal and
exits after eight seconds with thread stacks retained.

A disposable `DefaultEventLoopPolicy` adds one periodic callback every 10 ms.
The same tiny probe then completes. This adjustment is outside product and test
sources: no route, assertion, transport, worker, gameplay policy or native guard
is patched. Scheduling differs from an ordinary environment, so these runs are
bounded ASGI component evidence, not the canonical hosted invocation or network,
browser, timing or native Forge qualification.

## Whole-module results

| Whole modules | Result | Scope |
| --- | --- | --- |
| `test_forge_routes.py`, `test_forge_checkpoint_routes.py` | 27 passed, 98 subtests; 7.04 s | Synthetic managers through actual unchanged ASGI routing; no SQL, network or child process attempted |
| `test_manual_autoplay_collision_http.py` | 4 passed; 5.62 s | Both seats, revisioned/unversioned concurrent requests, original barrier/lock/checked actions, durable SQLite and restoration |
| `test_api_input_contracts.py` | 46 passed; 41.82 s | Real application lifespan/SQLite; existing malformed, wrong-actor, atomic rejection, hydration and action contracts; authored positions are not full rules certification |
| `test_human_bo3_interactive.py` | 1 passed; 227.20 s | One actual programmatically piloted human-controller BO3 and cold between-game restores |

The SQLite cohorts use a source-only archive of `4775d475` with all 2,875 tracked
backend/audit inputs hashed before/after and unchanged. Source lease markers and
the existing owned-capacity setup are retained. The collision and input cohorts
record 16 and 300 connections respectively, all targeting their owned fixture or
bootstrap databases, with zero recorded forbidden operations. Source-default/user
databases are not used. Existing deprecation warnings remain visible.

The audit observes connection targets and selected socket/process/artifact
operations. It is not a universal filesystem or SQLite sandbox: a connect hook
alone does not fence SQL `ATTACH`. Independent review found no such path in the
reviewed collision flow. Ordinary file access is not universally fenced by this
hook. These limits prevent transferring a narrow result into an unrestricted IO
or privacy certificate.

## Actual human-controller BO3

The unchanged existing fixture completes three natural Python-engine games,
with 780 accepted decision POSTs, a final 2–1 score and the original 1,190-second /
6,000-action bounds intact. External test pilots choose actions for two human
controllers; this is not a manually played browser game or an AI-strength sample.
No winner or gameplay state is forced by the execution harness.

After each of games one and two, the exact committed read-only cold worker opens
the declared owned database, reconstructs the match and compares full snapshots
and sideboard confirmations. Its original SQLite alias, network and nested-child
guards and 60-second timeout remain active. A separately pinned timer-only startup
shim services that worker's TestClient loop. Both child shim hashes match before /
after, both workers finish and their PIDs are absent after the test.

The parent allows only the exact worker/interpreter/source/cwd/environment and
valid UUID-shaped argument. The supervisor binds this single run to CPU one and
its own process group, retaining 1,210/1,220-second runner/outer bounds. The run
exits zero, its direct child is reaped, no leftover group is found and the group
is absent. Unexpected supervisor interruption lacks a general `finally` cleanup;
any future interrupted attempt requires independent owned-group cleanup and must
remain incomplete evidence.

Separate receipt readback rehashes all 2,875 source inputs, verifies the one-test
JUnit result, three games, two cold restores, sequential accepted-POST records,
terminal score and closure metadata. Raw snapshots, hands and decision records
remain private and are not public fixtures.

Independent final review checks source/hash bindings, the whole-module JUnit
result, both worker completions and supervisor closure metadata, with no remaining
findings. It accepts this bounded episode; it does not inspect raw game bodies or
qualify the broader release.

## Preserved failures and provenance

The first two database attempts each stop with four setup errors: the audit
wrapper initially mis-parses owned SQLite file URIs, then rejects owned `Path`
arguments. Both harness versions, errors and source equality records remain.
The corrected third collision attempt passes unchanged product/test code. The
original declaration's `retries: 0` does not describe all attempts; the explicit
attempt ledger records three collision invocations and zero repeats under the
final collision harness. The API input and natural BO3 modules each run once.

Before the BO3 launch, independent review catches a second Path/string mismatch
in the child cwd guard and missing shim provenance. Exact callback controls first
fail, then pass three accepted cwd forms and nine rejection cases; no natural
game is spent on that draft. Shim pin/completion checks are added before launch.
Independent static review clears these findings; this does not replace execution
and closure checks.

Private declarations, hashes, probe stacks, original failures, guard controls,
JUnit and process receipts are retained in
`/home/nick/mtg-rc-evidence-20261108/asyncio-timer-probe/` and
`/home/nick/mtg-rc-evidence-20261108/http-current-4775/`.

Remaining work includes different-card sideboard swaps, completed-series cold
restoration, broader current-source HTTP/rules interaction, browser/TCP/HTTPS,
unchanged guarded native execution and hosted qualification. No release gate is
closed by these runs.
