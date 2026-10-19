# Ninjutsu intent consumer guard

## Scope and dependency

Incremental over frozen canonical-ninjutsu-intent-audit-aSOT5i, patch SHA256
`ee419ebdf069ce8a097d115bf077fbf4267a16ca506e5eff82372676f626c648`.
The archived audited-backend-source.tar.gz supplies the exact baseline, including
the prior Foretell guard. No moving main/parent source or engine fix was applied.
Only production function `TrainingEnvironment.lookup_intent` changes; other
paths are the new guard test module and this document. API, schema, helper,
engine, dataset, producers and main remain untouched.

Public `NinjutsuAction` validates chosen fields BEFORE `complete_action`.
Unsupported keys, including null aliases, cannot be discarded. Source and
return CardIDs remain explicit: no target, cost, source or return is inferred.
Only `card_name`, `mana_cost`, `card_view` are display metadata, and supplied
values must exactly equal the current acting-seat eligible view for BOTH chosen
IDs. Metadata lookup uses a copied root. Bare typed actions avoid that extra
enumeration. Unknown/nested display changes and wrong actor/stale hints reject.
Raw API still rejects display fields; deliberate typed HTTP actions remain valid.
No full-hand performance or global ninjutsu/GUI support claim is made.

## Qualification ledger

Immutable audit baseline: 16 consumer failures, 26 independent passes, two
source-incarnation engine failures; exit 1, 71.07s. Original 44 tests unchanged.

Consumer qualification: original 44 plus NEW 52, all 96 executed without
skips, xfails or deselection: **94 passed, two engine failures**, 123 warnings,
143.06s, exit 1 (900s bound). All 16 former consumer failures and all NEW 52
pass. This is NOT a whole-96 green gate. The two ordinary failed assertions
remain `test_ninjutsu_pending_source_incarnation_does_not_move_reentered_card`
for seats 1 and 2. No engine dependency was applied or qualified here.

Separate serial fresh-local-SQLite neighbor gate: **259 passed**, 181 warnings,
444.35s, exit 0 (1800s bound), complete modules:

- test_training_foretell_intent_audit.py
- test_training_foretell_intent_guard.py
- test_training_environment.py
- test_training_dataset.py
- test_ai_action_contract.py
- test_training_combat_intent_guard.py

Both commands use pytest verbose, durations, no cache provider and no bytecode.
Before/end manifests match for all 965 source files. HTTP cases use own local
SQLite and forbid external network. Tests cover both seats, exact selected
second of two unblocked attackers, schema rejection before helper, whole legal
views, missing/invalid choices, actor privacy, root/DB purity, restart and stale
view rejection. Existing canonical combat damage and deliberately accepted or
declined optional draw controls remain passing. No fabricated Oracle text.

## Provenance and invariants

Environment preimage SHA256:
`8416c70395a0c6436d7cb40e20824beac5c88cfdb65bc4be7c8c68fb29e9d017`.
Postimage SHA256:
`1dc1c4f67931a2910c6af1133d585b5b6442794c6dc4072962e85f7eb8a11ff4`.
Unchanged original 44-test module SHA256:
`998ae3572682d0db09d30794ac7fee051172a992830cb515ce23e6eee4f20ba0`.
All 18 prior model bindings and all 13 prior display branches retain their
AST/bytes. Removing only the Ninja import, binding and branch restores the
whole original module AST. The full Scryfall response is unchanged, SHA256
`d5c28c0171ed64bf41b2435a9edcf4ebcef7cc5d121e27996c74b9a1a8f41b0f`,
official named-card URL and UTC provenance supplied by the immutable audit.

## Separate engine handoff

Unedited `rules_engine/engine.py:699` dispatches to
`rules_engine/keyword_actions.py:21` activate_ninjutsu. Line 43 queues only
attack_target. `effects/registry.py:221` dispatches to resolve_ninjutsu at
keyword_actions.py:47. It reads __source_card_id and current hand membership,
then moves the same CardID to battlefield without a captured incarnation check.
Keyword-actions SHA256:
`55bae25b6894fd90218fc0b7c9cb13db1a4b07faf38d4081739354648776382f`.
Engine SHA256:
`eb2ad608b61c6d9de5771ad82bca0c3dadc2bb2b7cc83d5f239b796a06d04690`.
These are audited baseline pins, NOT a claim of qualification of Sagan's fix.
The two retained probes perform a trusted hand-exile-hand zone transition while
pending; they are not a qualified real causal HTTP exile/return spell response.
Require separately frozen actual engine qualification before dependency pinning.
