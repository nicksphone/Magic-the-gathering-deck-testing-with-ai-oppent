# Phase-Aware Strategic Combat Leaves

Base: immutable 55ebc8c6. Product: ai/agent.py only, two strategic scoring
methods and one private completion guard. Search depth and attack selection policy
are unchanged. An actual announced action is executed before any projection.

Complete only already-declared combat with an empty stack, no mechanic/replacement/
trigger-order continuation, no defending hand/graveyard/exile resources, and a
battlefield consisting only of effective noncreature basic lands. Own activated,
unsupported combat, and combat-triggered sources are unknown. Both players' offered
legal responses must contain no effectful action. The existing projector then
finishes actual combat through damage/end-combat (or winner). It cannot silently
pass an offered spell or activation. Inputs are masked by decision_view.

Unknown positions retain the existing strategic planner. Blockers, crackback,
nonbasic lands, mana-creature opportunity costs, and effectful responses are not
certified response-free. This conservative boundary intentionally leaves many
ordinary natural positions unresolved, including opposing nonempty graveyards.
It is not a global combat oracle or a natural-game strength certificate.

Completed positions use the existing strategic score, including real damage,
winner and readiness, once. At the depth cutoff only the positional component
is replaced; other accumulated terms remain. No flat attack/damage bonus or
additional search depth is used. Unannounced attacker-choice states are not
finished by the completion helper.

The original 38 witnesses stay byte-identical. Before: 16 pass/22 fail. After:
32 pass/6 fail: all 20 desired legal attack cases pass, two Mutavault animation
availability failures remain, and four old-pass tapped-basic characterizations
are superseded. Four separate acceptance tests establish the new intended result
without changing those historical assertions. Never summarize the unchanged
original module as fully green. Original two Mutavault failures are unrelated
engine limits, not bypassed by this product.

New test_strategic_combat_leaf.py: 26 ordinary tests. Four neighboring modules
plus the new module: 108 pass. Three information/strategic modules: 181 pass.
No skipped, xfailed or deselected cases. Real checked Bolt and Counterspell
payments preserve both response windows. Resource reservation and real paid
postcombat deployments are covered by the whole postcombat-mana module.
