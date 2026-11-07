# Native Linked-Damage Pressure

This is a local modification of **Forge Team/Card-Forge's native AI**, not a
new engine or independently authored card database. The upstream implementation
and complete canonical card programs are retained under their supplied
GPL-3.0-or-later notices; see `NOTICE` and `LICENSE`.

## Change

The existing damage heuristic can reject a player-damage spell because its
required, controller-linked creature target survives that one spell. The new
root fallback admits positive player/creature pressure after combat, while
the child decision completes the same recognised effect safely. A second
spell is chosen normally after resolution: there is no forced action, named
card heuristic, altered Oracle or new two-card planner.

The complete supported shape is a single player/planeswalker-targeted damage
spell, one equally sized controller-linked creature-damage child, and the
native DamageMap resolution tail. Unknown body/condition/target shapes are
not reinterpreted. The root fallback requires an empty stack on the actor's
MAIN2/end step; an already-admitted ordinary native root keeps its timing.

Native legal-target, must-target, effective-condition, best-target and complete
payment/Ward checks remain in use. Nonlethal completion excludes the checked
damage/targeting-reaction hazards rather than letting a later kill-only
selector silently replace the safe choice. The earlier lethal completion is
retained. This is bounded tactical improvement, not general reaction search.

## Reproduction And Identity

`linked-pressure.patch` is **incremental over C10/commit01e3bc69**, not a patch
for pristine upstream Forge. `SOURCE-PINS.json` identifies the exact one-file
pre/postimages. Compile the changed `DamageDealAi` with the pinned upstream
classpath, inherit the other13 sources/22 classes, and derive a fresh schema11
runtime profile using `../runtime_profile.py` and `PAYLOAD.json`. Never relabel
an existing save or change a live/default runtime implicitly.

The five Java probes and complete canonical text programs are reproducible
trusted-pose tests, not natural games or expert training labels. Run them
against the full pinned native runtime using the existing guarded evaluation
infrastructure. `QUALIFICATION.json` records the separately executed cohorts,
source/class identities and historical rejected drafts. Raw actor/game traces
remain in the private archive, not public fixtures.

Completion of games does not prove strategic strength. Arbitrary compound
effects, full reaction forecasting, all matchups, useful learned-policy
generalisation and application/UI adoption remain separate acceptance work.
