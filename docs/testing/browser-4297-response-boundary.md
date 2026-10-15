# Browser Response Boundary Checkpoint

## Observed Native Results

Exact published `4297ed8059f56bc8e8a95379e46ca992bf19853e` completes native Linux
run `38701366423`. Chrome job `116310088820` and Brave job `116310088526` each
independently match all 45 ordered stage headers and 501 PASS banners. Actual
allowlisted metadata verifies source/preflight/driver pins, enabled sandbox,
successful process closure and empty control groups. This does not qualify
Firefox, remote LAN trust, AI strength or the full release.

## Separate Generic Browser Failure

The same source's generic browser job `116309466280` in run `38701180928` fails
in the accepted-response-loss test after the preceding UI/action checks pass.
Its trace has no observed response before the existing timeout. Request-stage
callbacks return before that old trace is populated, so an empty response list
does not prove that no request was sent or no action was committed.

The runtime root cause remains unknown. The native successes do not erase this
failure, and local pure tests are not a native reproduction.

## Bounded Diagnostic Correction

The failure trace now distinguishes observed OPTIONS/POST pauses, attempted
continuations, actual native acknowledgments/errors, pending acknowledgments
and outstanding callbacks. Failure-only observations read rendered revision,
the enabled matching-control count, canonical revision through one read-only
GET, and sanitized product/protocol identity from a real `/json/version` reply.
Unavailable or timed-out observations remain explicitly unavailable.

All observations share the existing one-second diagnostic bound. The original
15-second action deadline, mutation count, native continuation/drop actions,
assertions, pending-callback drains and original exception are preserved. There
is no timeout increase, mutation retry, inferred browser identity, Firefox CDP
fallback or sandbox-policy change. No raw URL, identifier, body or key is added
to the trace. A version request is not added to successful browser opens.

The existing 44 pure case bodies are preserved. The expanded standalone
contract passes 64 cases; the diagnostic component passes 174 pure cases.
Those results establish the diagnostic protocol, not the runtime root cause.

Only browser-job logs and allowlisted native metadata were downloaded. No raw
backend log or protected private game trace was fetched. Exact prior outcomes
and full private evidence remain immutable under
`diagnostics/ci/native-4297-browser-failure-supplement-20261015-2RXD7gPm/`.

## Subsequent Held-Response Boundary

The same `f2200b08` source separately completes both native vendor suites in
run `38708291897`: Chrome `116333077433` and Brave `116333077057` each match
all 45 ordered headers and 501 PASS banners, with enabled sandbox, exact
preflight/driver pins and verified closure. This does not transfer acceptance
to the later JSON-validator or held-diagnostic source.

Published `f2200b08970fd81099ea420df919f472a0e7323c` passes the preceding
accepted-response-drop scenario, but generic browser job `116332921108` fails
later at `browser-ui-v2-costs.mjs`'s `assert.ok(held)`. The pending-operation
and disabled-controls assertions passed first. The original 100-by-20ms wait
did not observe the held response. This is a distinct observed failure, not
proof of its cause or proof that the earlier intermittent boundary is fixed.

The existing shared trace recorded request activity but published it only on
callback exceptions. Its new callable `reportFailure()` method permits one
idempotent, immediate, cloned failure-time report when the outer assertion
fails. Actual pending-command counts and observed native acknowledgments are
retained. The outer catch concurrently reads UI state, canonical revision and
real browser identity within one shared 1000ms diagnostic bound, then rethrows
the original error. The original wait, every assertion, mutation, and native
enable/continue/disable command remain byte-identical. No retry or timing fix
is inferred from this instrumentation.

The expanded combined component passes 196 pure cases; 52 targeted cases are
independently reproduced. The original 30 case bodies remain unchanged. A
31-pass/19-fail diagnostic RED precedes the implementation. No local browser,
network or SQLite execution is used by these pure checks. The driver's existing
fire-and-forget callback lifecycle and native runtime cause remain unqualified.
Private exact-source evidence is under
`native-held-boundary-diagnostic-20261015-ZtEE9T/`.
