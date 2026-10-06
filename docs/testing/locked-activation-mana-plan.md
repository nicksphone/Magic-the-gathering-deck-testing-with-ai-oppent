# Locked Activation Mana Plans

## Failure And Scope

The frozen composed candidate reproduced both unchanged Logbook integration
failures. With five real engine-created Treasures the selected ability costs
generic zero plus U1. The existing requirements were already locked correctly
before mana-source consumption: there was no missing ability-index forwarding,
late discount recomputation or additional-cost relaxation to fix.

The shared physical planner explored irrelevant Treasure colors before the
outstanding U symbol. Its first feasible fallback converted all five Treasures;
execution's resource-score comparison retained that plan on a tie. The archived
trace observed W4 remaining after payment (the reported pool U4 was not reproduced
in this frozen source). The exact colored requirement remained U1 throughout.

Only rules_engine/mana.py is changed. No engine, costs, AI, API, parser or Escape
hook changes. Both query and application use the shared planner. Requirements,
payment validation, full post-mana additional costs and reservations are unchanged.

## Narrow Change

Prioritize existing candidate output bundles that serve currently outstanding
colored symbols in the locked requirement, using the actual payment context and
existing output_bundles function. Preserve every fallback: an off-color activation
may fund a later filter prerequisite. No output pruning or new search cutoff.
If the existing pool already covers the whole requirement, return its zero-step
plan rather than considering unnecessary physical mana activations.

This is deterministic payment ordering, not an AI-search change, a general
minimum-resource optimizer or permission to accept invalid costs. Indivisible
multi-mana outputs can legitimately leave surplus; this fix does not forbid that.
Printed/live cost views may change after paying, but do not replace the locked
requirements used by the real payment path.

## Canonical Controls

Tests reuse unchanged canonical fixtures: Tamiyo's Logbook (other artifacts),
Deepwood Denizen (+1/+1 counters), and Azure Mage with Training Grounds/Heartstone
(external reductions with floors). All Treasures come from named_artifact_token
and real create_token. No Oracle text edits, fabricated source cards or scores.

Both seats: unfunded consumes one Treasure and leaves pool zero/four Treasures;
prefunded consumes none and leaves pool zero/five Treasures. The tests capture
actual planner requirements and steps, compare complete checked snapshots and
serialized replay, preserve root/RNG, and resolve the real draw effect.

Command-only HTTP requests test malformed-index rejection with full rules,
controller and SQL-dump purity, then exact payment, persisted controller reload,
fresh-process read-only recovery and real priority passes resolving the effect.
Fresh recovery uses an explicit SQLite mode=ro connection and forbids sockets;
the API tests operate only a source-local disposable DB, never the live DB/NFS.
Legal-move display metadata is not a command: initial draft boundary failures
are preserved separately, not counted as production payment regressions.

Qualification, baseline/file/fixture hashes, exact serial neighbor selection and
private before/after snapshot receipts accompany the patch. No live deployment
or whole-suite-green claim is made. The historical Escape witness is unchanged.
