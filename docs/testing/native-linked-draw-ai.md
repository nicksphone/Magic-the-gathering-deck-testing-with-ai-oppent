# Native Linked Damage And Targeted Draw

These are modifications of the Forge Team/Card-Forge AI, not a replacement
engine or learned model authored from scratch. Upstream revision
`61e9442c433711a82258daca3236f936a1d6f70e`, complete source pre/postimages,
copyright headers and GPL-3.0-or-later notices are retained beside each patch.
The live Python opponent and model weights are unchanged.

## Linked Damage

The [unchanged audit](../../tools/engine_evaluation/forge/native-ai/linked-damage-lethal-audit/RESULTS.md)
found four missed wins: the native policy selected the opposing player for
Searing Blaze, then rejected its required creature target because that creature
would survive. Separate paid legal executions demonstrated native wins; those
manual controls were not counted as successful AI decisions.

The [one-source correction](../../tools/engine_evaluation/forge/native-ai/linked-damage-lethal-policy/RESULTS.md)
adds a fallback only after ordinary linked-child targeting fails. It requires
a pure, equal-amount player-damage/required-opposing-creature-damage chain with
terminal DamageResolve and a lethal native player forecast. Ordinary target
legality, MustTarget, cost/payment and cast-backlash checks remain. It does not
set a global mandatory flag, recall the root play policy or cache a decision.
Unknown/optional/conditional/extra-effect, X, copied and activated forms are
outside that fallback. The extra native forecast can evaluate authored
replacement expressions; universal RNG-history parity is not claimed.

The same 32 check-method cases gave **28 passes/four strict failures** before
the patch and **32 passes** afterward, including all four actual paid native
wins and 20 preservation controls. A prior natural-game pass remains a review
candidate, not a retrospectively proven occurrence of this exact failure.

## Targeted Draw

The [initial correction](../../tools/engine_evaluation/forge/native-ai/targeted-draw-policy/README.md)
accepts an opponent deliberately selected by native targetAI instead of
contradicting that decision with a zero rating. It also fixes the equality
boundary: drawing exactly the library size is not an immediate decking loss.
The initial 22 AI checks passed, but a separate replacement audit then found
four failures in that draft. It was not promoted as a finished strategy.

The [safety follow-up](../../tools/engine_evaluation/forge/native-ai/targeted-draw-safety-policy/DrawAi.patch)
checks whether the opponent may draw the library size plus one, and detects
known active Draw replacements containing a native WinsGame instruction.
Visibility is checked before reading replacement bodies. Suppression, active
zones and affected-player validity remain native. Empty-library conditions
are not incorrectly evaluated against the earlier nonempty library. This is
a conservative structural guard, not complete conditional/replacement analysis.

On the corrected source, **34 AI checks** pass: the original 12, ten equality/
funding/safety cases, eight replacement cases, and four positive controls for
Teferi's Ageless Insight and genuine Jace departure. Four separate explicit
opponent-target executions demonstrate replacement outcomes; they are not AI
passes. The engine supplies actual targets, payments, stack resolution and
outcomes in the AI checks. No named-card policy branch or forced cast was added.

## Combined Runtime

The parent independently rebuilt both source/class pairs byte-identically and
composed one exact **seven-source/nine-class** prefix. On that single prefix,
the 32 linked-damage and 34 draw checks pass, together with four separate draw
execution controls, the existing 70 pressure/safety checks, 38 knowledge checks,
48 boundary checks and four synthetic empty-source checks. Source and payload
pins match before/after. These are distinct method cohorts, not a game count.
The profile boundary's **24 synthetic tests** retain all previous 22 bodies.

Composition: `8e9384dbc01527a853e5e22caabce51e126cc2fb83c8e627dbf1bd6893169685`.
Operator profile: `5fb2cfa365ee5cc7d110a1042a05c4e08a6dc1cb9be182bcf9e036b4d591ca26`.
It does not reuse an old save/build identity or change the default service.

An earlier draw-only Control/Ramp UI attempt stopped at the unchanged worker's
30-turn cap, after 369 accepted rendered answers. Native stderr confirms
`turn_budget`; the frontend correctly rendered failure while the driver was
waiting for an older question. There was no completed game or winner. All 25
observed processes ended; both local databases closed with integrity/fuser
checks, and all 4,646 clean-app files and 29 private inputs stayed unchanged.
That failed attempt is retained separately, not relabelled as qualification.

One fresh built-UI Burn/Ramp game on the final combined profile completed with
**142 accepted rendered-control answers and 142 native starts/returns**, in
**82.296 seconds**. Burn won naturally on turn 10 against human-side Ramp in the
second seat. The unchanged automated human-side picker is not expert play.
This different game is not a matched speedup or strategic superiority result.
Reload, wrong-capability/stale/duplicate requests, four root-purity checks and
actor-view privacy checks passed. Independent verification checked all nine
actual loaded override origins, seven source hashes, 33 base resources and
29 loaded unoverridden origins. All 4,648 tracked clean-app files and 29 private
inputs stayed unchanged; all 22 observed processes ended and the local database
closed with integrity/fuser checks. New-profile cold-save compatibility is not
qualified by this game.

Broader natural-game decision quality, replacement interactions, hidden-input
fairness, durable saves/BO3, practical control-game limits and live adoption
remain open. Private hands, RNG/game streams and browser evidence remain in
private NFS archives, not public fixtures. Isolated passing checks do not close
AI release acceptance.
