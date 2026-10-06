# Natural Friendly-Removal Boundary Audit

Diagnostics and tests only, pinned to the sealed natural-audit source
`19a925291364f08547f06dd55fc8344e14fe8c6f`. No AI product, engine, card,
Oracle, seed, search-budget, API or training changes. The newer source pin
is unnecessary: this reconstruction uses the actual recorded source and
restores the actor's exact configuration and transient pass-memory.

## Exact Witness

The private synthetic receipt is `pair1-seat1-seed1702`, turn 11 end step,
decision tick 303. Tempo/master/opponent Control casts Unholy Heat on its
own front Delver while the opponent's Memory Deluge is pending and no
opposing creature exists. The recorded checked declaration is reproduced.
The original applications at ticks 303-305 are replayed without rewriting
cards, Oracle, library order, RNG or choices. Delver and Heat go to the
graveyard, the opponent's Deluge remains on the stack, and the actor gains
no life or death payoff. Existing board evaluation changes by -3.0005.

Comparison of applied snapshots excludes ONLY historical `log`: the original
collector appended `AI TRACE` diagnostic strings before checked application.
Every other serialized field, including complete cards and RNG, must match.
Original receipt bytes remain immutable; this is comparison normalization,
not mutation of the supplied snapshot or policy input.

## Measured Decision Boundary

The actual private-view ranker assigns Heat 9.6065, pass 5.2815, and the
offered mana activations 7.4065. These are captured return values from the
existing scorer, not estimated scores or overridden rankings. Normal ranker
search settings are unchanged. The actual response path bypasses ranking:
`_forced_stack_interaction` observes threat 4.0 and assigns Heat 2.5 merely
because its Oracle matches generic removal/damage text. Materialization
selects the sole friendly creature. Neither operation establishes that the
cast answers Deluge or improves the position.

The actual chooser calls `friendly_destruction_profit` zero times. Direct
raw and private-view probes return unknown, not profitable: settling the
unrelated opponent's inspection needs an unavailable private continuation.
That is conservative projection behavior, not a false-positive profit result.
The generic `unproductive_destroy_targets` gate handles pure destruction;
damage text is excluded. `_burn_has_only_friendly_targets` and damage-target
filtering cover narrower any-target forms, not this actual creature-or-
planeswalker conditional damage declaration.

Separate explicit canonical fixtures reproduce harmful self-targeting in
both seats and response/proactive windows. In proactive fixtures the profit
helper returns False, but the chosen action still targets the friendly victim,
with reason `Break pass-loop by selecting proactive legal action`. Therefore
repairing only the forced-response branch would leave a shared materialization
gap. Those fixture decisions are diagnostic observations, not claimed passing
policy correctness. The sole policy correctness regression remains an
ordinary RED preventing the demonstrated original losing trade.

## Positive Controls And Limits

Sixteen beneficial-removal controls use two existing authentic families:
Bastion of Remembrance and Blood Artist, each across both seats, Tempo and
Aristocrats, response and proactive windows. Their declared friendly damage
is legal, materializes without rejection, has a positive resolved-profit
forecast, and actually wins through the canonical death effects. Four opposing-
target controls materialize the opponent, resolve the damage and improve the
actor's board evaluation. No blanket own-target ban is acceptable.

The existing complete fixtures `self_removal.json` and `recurring_engines.json`
are reused. Heat, Delver and Deluge controls copy complete canonical instances
from the immutable synthetic witness; printed characteristics and faces are
not edited. Control fixtures have explicit mana/life/zone/priority setup and
are NOT claims of reconstructed natural games. No Doomed Traveler fixture
was present, so that suggested example is not fabricated or certified.

Initial controls incorrectly required immediate self-removal even when the
agent forecast a winning attack. Those four assertion failures and the initial
diagnostic-log comparison failure are preserved. Corrected controls require
that beneficial friendly removal remains a valid winning option, rather than
forcing it over a different winning line. Actual chooser decisions are retained.

Both private libraries are opaque to policy; the opponent starting deck is
absent and opponent hand is masked. Full historical synthetic state is private
diagnostic evidence, not extra policy knowledge. No full-clause, tournament-
dataset, expert-policy or global performance certification is made.

## Commands

Use an isolated checkout of the declared source and matching external Python,
with the verified raw receipt copied to local evidence as
`sealed-self-removal-witness.json`:

```bash
export PYTHONPATH="$PWD/backend"
export MTG_HEAT_WITNESS=/local/evidence/sealed-self-removal-witness.json
export MTG_HEAT_REPORT=/local/evidence/rank-diagnostic.json
cd backend
"$MTG_TEST_PYTHON" -m pytest -q tests/test_natural_heat_target_audit.py
```

The correct baseline result is one ordinary failure, not an xfail or a green
policy gate. The receipt and report directories must be private and local.
No SQLite database is needed. Do not run this against parent/main/live.

## Proposed Repair Scope, Not Implemented

Candidate shared seam: generic announced-action target materialization in
`AIAgent._materialize_action_without_resources`, reusing checked engine effects
and proven public consequences. Response scoring must require a useful answer,
not reward arbitrary damage while a threatening stack object exists. Pass-loop
fallbacks must not recover the same demonstrated losing declaration. Reuse
pending-effect projection rather than deriving new damage rules or card-name
exceptions. Unknown opponent continuations must remain unknown, while an
independently proven harmful immediate own-object consequence may be compared
with holding; retain valid beneficial removal, replacements and death wins.

Any product change requires separate authorization and must turn the original
ordinary RED green without weakening the positive controls or introducing
search caps. The observed standalone BO3 latency and exit139 are separate
diagnostic facts, not explained by this policy finding.
