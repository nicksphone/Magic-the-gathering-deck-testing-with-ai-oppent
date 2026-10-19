# Browser Fetch Filter Capability

The main and release-owned browser drivers expose a read-only,
per-page `supportsFetchResourceTypeFilter` capability. CDP pages return `true`;
pages using the bound Firefox transport return `false`. This is a transport
capability, not a user-agent, browser-version or input-device inference.
It is non-enumerable, preserving the existing public command-key interface.

The dropped-response recovery scenario requires an explicit boolean before
enabling interception or clicking an action. CDP uses the existing exact action
URL and response stage, with `resourceType: 'Fetch'`. Firefox retains its
existing URL/stage pattern; its transport still rejects resource-type filters.
Missing or non-boolean capabilities fail immediately. The action, accepted
response drop, revision reconciliation and interception cleanup assertions are
not weakened, and no retry or longer deadline is introduced.

## Local Regression Evidence

On October 18 the same three whole modules run before and after the change:

| Whole Module | Before | After |
| --- | --- | --- |
| `firefox-driver-contract.test.mjs` | 32 pass, 4 fail | 36 pass |
| `browser-v2-drop-response-contract.mjs` | 69 pass, 3 fail | 72 pass |
| `browser-fetch-causal-order.test.mjs` | 8 pass | 8 pass |

All 108 inherited cases pass in both runs. The seven baseline failures exercise
the missing driver getters, CDP filter selection and unknown-capability
rejection. Eight new cases are added; the explicit Firefox-false control
already passes before the fix. The causal module is registered in the native
browser unit-test script rather than left outside the project test command.

Both executions use the unchanged guarded Node preload, with 39 expected denial
controls and no unexpected requests. Source, Node and system checks are equal
before and after. There are no skipped or cancelled cases, surviving children,
database files or leaked descriptors. The shared native lock is released after
closure. Candidate release is `2026-10-18T20:32:58.641726Z`.

These are protocol-mock and actual-driver contract tests, not native-browser
acceptance. They do not prove that Chrome's hosted preflight cancellation is
fixed, nor certify Brave or Firefox gameplay. The complete frontend command and
genuine accepted-action/drop/reconciliation flows still need their CI results.

## Enumeration Compatibility Follow-Up

The first hosted full frontend run of `1a4beb3e` fails its unit-test step.
An unchanged passive-observer test requires the exact existing enumerable
command keys. A local four-whole-module baseline reproduces that concrete
incompatibility: all116 earlier cases and30 passive cases pass, while the
command-key assertion fails. This identifies a real missed caller contract,
not proof of the hosted run's sole failing assertion; no raw frontend or
backend job log was inspected.

Both drivers now use an own non-enumerable getter, leaving every existing test
and assertion unchanged. The same147 cases pass, with52 expected guard denials
and clean source/Node/system/resource closure. Physical release is
`2026-10-18T20:48:10.948165Z`. The passive31 module alone retains its previously
qualified native filesystem-write flag for its genuine owned symlink test;
the unchanged JavaScript guard still checks owned paths. This is trusted,
source-pinned testing, not hostile-code filesystem isolation.

An initial147 run records121 passes and26 failures: one command-key failure
plus25 passive-owner failures because its scratch directory was outside
`/tmp`. The existing observer explicitly requires a private local `/tmp`
owner. Only the fresh runtime binding was corrected before the controlled
146-pass/1-fail baseline; no product, test, guard or permission was changed.
All three actual ledgers are preserved separately. The new147 pass does not
replace the still-required full `npm test` and native-browser results.

Verified immutable evidence is stored under
`diagnostics/ci/NODE116-BASELINE-109P7F-CLOSED-20261018-1JGZJMsb` and
`diagnostics/ci/NODE116-CANDIDATE-PASS-CLOSED-20261018-zEP1gPe0` in the project
archive. No protected synthetic trace or backend raw log was used.
