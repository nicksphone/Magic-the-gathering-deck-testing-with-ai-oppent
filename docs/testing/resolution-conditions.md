# Resolution-Time Conditional Instructions

The engine recognizes two bounded whole-instruction families:

- Destroy a target creature below a normal mana-value threshold, using an
  alternate threshold if a permanent left the controller's battlefield this turn.
- Deal a normal amount to a target creature or planeswalker, using an alternate
  amount if the controller's graveyard contains at least four distinct card types.

Canonical Fatal Push and Unholy Heat fixtures reproduce the original failures.
The conditions are evaluated at resolution, not locked at casting. Legal target
selection is distinct from whether the resolved instruction affects that target.
Damage alternatives do not add together. Target incarnation references prevent
effects from following objects through zone changes; copies capture their own
retargeted references. Shared damage prevention/replacement and destruction rules
remain responsible for the resulting instruction.

Nearby unsupported clauses are reported explicitly. This is not general support
for every revolt, delirium or intervening-if ability.

Golden tests cover both seats, changing conditions, snapshots, real stack copies,
retargeting, zone changes, indestructible, damage replacement and AI removal hints.
Unchanged canonical records and provenance are in
`backend/tests/fixtures/resolution_conditions/`; run
`backend/tests/test_resolution_conditions.py` with the backend test suite.
