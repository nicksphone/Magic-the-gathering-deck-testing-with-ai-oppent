# Request-Stage Recovery And Finite Failure Metadata

This composition is based on PR9 commit
`332b7aba4e25f39f6b35dba75832b7ea184a06e0`. It changes browser test
orchestration and failure reporting, not application or backend behavior.

## Recovery Contract

`browser-ui-v2.mjs` registers the exact match-action URL at Fetch Request
stage without a resource-type filter. The existing shared continuation
helper continues OPTIONS with `interceptResponse: false` and POST with
`interceptResponse: true`. Only the current POST 200 response is failed.
Recovery still requires its native failure-command acknowledgment before
the existing UI and canonical revision checks. The 15-second recovery
clock, single-commit checks, error propagation and cleanup are unchanged.

The six new actual-function VM protocols exercise registration for both
boolean capabilities, OPTIONS/POST continuation, deferred native ACK,
fatal rejected ACK, foreign/non-200 responses and unknown capabilities.
These are inert transport units, not native-browser or application proof.

Four old stage expectations change from Response to Request, and the old
pre-report UI hash binds the approved literal/comment change. No old
assertions, callbacks, clocks or test names are removed.

## Failure Metadata Contract

`browser-start-recovery.mjs` reports the existing failure-only trace through
`reportStartRecoveryFailure`. The helper projects finite method/status,
continuation counters, control state and numeric protocol-error fields into
the `Browser start recovery failure` annotation. It exports no URLs,
request IDs, raw error text, stacks, environment or response bodies.
Malformed input or an annotation sink error cannot replace the original
scenario failure. The JSON body is capped at 768 characters.

The fourteen new protocols bind the actual projector, reporter and caller.
The prior helper prefix and all scenario awaits remain unchanged. Reporting
adds no request, retry, timeout extension or browser-driver capability.

## Recorded Scope

The parent observed the original six protocols as 1 pass and 5 failures,
then the unadapted product cohort as 88 passes and 6 failures out of 94.
All six new protocols passed in that product observation; the remaining
failures were the old registration and UI-hash expectations adapted here.
The separate start-observability baseline recorded fourteen ordinary
failures. This source composition records no combined-cohort result and
no native Chrome, Brave or Firefox qualification.

`test:unit:native-browser` retains all eighteen existing operands in order
and appends only the two new modules. The eight-module Firefox script,
all other package keys, lockfile, backend and capacity contracts are intact.
