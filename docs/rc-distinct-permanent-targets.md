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

## Distinct-Target Response Boundary

The shared legal-move/cost-option parser validates distinct counts within the
existing ordered-control budget (2..250), supplied candidate IDs/names and
per-pool uniqueness, mutually exclusive instance metadata, and paired counter
amount/type fields. Counter amounts must match the count and be nonnegative
integers. Extra candidate metadata is preserved. Empty or insufficient candidate
pools remain valid responses, leaving the action incomplete rather than choosing
recipients or pretending it is castable.

The regression rejects 58 malformed move/cost-specific views and retains four
positive response shapes in both locations. The full frontend test command, lint and build pass;
the actual Ghostly, Incremental Growth and Agony Warp browser programs pass on
this follow-up. The complete browser result above belongs to `d727e0d1`, not an
implicit full-suite certificate for every later source revision.
