# Replacement-aware optional draw forecasting

## Checklist

- [x] Reuse shared draw/gain-life replacement selection and draw restrictions.
- [x] Forecast from public library size without reading future card identities.
- [x] Keep authoritative state, counters, log and RNG unchanged.
- [x] Compare canonical single/multiple draw doublers, own-draw-step exceptions
  and draw caps against actual effect resolution for both seats.
- [x] Test actual optional-cost choices across Casual, Strong and Master.
- [x] Focused gate: 189 passed, including 68 new forecast checks.
- [x] Frontend lint, contract tests and production build pass.
- [x] Complete browser suite, including restart and natural BO3 flows.
- [x] Actual decision comparison against published `e50092a`: twelve scenarios
  across both seats and all difficulties; unsafe kicked draws fall from six to
  zero while all six safe kicked draws remain selected. This is bounded decision
  evidence, not a measured win-rate improvement.
- [x] Twelve seat-balanced BO1 replay samples, each executed twice: zero
  reported anomalies, timeouts or determinism failures, 519.238 seconds.
- [x] Full isolated backend suite: 4,081 passed, 364 deprecation warnings,
  633.68 seconds. Tests reuse installed dependencies; this is not fresh-install evidence.

## Contract

`forecast_draw_count` reuses the engine's deterministic default replacement order
instead of counting nominal instructions. Each replaced draw is re-evaluated
separately, tracking used replacement sources and successful draw history. Thus
multiple doublers compound without reapplying the same source to its own event;
draw limits can stop subsequent substituted draws, and the first-draw exception
applies only in that player's own draw step.

The lightweight projection owns its log and draw-history dictionaries. It never
pops a library, reads a future card identity, emits triggers, advances the RNG or
changes the original match. It stops at the first projected empty-library attempt
to bound amplification. Normal/kicked payoffs compare separate projected counts,
and a projected failed draw strongly discourages buying the optional branch.

Canonical Scryfall fixtures preserve Thought Reflection, Teferi's Ageless Insight,
Spirit of the Labyrinth and Narset, Parter of Veils. Both-seat cases use actual
Citanul Woodreaders cost choices, not modified tournament decks. A test library
containing deliberately unreadable identifiers verifies count-only inspection;
those identifiers are not invented playable cards.

## Known Limitations and Next Upgrades

This forecast follows the existing default replacement order, not an optimization
over affected-player choices. Optional dredge, unknown replacement grammar,
downstream draw triggers, changing battlefield state and alternate win conditions
are not simulated. Life-conversion paths reuse existing replacements but do not
value resulting life or certify all interacting life-trigger chains. The consumer
is optional kicker valuation, not all AI draw decisions or expert resource
planning. Passing fixtures and a small replay matrix do not establish balance,
complete card correctness, fresh-install reproducibility or deferred UI ergonomics.

Verified source, raw canonical responses, test logs and baseline/current decision evidence
are archived on RCHFiles at `diagnostics/ai-draw-forecast/20261003T122413Z/`.
