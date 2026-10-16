# Bounded Browser Response Metadata

The latest observed browser failures are different: the held-action scenario
receives a continued OPTIONS interception but never retains its expected POST
response pause; an earlier start-recovery scenario fails after intentionally
dropping a successful response. Neither observation establishes the underlying
browser or application cause. A protocol command acknowledgment is not proof
that the corresponding HTTP exchange succeeded.

## Diagnostic Boundary

The existing response tracer accepts an optional backend origin. The affected
programs opt in. The shared driver forwards native protocol events
without consuming command replies or changing Fetch interception. The held-action
and start-recovery programs subscribe to Network, Page and Runtime inside their
existing cleanup boundary. The accepted-response-drop flow subscribes to Network.
A rejected subscription still retains its error and the owned cleanup boundary.

The new history contains only route classes, method/status categories, local
correlation ordinals, finite failure classifications and navigation/context
markers. It retains at most 64 events and 16 request, frame and loader
identities, with explicit omission/overflow/unknown counts. It does not print
URLs, headers, bodies, card/match identifiers, native opaque identifiers, raw
errors, hashes of private values or console content. It issues no protocol or
HTTP commands itself. Existing scenario body-capture assertions remain intact;
this is not permission to enable the separate body-reading passive observer.

A preflight's native initiator reference may correlate with a later failure
without manufacturing a POST request event. Unmatched failures are explicit;
they are not attributed to the last request. Context clearing is not proof of
a React remount. Unknown same-document frame identity remains unknown. Redirects
leaving the selected routes retain only their original local ordinal.

Failure snapshots are immutable and published once. Reporting exceptions cannot
replace the original scenario error. Successful recovery does not publish a
failure report. No wait, timeout, retry count, mutation, browser flag or security
policy changes.

## Executed Checks

The final review regressions first produce 20 passes and nine failures in the
29-case metadata module. They expose missing redirect correlation, missing
Runtime subscription and skipped cleanup after rejected subscriptions. The
corrected five-whole-module declaration passes all 121 cases. The expanded
native-related **unit** command passes all 161 cases; it is not a native-browser
run. Existing stale API-key expectation and protocol-double subscription gaps
are corrected without removing their original behavior assertions.

The full declared `npm --prefix frontend test` command then succeeds using the
explicit existing qualified backend Python for its real pure-rule contracts;
the production frontend build also succeeds. Earlier missing-interpreter and
protocol-double failure ledgers remain separate, not relabeled as passing runs.
No private game trace is downloaded or used by these frontend commands.

Actual native/browser acceptance and a root-cause repair remain separate work.
Diagnostic results must not be presented as a fix for either observed failure.

## Current v2 Missing POST

The exact `79e215fb` browser job `116821296744` fails at the original
accepted-response-drop deadline. Its trace records one acknowledged OPTIONS
continuation, no POST interception, no response pause and canonical revision
zero. This does not establish that preflight completed, that the browser sent
the POST, or why the request stalled. The underlying cause remains unknown.

The v2 flow now reuses the same bounded tracer and awaits `Network.enable`
before enabling interception and clicking. Genuine native network events and
Fetch acknowledgments are attached as `requestLifecycle` to its existing single
failure report. The shared tracer and driver are unchanged. No extra body read,
action retry, recovery deadline, scenario assertion or browser security flag is
introduced. Successful recovery still emits no failure report.

Four new projected-flow controls fail against the unmodified v2 source, while
all 64 existing cases pass. After wiring, the complete 68-case recovery contract
and unchanged 29-case metadata module pass together: 97 cases, no failures or
skips. Every existing test-call body and all 27 browser assertion call sites are
byte-identical. The protocol harness drains one event-loop turn instead of
guessing a fixed microtask depth; the initial six timing-check failures are
preserved as a separate harness ledger. The configured complete frontend test
command and production build also pass using the existing locked Python
environment. An earlier full-suite attempt stops at the absent checkout-local
interpreter; it is not relabeled as passing.

These are diagnostic and protocol checks, not a reproduced native root cause or
a repair of the failed hosted browser run. A subsequent actual browser run must
retain its own source, outcome and failure metadata.

## Navigation Follow-Up

Exact `88a62c3a`, job `116831381170`, passes the accepted-response-drop scenario
but fails the later held-response assertion. Its native trace records a finished
OPTIONS200, a POST canceled with `net::ERR_ABORTED` after42.719ms, and subsequent
same-frame navigations with distinct loaders. It records no held POST response.
Those observations do not prove which code initiated navigation or establish a
CORS rejection. The first parser's expectation of another drop trace was wrong;
the corrected reading uses the existing held trace without rerunning the job.

The held observer is now installed before the existing final fixture reload, so
it can observe the new document and socket rather than guessing their history.
Interception still starts only after fixture setup returns; no reload, click,
retry or timer is added. Setup failures preserve the original error without a
match-specific read of an undefined fixture.

Additional metadata contains only finite native navigation reasons/types and
frontend-root document initiator categories. A Vite message classification needs
an observed canonical frontend WebSocket creation and a native101 handshake with
the exact `vite-hmr` subprotocol. Creation alone does not establish that identity.
Only known text-message types from bounded4096-byte JSON frames are retained;
URLs, tokens, paths, headers and payloads are not. The existing64-event limit and
16-entry identity limits remain, with a separate16-entry socket map and explicit
overflow counts. No response-body getter or observation command is added.

After independent static reviews, the combined navigation and separately branded
Firefox realm observer pass383 ordinary cases across nine whole Node modules.
Removing either helper addition restores the other reviewed postimage exactly.
The complete configured frontend command passes with the new modules registered
in normal CI:225 native-related unit cases and170 Firefox protocol/driver cases
are separate command totals, not actual native-browser results. Build and lint
also pass. All3674 runtime file bodies, four links and429 directory entries
remain exact after that command with global bytecode writes disabled. These
routine Node/Python tests are not a kernel or global I/O confinement certificate.

An actual browser run on the eventual published composition remains necessary.
Neither this protocol result nor the earlier passing drop scenario repairs or
explains the historical navigation failure.
