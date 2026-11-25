# Opt-in interactive AI search limits

Autoplay uses the existing search policy unless one of these environment
variables is set in the backend process:

- `MTG_AI_INTERACTIVE_NODES` limits instrumented planning copies and
  simulated actions per decision. Use a nonnegative integer.
- `MTG_AI_INTERACTIVE_MS` sets a per-decision elapsed-time budget in
  milliseconds. Use a nonnegative integer.

Both limits can be set together. The first exhausted limit ends speculative
work. The deadline is cooperative. A single rules operation, legal offer
generation, or validating the fallback can take additional time. The
limits apply per decision, so an autoplay request containing multiple
ticks can take longer.

A completed search retains its original decision. After exhaustion, the
app tries one checked offer, preferring pass priority when offered. If the
offer cannot be checked on the first tick, the endpoint returns retryable
503 with code `ai_decision_budget_exhausted` and rolls back the request
revision and idempotency receipt. If earlier ticks already did work, autoplay
commits those ticks and stops before the current action. Mandatory choices
can require more budget on a later request.
This policy can change play quality and is separate from the exact Master
policy used by the strength harness.
