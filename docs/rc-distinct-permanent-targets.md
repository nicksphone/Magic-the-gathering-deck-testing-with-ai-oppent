# Human Exact-Two Permanent Targets

The hand controls use the server's permanent candidates when no creature list is
offered. The same candidates drive the selectors and completeness checks. Empty,
duplicate, and unoffered distinct-target drafts cannot be cast; editing clears a
stale scalar target, preserves selection order, and never chooses automatically.
Creature-instance spells still allow repeated recipients. Counter and modifier
labels are shown only when the server actually supplies those effects.

Public stack previews expose the announced pair for `exile_return_batch`,
including real copied spells. Private payloads and incarnation references remain
outside the public view. Payment, legality, copy choices, and resolution rules
are unchanged.

Regression coverage uses existing full canonical fixtures, both seats, actual
public views, component callbacks, checked engine payment/resolution, and
snapshot restoration. The new App/API browser scenario selects a creature and
land, reloads a paid stack, resolves it, and reloads the returned battlefield;
normal and foreign-owner starting positions are exercised separately.

Validation commands:

```sh
MTG_TEST_PYTHON=/path/to/python npm test
npm run lint
npm run build
```

The unchanged five-module backend neighborhood plus the new copied-stack module
passed all 218 cases in an owned local SQL checkout. Browser CI includes the new
scenario alongside the original distinct-counter and repeated-creature flows.
The held-response browser test now continues CORS preflights and explicitly holds
the real successful POST, retaining its original pending-control and exactly-once
assertions. The dropped-response test records method/status-only diagnostics on
failure without relaxing its expectations.

These checks are component evidence, not an arbitrary-rules, expert-AI, or full
release certificate. Historical failed harness attempts are retained privately;
the protected archived game trace remains private.
