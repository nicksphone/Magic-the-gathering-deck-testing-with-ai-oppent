# Accepted-Response Pattern Restoration

The hosted recovery check passes on `03fdf68e` with an exact-URL, unfiltered
Response pattern. Commit `1a4beb3e` adds `resourceType: 'Fetch'` on CDP. Later
hosted runs, including `e8811ad0`, abort the action before the intended accepted
POST200 can be dropped. The public trace records an un-aborted application
signal and canonical revision 0; a 15-second timeout is the symptom, not evidence
of a slow server or accepted mutation.

The existing four direct CORS probes already use the same 30000ms AbortSignal,
headers and action shape and pass without a resource-type filter. The candidate
therefore restores the earlier unfiltered pattern with one changed UI-test
line. This is a source-supported regression candidate, not a claimed Chromium
internals diagnosis. Real hosted browser confirmation is still required.

## Preserved Contract

The exact action URL, Response stage, strict boolean transport-capability
validation, native OPTIONS continuation, POST200-only drop, command ACK waits,
fatal callback errors, revision1 reconciliation and original deadlines remain.
There is no added retry, synthetic response or relaxed accepted-mutation check.
Both driver capability getters and their non-enumerable command surfaces remain
unchanged. One stale CDP table golden removes its expected filter field; every
existing 147 case identities and all drop/reconciliation assertions remain.

Four new actual-function VM controls exercise the plain pattern for both
capability values, the original continuations, single drop and unchanged error
identity. These are mocks, not real browser or gameplay certificates.

## Actual Checks

The correct-layout baseline runs 151 cases in four whole modules: 150 pass and
the new CDP pattern expectation fails. Its original 147 cases pass. The candidate
runs the same 151 and all pass, with 52 expected denials, unchanged source/Node
binary/system inputs and physical release at `2026-10-19T00:18:42.495425Z`.
No SQL, provider, real browser or new child-execution role is granted.

An earlier wrapper attempt uses a home-directory temp root incompatible with
the existing passive-observer private-directory contract: 125 pass and 26 fail,
including 25 harness-layout failures. That attempt is preserved separately.
Only the fresh actual output root moves to the previously qualified `/tmp`
layout; source, tests and permissions do not change between those baselines.

A fifth typed-filter CORS diagnostic and its tests are prepared and archived,
but deliberately not applied or executed. The current four live probes and
the complete existing browser suite stay unchanged. Native Chrome, Brave and
Firefox acceptance and full release qualification remain separate requirements.
