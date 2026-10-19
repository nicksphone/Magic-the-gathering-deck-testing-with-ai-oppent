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

## Separate Sandboxed Chrome And Brave Result

The existing native workflow is subsequently dispatched once on the same exact
`cdba5196` source: run `38835461011`, attempt 1. Brave job `116763479412`
completes successfully at 01:58:46 UTC; Chrome job `116763479869` at
01:59:03 UTC on October 16. Each vendor's own log independently contains all
45 ordered launcher stages and 501 PASS banners, rather than inheriting the
generic job's counts. Original program bounds and scenario assertions remain.

Both vendors retain `MTG_BROWSER_NO_SANDBOX=0`, pass actual binary/runtime
identity and DOM preflight, and report an enabled expected renderer sandbox.
Brave reports the SUID first layer; Chrome reports Namespace, with PID/network
namespaces and seccomp checks. This is browser-reported status, not per-renderer
kernel attestation. Each preflight child exits zero, and each enclosing service
reports exit zero with its control group empty. No local security settings or
browser installations are changed by this remote qualification.

Only the exact two native jobs' logs and allowlisted metadata artifacts are
retrieved. Each artifact contains solely bounded `preflight.json` and
`lifecycle.json`. Parent reconciliation matches their hashes and all five
declared source bindings to exact published Git blobs. Private immutable
evidence is under
`diagnostics/ci/native-cdba-metadata-qualified-20261016-SQlkDGQC/`; report SHA-256:
`279d7d053fe51e7534550adda4396ccaebb7e0c3268cfabed52255119173e2cb`.

This qualifies the existing full native Chrome/Brave browser cohort on cdba,
not Firefox, new `uiInput` feature branches, the later fixture-only source,
whole-backend CI, LAN/trust or the full release. Prior intermittent failure
causes remain unknown. The generic job's no-sandbox result stays separate.
