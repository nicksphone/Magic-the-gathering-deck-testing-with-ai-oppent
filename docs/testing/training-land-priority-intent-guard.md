# Land and priority consumer guard

## Frozen dependency and scope

Incremental over land-priority-intent-audit-AwMuaM, patch SHA256
`381961fa8c7157a261489de3d5f40fa78b27a36ed48695bcfe0aee08753817de`.
Its audited-backend-source.tar.gz supplies all 966 verified baseline files,
including the prior frozen c866 Ninja consumer guard. No current parent or main
copy and no Sagan engine dependency was consumed. Only production function
TrainingEnvironment.lookup_intent changes; NEW guard tests and this doc are
the other two patch paths. Original 48-test audit remains byte-identical.

Public LandAction and PassAction are imported locally and bound to exactly
play_land and pass_priority. PassAction.type is ONLY Literal[pass_priority];
next_step is not an action type added by this patch. Pass display allowlist is
empty. Unknown requested fields, including null fields, reject before helper.
The API, helper, schemas, producers, engine and raw/encoded actions are unchanged.

LandAction validates all authoritative fields before helper. Explicit source,
origin flags, permission key, face index and entry choice are retained under the
public model, not inferred or selected from suggestions. Omitted origin flags
retain schema defaults False; deliberate valid fixtures explicitly declare False.
Only card_view, card_name, graveyard_permission_name can be display. If supplied,
their values must exactly equal a current-actor offered legal move whose full
normalized PUBLIC LandAction parameters equal the requested action. card_view
is the existing serializer on the copied root. Unknown/null/changed/nested
metadata, unoffered names, wrong actor and stale views reject without helper.
Bare typed actions avoid extra legal-view enumeration and keep checked legality.
Root/input are unchanged; no performance improvement claim is made.

## Qualified evidence

Focused complete original48 + NEW88 = **136 ordinary passed**, 143 warnings,
143.88s, exit 0, timeout bound 900s. No skips, xfails or deselection. All prior
32 consumer RED expectations now pass unchanged, as do all 16 original controls.
New controls cover schema/unknown/null rejection before a delegating real helper,
malformed proper typed fields, exact whole HTTP legal views, deliberate second
basic-land choice, no inferred source, actual typed HTTP execution, wrong actor,
stale view, restart, privacy/hidden-order byte equality and action-alias reversal
for both seats. Pass has no inferred actor/phase parameter; actual priority
legality still runs through checked_action. Pass whole views are bare actions.

Separate serial fresh-local-SQLite neighbor gate: **336 ordinary passed**,
167 warnings, 266.61s, exit 0, bound 1800s; complete modules:

- test_training_environment.py
- test_training_dataset.py
- test_ai_action_contract.py
- test_training_foretell_intent_guard.py
- test_training_ninjutsu_intent_guard.py
- test_training_combat_intent_guard.py
- test_land_entry_choice.py
- test_graveyard_play_permissions.py

Both commands use pytest verbose/durations, no cache provider, no bytecode.
Owned SQLite stays local and HTTP tests forbid external network. Gates finished
before documentation was added. Both 967-source-file before/end manifests match,
SHA256 `f02d571f60e9102385037e2072506eba0fbacffeb6e4e8c89e377cce6caee88e`.
19 prior model bindings and 14 prior display branch bodies retain bytes/AST;
removing only two imports, two bindings and two branches restores whole module
AST. Every source byte outside lookup_intent is unchanged.

## Exact pins and limitations

Environment preimage SHA256:
`1dc1c4f67931a2910c6af1133d585b5b6442794c6dc4072962e85f7eb8a11ff4`.
Postimage:
`52fe5bffae33dc72f990c99fdff1fcfbe943a65af2adb3761792b89e68b10ed1`.
Unchanged original48 SHA256:
`fce1da1842f44bda04d10e8b1da03a32a90d2d13f4b1b6818795295550159f5b`.
NEW88 module SHA256:
`c6ca925b5a14d66ac6d40936068b85497a6ce70b35aec03f38caf71bc077e3c9`.
Unchanged engine:
`eb2ad608b61c6d9de5771ad82bca0c3dadc2bb2b7cc83d5f239b796a06d04690`.
Unchanged keyword_actions:
`55bae25b6894fd90218fc0b7c9cb13db1a4b07faf38d4081739354648776382f`.

Immutable audit history remains: final32RED16PASS72.77s exit1; draft32consumerRED,
12PASS and four default-False test-comparison failures113.67s exit1. Neither
archive/log/test version was rewritten; those are separate historical ledgers.
Basic hand-land card_view is the NEW positively qualified metadata. Basic-land
card_name/graveyard_permission_name are unoffered and must reject. No modal,
exile/graveyard origin, permission-label, or entry-choice CONSUMER metadata
certification is claimed; existing engine-neighbor passes are not that claim.
No new canonical card or altered Oracle was introduced. Existing two Ninja
incarnation engine failures remain outside this selected neighbor run; no engine
fix, causal response qualification, GUI completeness or model competence claim.
Parent must compose against its own newer engine separately; this source is not
the parent's nth/private/current Ninja-engine composition.
