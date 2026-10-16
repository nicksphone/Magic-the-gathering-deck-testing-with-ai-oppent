# Exact cdba Browser CI Acceptance

Hosted run `38830866267`, attempt 1, browser job `116749084579`, succeeds on
`cdba5196d90b984995718c96a5e2ea8326600b10`. It completes at
2026-10-16 01:09:15 UTC. The frontend job also succeeds; the backend job is
still executing at this review. This is not a passing whole-workflow claim.

## Executed Scope

Independent reconciliation matches all 45 ordered stage headers to the
unchanged zero-argument `frontend/tests/run-browser-ci.sh` launcher. Its SHA-256
is `b2b0239bc5a2f0353524681e52aa3fbfbc45bccf65e1b8336b848079f86524d0`.
The actual log contains 501 PASS markers. They are banners, not assertion or
program counts. The source roster has 68 top-level entries: 67 direct Node
invocations and Officer's shell launcher. Including its two modes gives
69 entrypoint invocations across 66 distinct MJS files.

All 919 original static scenario assertion call sites remain AST-identical.
This proves their source preservation, not execution of every conditional
branch. The new diagnostic subscription/cleanup checks are separate. Frontend
application source, launcher, workflow, scenario assertions, waits and retry
limits are unchanged by the diagnostic addition. No failure-history JSON is
emitted during this successful run.

## Boundaries

This configured generic CI job retains its existing explicit no-sandbox mode.
It is not secure native-vendor, Firefox, LAN/trust, deployment, AI-strength or
whole-backend acceptance. Native Firefox `uiInput` flows configured here: zero.
The separate existing Linux Chrome/Brave workflow is required for sandboxed
vendor evidence; it must not inherit this job's result.

The two earlier browser failures remain historical observations with unknown
causes. Passing with additional read-only diagnostics does not establish that
either root cause was repaired or that an intermittent failure cannot recur.

Only this exact browser job log was retrieved, privately; no backend log or
protected game trace was downloaded. Immutable evidence is under
`diagnostics/ci/browser-cdba-success-log-qualified-20261016-pnU48nQu/` in the
project NFS archive. Log SHA-256:
`7f5e2bec3fd68fced630209d0052f01ec1675953b9c46717ba88992176795eb5`.
Verified report SHA-256:
`27a5567b55d095828ec594561946c6ec4492637afd2ae746363951182289d0c6`.
