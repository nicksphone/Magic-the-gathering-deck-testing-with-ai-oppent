# Native Pending Life-Gain Denial

## Reproduced Defect

Review of the declared six-archetype baseline found funded Skullcrack held while
opposing Sheoldred gain triggers resolved. A separate complete-card native
reproduction confirmed both-seat refusals. Manual controls paid the actual 1R,
dealt three damage and prevented the pending gain of two, without ending the game.
Those controls are rules evidence, not successful AI choices.

The `Effect/Burn` root delegated to its damage child. That child treated the
nonlethal damage as ordinary burn to hold for later, missing the root's useful
gain prevention now. The correction opens only that typed, currently beneficial
response in the shared player-target preference and its surrounding timing gate.

## Correction And Boundaries

The complete supported root/static/child chain must match an immediate damage
effect with applicable life-gain prevention and default or explicit end-of-turn
duration. The actual pending gain must be positive, beneficial to the sole
opponent and have that opponent as its actual recipient. Visibility precedes
root, child, wrapper, trigger and unwrapped-body inspection. Native damage
prediction, targeting, avoidance, full-chain conditions and payment remain in
place. There is no card-name lookup, target injection or forced mandatory
drawback path. Unknown/conditional bodies, own-only gain, already-prevented or
harmful gain do not receive the new exception.

This does not cover every gain source, lifelink/combat situation, stack sequence,
copied spell or hidden-history interaction. It is not a full-hand search or a
trained policy. No live application profile was switched.

## Executed Evidence

- Unchanged original six-pose source: baseline has two funded refusals; final
  candidate takes both through ordinary selection, native targets, real payment
  and resolution. Unfunded refusals remain. Two no-pending cases are observations,
  not additional expert-play successes.
- Unchanged preservation ten: eight refusals and two AI-paid lethal wins pass on
  both baseline and final candidate.
- Existing pressure70, knowledge38 and actor/stack/LKI boundary48: all 156 checks
  pass across eight serial native JVMs, exit 0, 185.431 seconds. These are not 156
  games or mutually independent tactical scenarios.
- Four fresh matched Burn/Dimir games complete with zero native errors, no caps
  or skips. Decks, seat orders, seeds and probe source match baseline cases00-03;
  only the candidate/profile and owned output paths change. Execution totals
  107.329 seconds, not a causal performance comparison.
- In completed natural cases00/02, Burn now casts Skullcrack and Control legally
  counters it. Control still wins all four games; no measured win-rate gain is
  claimed. More extensive strategy and holdout comparisons remain open.

Final content ID: `f4c8d41f6de9016c194551b2bfcedad9f61ddf2fdf556eb88e16a6618d40dfb5`.
The isolated operator profile is
`f784fbbee9d64745cf4fa077dcc8080033ae4306b97581456734239c7d59d94c`.
All thirteen source/twenty-one class pins and 59,971 base resources match before
and after the final gates. The earlier compiled revision's sixteen green cases
are retained separately; they are not relabelled as final visibility-qualified
results. The initial Java type error and preflight failures are preserved too.

The launcher uses unchanged native guards with Python `-S`; SQL/protected
noncanary attempts are checked over complete logs. Denied socket attempts are
recorded, so quiet I/O is not claimed. Owned process closure and byte-verified
private archives are recorded separately from gameplay assertions.

## Reuse And Delivery

[Source delta, unchanged fixtures, full programs and pins](../../tools/engine_evaluation/forge/native-ai/gain-denial/README.md)
are public source artifacts. Forge Team/Card-Forge credit and GPL notices are
retained in the package and the patch itself. Rebuild only over its exact
qualified parent prefix using the existing isolated native harness and profile
composer. This is not automatic deployment or universal save compatibility.
