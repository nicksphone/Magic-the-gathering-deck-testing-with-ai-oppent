# Retained Graveyard Shuffle Reference

## Frozen Composition

Reconstructed from immutable committed-graveyard-entry-emitter-OSIiwt backend
archive SHA2356b27a0dd0fb3c7cb8e5b9646b8b705599f7e5435f25f74dff17c0b6cf69c8.
It contains the frozen jry/efbd backend, original22, consumer7dce2be8 and emitter
4ceec540 (zone3b317d5e). The consumer's two new test modules were copied from its
verified frozen source archive, not from any moving parent root.

Only product file: `backend/rules_engine/shuffle_actions.py`.
Preimage8137af7d721567ba6c198544764849d71ae8e2c312ebac08d33661f052dfc5b4;
postimagea1f80220c9eeff168bb99c8a223a73ecf79ef118d96666f203e78a5db9ff3d86.
No handlers, zones, costs, events, compiler, registry, stack transport, keyword,
AI, API, schema or frontend changes. Those consumers/producers are dependencies,
not bundled whole-file replacements.

## Reader Contract

The real resolving StackItem dictionary is supplied through the unchanged
`resolving_item` ABI. Its complete private `__trigger_source_reference` is used
only with actual kind `triggered` and event `enters_graveyard`. Exact dictionary
keys are `incarnation` and `zone_change_sequence`; both must be nonnegative
integers, excluding bool, strings and extra/missing fields. The entry event
requires this reference; malformed/miscontextualized references fail before
helper RNG/log/shuffle-event effects. No static receipt substitution or invented
StackItem/cause/source ID. Other resolving shuffles retain their previous path.

The reference identifies the trigger's source at graveyard entry, PRE any later
movement; it is POST the original entry. Do not compare it with the source's
current zone/reference: Cremate legitimately changes those while the real
trigger remains on the stack. This reader relies on the engine's genuine
retained resolving-frame transport, not a new caller-dictionary authentication
or external action/API field. Existing source-record presence checks remain;
no assertion that sources erased from state/cards or all token/copy routes work.

## Executed Evidence

Before product edit, all six focused modules144 cases:20FAIL124PASS33.09s.
After the sole product hunk, the EXACT SAME six modules/test assertions:
144PASS34.92s. Original22/60 and prior desired episodes unchanged.
Twenty new cases: six actual lifecycle episodes (both seats x normal/Cremate/
Stifle) plus fourteen supplementary malformed-reference negatives built from
real paid trigger frames. No positive injected-event or fictional-card test.

Actual checked actions preserve deterministic repeated snapshot results. Fresh
process snapshot restart is checked at entry, paid response, and observer cause.
Normal and Cremate shuffles preserve the real trigger id/source/controller and
entry pair; Cremate's source stays exiled. Stifle prevents the shuffle/receipt.
One shuffle log, current whole-graveyard movement and opponent hidden hand/
library views are asserted. Negative helper calls preserve the full snapshot,
including RNG/log. These supplementary damaged-input calls are not legal-episode
certification.

Thirteen whole neighbor modules488PASS209.82s: static-cause ABI, static producer
resolution/HTTP, shuffle observer resolution/HTTP, library reorder/state/HTTP,
queued lifecycle/HTTP, counterability, graveyard departures, discard and mill.
No exclusions, skips or xfails; bounds300s focused/900s neighbors. Total632
distinct ordinary cases pass. Qualified cached Python3.12 matches backend pins;
no dependencies installed. Audit hook blocks network and foreign SQLite. All
SQLite stays in this independent local root; no main/live/parent writes.

Existing episode modules provide both-seat memory/file HTTP entry restart and
private-view/atomic-rejection checks. NEW Cremate/Stifle lifecycle tests use
checked engine actions plus fresh process snapshots, not new HTTP response
coverage. Do not conflate these two evidence scopes.

## Limits

The existing selected-discard batch/order cases pass on this composition;
that is not exhaustive simultaneous publication qualification. No deferred
batch publication, printed stack-face normalization, direct death/handler/
keyword migration, all-zone LKI, all-Kozilek, static receipt persistence or
deployment-readiness claim. Historical audit failures and frozen dependencies
are unchanged. Parent integrates this small incremental hunk separately from
Lagrange's handler migration and Sagan's keyword work.
