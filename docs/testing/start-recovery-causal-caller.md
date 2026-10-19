# Match Start Recovery Causal Caller

This diagnostic-only candidate follows qualification commit `e4d0c77e`.
Its hosted browser job failed before observing any POST interception pause:
the genuine OPTIONS request completed, then two POST requests were canceled.
The intentional accepted-response drop was never reached. The same browser
source passed in the separate `8aeba8e6` and `67ed7158` jobs; that does not
identify the cancellation cause or make the failing job pass.

The recovery caller now enables the existing bounded causal collector and
observes the send/acknowledgment boundary of its original Fetch controls.
Commands, parameters, interception patterns, deadlines, response-drop logic,
idempotency assertions and application code are unchanged. Failed commands
retain their original error; no successful acknowledgment is invented.
The collector retains only bounded categories and local ordinals, not raw
request, context, frame, target or session identifiers. Signal observations
remain explicitly unjoined to native network IDs.

Four whole pure protocol/caller modules execute 54 checks. The initial paired
53-case declaration has 51 passes and two new wiring failures against the
original caller, then 53 passes with the wiring. Independent review finds two
legacy control sites still bypassing observation: the added nine-site inventory
check fails before their correction. The final whole declaration passes all
54 checks without skips or cancellation. An initial zero-test CLI
file-discovery failure and a new test's cross-realm comparison error are retained
separately; neither is an application defect or a passing declaration.

These are public mocked-protocol unit checks, not real browser, HTTP, SQL,
vendor, whole-backend or Phase 1 acceptance. They use the existing serialized
native coordination lock and a fresh source-only archive. Node's permission
mode allows source reads but no filesystem writes, child, worker or addon
permissions. There is no claim of an OS-level network fence. No private input,
trace, credential, application dependency or existing worker is consumed.

The cancellation remains unresolved. A future real browser result must be
evaluated as observed; this change adds evidence, not a retry or workaround.
