# Accepted-Response Drop Metadata

The existing `recoverDroppedResponse` failure path emits one bounded
`Browser response drop failure` annotation from data it already collected.
No request, retry, recovery action, deadline or browser setting is added.
The original diagnostic stream and original thrown error remain unchanged.

The closed projection contains observed/drop booleans, retained response
status/continuation counts, omitted/pending counters and canonical-read
availability with a nullable revision. It retains at most 16 response rows.
It exports no URLs, IDs, card names, headers, bodies, error text or stacks.
Invalid operands and sink failures suppress the annotation, not the primary
failure. Missing observations never become an invented revision zero.

Counts describe the retained collector slice, not all traffic or a causal join.
An OPTIONS continuation does not establish POST delivery or an accepted drop.
Even an acknowledged drop and an available canonical revision do not identify
the cause of a separate browser failure. A source hint remains unverified.

## Observed Component Evidence

- Whole NEW projection/caller module: 12 missing-feature failures before,
  then 12 ordinary passes after.
- Three whole existing recovery/causal/request-signal modules: 131 ordinary
  passes after the test-only bindings below; no skipped cases or assertions.
- Whole existing failure-wrapper module: 24 ordinary passes using its genuine
  fixed inert Bash/Node children. This is not a child-denied or OS-sandbox role.
- One npm-schedule contract: failure before wiring, pass after. The original
  17 native-browser module operands retain their order; NEW12 is appended once.

The Node component fence is a trusted API/file fence, not an adversarial OS
sandbox. Recorded source bytes were equal across each execution and owned
groups closed. These are separate gates, not one combined test invocation.

Two existing VM fixtures previously extracted the real recovery function but
omitted its new imported reporter. Their 40 failed cases suppressed the legacy
diagnostic inside the existing try/catch. The separate test-only correction
binds the actual reporter body and real projector with a captured write sink;
all original test/assertion lines remain. No production no-op fallback is used.

Dependencies, lockfiles, the top-level npm hook, application behavior and the
original source-hint schema remain unchanged. Hosted default npm execution and
actual browser outcomes require their own observations. This instrumentation
does not fix or qualify Chrome, Brave, Firefox or the full release.
