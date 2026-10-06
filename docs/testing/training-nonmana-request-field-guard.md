# Non-mana requested-field guard

## Scope

Only `TrainingEnvironment.lookup_intent` changes in production. Its public-model
map now also covers `cast_spell` (`CastAction`) and `activate_ability`
(`AbilityAction`). Non-schema requested keys reject before `complete_action`,
including explicitly null extras. No private model catalog imports or duplicate
normalization helper. Typed values and required choices remain validated by the
existing helper and authoritative `checked_action`.

Qualified cast presentation keys: `card_name`, `mana_cost`, `cost_options`,
`target_hints`. Qualified activated presentation keys: `card_name`, `mana_cost`,
`ability_label`, `payment_options`, `activation_costs`, `hybrid_symbols`,
`target_hints`. The existing four mana types retain their previous public-model
map, display allowlist and rejection message. The existing `_invalid_ai_choice`
envelope handling is preserved.

These display keys are not chosen targets, costs, zones or faces. All schema
chosen fields remain present for validation, including nested targets/X,
`cost_choice`, `payment_choices` and ability index. Public schema default false
origin flags are legitimate defaults, not unsupported keys. Encoded actions,
strict lookup/step, raw API, engine, AI/helper and dataset implementation are
unchanged.

## Qualification

All execution gates were bounded and serial, with fresh local SQLite for each
post-fix gate, existing dependencies and no external network connections.

- Unchanged historical witnesses after the guard: 32 failures at their EARLIER
  acceptance call, 84 ordinary passes, 96 warnings, 179.61s, exit 1. Diagnostic
  only: the old tests require acceptance and then rejection of the same request.
- Shared 16-module gate before adapting those witnesses: 562 ordinary passes,
  250 warnings, 482.03s, exit 0. Defined shared scope is recorded in the archive.
- Explicitly authorized working-copy test adaptation, then complete 18-module
  gate: 620 ordinary passes, 304 warnings, 629.91s, exit 0.
- Separate adapted original/null plus NEW58 gate: 116 ordinary passes,
  159 warnings, 100.16s, exit 0. No skips, xfails or deselection in either final
  acceptance gate. Warnings are deprecated UTC datetime construction.

The 32 unsupported target/cost/zone/face cases now reject normally, including
null extras. NEW rejection-only cases also verify rejection precedes the helper:
their negative spy fails if normalization is reached; it never substitutes an
accepted action or changes production behavior. NEW58 code is unchanged from its
earlier passing post-fix run.

Both seats use actual canonical full legal views and execute/restart/replay:
Bolt's chosen player versus creature target yields different correct outcomes;
Sickening Dreams retains X=1 and exact selected Opt discard, preserving the
unselected Savannah Lions; Officer's actor-private inspection/selection remains
private; Goblin Warrens retains exact selected two-of-three Goblin payments,
preserves the unselected Goblin and creates three actual tokens. No invented
Oracle text or unsupported choice is fabricated. Whole intent dictionaries and
root snapshots remain unchanged by lookup. Raw rejected API actions preserve
root/controller and DB dumps. Hidden identity permutation and actor alias byte
equality controls rerun unchanged.

## Historical Ledger and Test Adaptation

Frozen original e900 audit: 16 strict failures/12 controls, 22.69s. Frozen null
e51 composed audit: 32 strict failures/26 controls, 73.47s, on the older P7 source.
Those archives, sources and logs remain byte-immutable; earlier default-false
comparison construction errors remain separately archived there.

Only two working-copy witness sections were adapted under explicit approval.
They now lookup the canonical action independently declared by the real-card
fixture and run its valid HTTP/replay controls. They NEVER create a valid control
by stripping the unsupported request. Raw lookup/API rejection and final
unsupported-intent rejection, root invariance and privacy controls remain.
All six parametrized positive-control function bodies/decorators (26 cases) are
unchanged, verified by AST comparison. Adaptation is a separate incremental
patch, not a mutation of e900/e51 or a production change.

New-test construction history is retained separately: initial Walking Ballista
counter-removal admission was not offered; a subsequent Goblin fixture lookup
used the wrong fixture file. Neither run qualifies those controls. Correct
canonical Goblin Warrens controls passed both seats before the production guard
(2 passes, 5.83s), and in both final acceptance gates. The unsupported Ballista
ability was not certified or altered.

## Source Precondition and Limits

Baseline is the frozen `current-ai-mana-frontend-static-qualified-source.tar.gz`.
All 876 backend files match `current-ai-mana-browser-qualified-source.tar.gz`
byte-for-byte (same backend manifest). Apply immutable e900 original tests/doc,
then immutable e51 null tests/doc, then the separate adaptation and guard
increments. The production preimage `backend/training/environment.py` SHA256 is
`a398d739a10b4d224295e955cdcef10dc52acadb62a0d90f855b404183eca074`.
Parent reports its later environment unchanged; these results do NOT claim
qualification of later layer/resource-access/AI/UI source compositions.

Only the two stated non-mana types are newly guarded. Loyalty and other non-mana
families remain outside this slice. Unknown `cast_variant` is not presentation
metadata in the public cast schema: unsupported whole views reject rather than
silently drop that request. These controls do not certify every alternate-zone,
multi-face, modal or activated mechanism, manual GUI, AI policy or NN competence.
No source changes during gates, main/live writes, database bootstrap against
user data or deployment. Finished evidence is archived on verified writable NFS;
databases run locally only. Source begin/end/AST and patch reconstruction hashes
are recorded alongside the final artifacts.
