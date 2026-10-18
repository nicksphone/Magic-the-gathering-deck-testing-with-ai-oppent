# Browser Fetch Filter Capability

The main and release-owned browser drivers expose a read-only,
per-page `supportsFetchResourceTypeFilter` capability. CDP pages return `true`;
pages using the bound Firefox transport return `false`. This is a transport
capability, not a user-agent, browser-version or input-device inference.

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

Verified immutable evidence is stored under
`diagnostics/ci/NODE116-BASELINE-109P7F-CLOSED-20261018-1JGZJMsb` and
`diagnostics/ci/NODE116-CANDIDATE-PASS-CLOSED-20261018-zEP1gPe0` in the project
archive. No protected synthetic trace or backend raw log was used.
