# POST-Only Response Selectivity

This is a browser-test harness protocol correction over a7a08c4f plus the
separately qualified early-observer317 component. It is not a proven fix for
the hosted ERR_ABORTED failure, whose cause remains UNKNOWN.

The shared continueRequestForPostResponse helper only selects POST responses
when it first receives a Request-stage pause: it continues OPTIONS with
interceptResponse=false and POST with interceptResponse=true. The initial and
rearmed start-recovery captures and the V2-costs held-response capture instead
had Response patterns, which selected OPTIONS response pauses directly.

Exactly three caller literals now use Request stage in two browser programs.
The existing callbacks/helper, endpoint patterns, headers, request bodies,
idempotency keys, POST200/body/drop/hold/resume/disable behavior, scenario
assertions, retries, clocks and deadlines are unchanged. No App/client/CORS,
driver API or Firefox adapter change is included. Three expected stage literals
and two descriptive titles in two existing contract tests were separately
approved; all other assertions and actions are retained.

The unchanged Firefox bridge supports Request patterns, genuine native request
continuation ACKs and per-request response opt-in. Its collector registration
precedes interception, and response publication joins earlier continuation
ACKs. This statement describes source/protocol contracts, not a native browser
execution qualification.

## Bounded Pure Evidence

NEW5 executes actual caller slices/helper/explicit release through an explicit
CDP phase-scheduling model. On original Response literals, actual2PASS3FAIL:
initial start, rearm and costs each exposed an OPTIONS response pause. The two
model controls passed. Those RED bytes and historical317 remain immutable.

On the three corrected literals, SAME original317 plus unchanged NEW5 produced
actual322PASS, no fail/skip/cancel/todo, across twelve whole files. Only the two
approved title identities differ in the old317 roster. Existing direct CORS
response callbacks, POST error/body/drop controls and all scenario assertions
remain. The separately declared whole firefox-fetch-collector module produced
actual20PASS; that is supplemental evidence, not a relabelled322 cohort.

The original preimport13-denial guard and Node roles are unchanged. Only the
already approved source-pinned passive-CDP31 process has Node fs-write-star;
all other roles keep scoped writes. This is cooperative trusted-unit safety,
not hostile filesystem isolation. No actual browser/SQL/provider/network/
project child, CI operation, dependency clone or W/index mutation occurred.
Source/Node/guard before/end matched; known PIDs ended, owned temp directories
were empty and owned-directory fuser checks returned1 with both streams empty.

The whole firefox-transport module was inspected but NOT executed: its real
symlink-negative case needs a separate Node22 trusted fs-write-star role, not
silently inherited permission. No native/whole-Firefox/whole-frontend/backend,
Phase1 or RC qualification follows from these pure results. Parent owns the
integrated graph refresh and any later hosted capture. This publication note
was authored after the pure gates, outside their frozen source tree.
