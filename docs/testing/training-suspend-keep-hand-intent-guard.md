# Suspend and keep-hand consumer guard

## Exact dependency

Incremental three-path change over the immutable aadde4 test-only audit's
source-only.tar.gz (d3 application source), NOT over the later parent Land/Pass
composition. Preimage environment SHA256:
2a6c0251c8e89d4f97b074eab36a0790385f127da3aca3a418f8fc6a436c3143.
Engine eb1ae and keyword actions 8c8e remain unchanged. Public contracts, helper,
API, producers and all old branches are unchanged. Frozen prior audit bytes/logs
remain immutable. Its baseline had 32 sole consumer RED and 36 PASS; those same
68 test cases are retained without edits.

The pinned source has 19 prior public-model bindings, not the parent's later 21
which additionally include LandAction/PassAction. This patch adds SuspendAction
and KeepAction (21 total on this preimage). Removing only the two imports, bindings
and new branches restores the entire original module AST. All 14 old dispatch
branch bodies and all bytes outside lookup_intent remain identical. Apply only
as a surgical increment; do not overwrite a later parent's whole environment.py.
Land/Pass integration qualification belongs to a separate parent composition.

## Boundary

Public SuspendAction validates chosen card_id/type BEFORE complete_action. Display
allowlist is exactly the measured card_name, mana_cost, time_counters, card_view;
any supplied value must equal the current actor's actual offered Suspend view
for the explicitly selected source. The card_view is serialized from an engine
copy only after a matching offered action exists. Null, changed, scalar/object,
nested injected aliases and stale/foreign actor views reject before completion.
Unknown requested keys are rejected, even null. No card, target, cost, actor or
pending continuation is inferred or substituted. Bare authoritative actions
retain checked_action legality without enumerating presentation unnecessarily.

Public KeepAction validates the entire intent BEFORE complete_action; its display
allowlist is empty. Explicit bottom_card_ids/order is preserved. Missing bottoms
are not guessed: the authoritative check rejects insufficient choices on the
supported legacy unbottomed boundary, while an ordinary keep after current London
bottoming legitimately uses an empty default. Current London pending bottoms remain
choose_mechanic, never silently replaced by keep_hand. Raw API/lookup/step/encoding
remain unchanged. Known internal invalid-AI markers still cannot become accepted
actions; no behavior in other guard families changes.

## Qualification

Complete original two-module audit plus one NEW regression module, with independent
rejection witnesses and valid controls. NEW tests observe helper calls without
altering its behavior; unknown/null/malformed chosen parameters and display failures
must reject before any helper call. Full actual HTTP both-seat Rift Bolt and Ancestral
Vision controls exercise exact suspend costs, public exile/time counters, upkeep and
free-cast triggers, pending restart, deliberate targets or decline, no cast payment,
actual damage/draw outcome and final restart. Canonical fixture/provenance bytes and
full Oracle are inherited unchanged. Existing audits cover ordered legacy selections,
current London two rounds, chosen-card privacy, invalid selections, replay and HTTP
root/controller/full SQLite dump atomicity.

The first implementation's focused gate retained separately: 136 PASS / 8 failures
at the helper-observation assertion for malformed Keep bottoms (helper rejection
occurred too late), exit 1. Original 68 all passed. Explicit KeepAction validation
was then added, with original and NEW test assertions unchanged. Subsequent exact
terminal totals, logs, all-node JUnit, fresh-DB complete neighbor modules, AST proofs,
source/runtime inventories and checksum manifest are in the accompanying report.
No skips, xfails, deselections or historical red-ledger rewriting for a green claim.

Disposable source-only/no-.git/exact ownership marker; fresh local SQLite per gate,
serial execution, explicit timeout bounds and qualified cached interpreter. No
main/parent/live reads or writes, no engine/schema/helper changes, no package swaps.
Completed evidence archived on verified writable NFS, databases never executed on
NFS. No full-game engine/mechanics/UI/AI competence or special Suspend-card claims.
