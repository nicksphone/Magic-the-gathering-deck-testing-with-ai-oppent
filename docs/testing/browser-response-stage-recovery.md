# Browser Response-Stage Recovery

The browser recovery suites now intercept the response directly, after the
server has accepted the request and before the response body is delivered.
Only four `Fetch.enable` stage literals change across the existing lost-action,
held-action and initial/resumed match-start scenarios. This removes reliance on
the experimental per-request interception override; it does not establish why
the earlier native requests aborted. See the
[official Fetch protocol](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Fetch.pdl).

The original clicks, payloads, idempotency keys, genuine request-body capture,
mutation/revision assertions, deadlines, callback drains and cleanup remain.
Four mechanism-specific expected stage operands and three test titles are
explicitly adapted. All other assertions and request-phase defensive controls
remain; the shared continuation helper and diagnostic `current-request` mode
are unchanged. Application, API, engine and browser adapters do not change.

The four whole protocol modules pass all 129 cases. The preceding 125-pass,
four-literal-failure run and earlier 67-pass/one-failure run remain separate
ledgers. Pre-import I/O controls admit no child, socket, SQL, provider or real
browser operation; source/dependency/runtime inventories remain equal.

This is protocol qualification, not native-browser acceptance. The Firefox
adapter already has a direct response-stage path, but actual request-body
availability and all original Chrome, Brave and Firefox recovery scenarios
still require native qualification. The hosted `7fddf697` browser failure is
the held-response assertion, with an unknown abort cause. Its frontend job
separately passes build, lint and the full frontend unit command after the
bounded replay-capture correction.
