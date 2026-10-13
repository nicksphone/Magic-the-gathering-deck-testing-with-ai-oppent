# Browser v2 accepted-response recovery

The recovery test now waits for the current fixture's accepted POST response to
be failed by the actual CDP `Fetch.failRequest` command before disabling
interception. Entering the callback is not delivery proof. It then requires the
same match ID, rendered revision 1, the operation error, and an idle reconciled
UI. The original revision and dropped-response assertions remain. There is one
click, no action retry, and the original 15-second wait budget is shared between
drop fulfillment and reconciliation.

## Evidence And Limits

At immutable source `9c3eff98dca2a3635fe4fdc4dfcee827dc2c14ef`, the completed
hosted browser job reached server revision 1 but failed `assert.ok(dropped)`.
That failure did not include an interception trace. Its actual callback history
and root cause remain unknown; a stale alert is not an observed hosted fact.

Six pure controls project the actual recovery source into deferred public
protocol doubles. They cover a preexisting alert, command fulfillment, a foreign
match response, command rejection, timeout cleanup, and current-UI readiness.
The original source produced four strict failures and two passes; the corrected
source passed all six. An earlier five-failure/one-pass fixture attempt is
retained separately. These controls prove a test-readiness flaw, not a native
game or hosted causal explanation.

The complete declared pure neighbor run passed 19 Node test cases, plus the
existing fixture-handoff and navigation scripts' top-level assertions. The new
configured plain-Node entry separately passed six. Pre-import fetch, socket and
process canaries were denied, with no unexpected I/O. No browser, HTTP, SQL or
game was executed for this qualification.

`npm test` appends `browser-v2-drop-response-contract.mjs` as program 49, keeping
the original 48 programs in the exact same order. Dependencies and lockfiles
are unchanged. The full configured frontend script was not executed here.
Actual whole `browser-ui-v2.mjs` runtime qualification remains pending a fresh
parent-owned browser/SQL lease; no application or browser-driver code changed.

## Deadline Follow-Up

The first frozen increment is retained with its peer HOLD: the driver checks
time before evaluation, but can return a ready result after the deadline. A
seventh pure control delivers drop fulfillment at 14.9 seconds and returns ready
at 15.1 seconds without making the driver double reject. It failed strictly on
the first helper. The corrective helper checks the same deadline again after
`waitFor`, before fetching state or asserting success. No driver, clock budget,
action retry, original assertion or configured program order changed.

## Parent Frontend Acceptance: 2026-10-13

The final helper passes all seven configured regression cases. The unchanged
cost-handoff neighbor separately passes eleven cases; fixture-handoff and
navigation scripts retain their top-level assertions. These are separate checks,
not a combined browser or backend result.

On an owned source copy with the same lockfiles and read-only Vite 6.4.4
dependencies, the complete configured `npm test && npm run lint && npm run build`
chain exits zero (16:56:48--16:57:52 UTC). All original 48 programs remain ordered,
followed by the new recovery program; all 2,409 recorded source hashes match
afterward. Network and external filesystem access are isolated by namespaces.
This is not a claim of a global Python I/O audit or a live browser pass.

Earlier owned harness attempts are retained: missing backend/interpreter input,
missing audit fixtures, missing qualification fixtures, and Vite's read-only
`.vite-temp` write. Only the harness inputs and private temporary mount were
corrected; test source, assertions, dependencies and deadlines were unchanged.
The live v2 result is recorded below. Current hosted CI still needs its own
terminal evidence.

## Isolated Live v2 Acceptance

The unchanged focused `run-browser-ci.sh browser-ui-v2.mjs` invocation exits zero
on an owned `9c3eff98` source copy plus the four reviewed recovery paths. It runs
16:59:47--17:00:28 UTC with twelve observed PASS banners, including double-intent
revision recovery and the actual dropped accepted HTTP response. All original
assertions remain. The external 180-second limit and each original test deadline
are unchanged. This focused invocation does not establish the entire configured
zero-argument browser suite or built HTTPS deployment.

The new harness installs its finite SQLite fence before application import and
isolates network, process and IPC namespaces. Its actual startup backup is bound
to the registered owner, epoch, source pins and lock descriptor. An earlier
attempt fails before browser assertions because Chrome's temporary Unix-socket
path is too long. The corrected attempt changes only Chrome's private `TMPDIR`;
the service database path, guard and test script stay unchanged. That failed
attempt and its closure receipt remain separate evidence, not a hosted root-cause
claim.
